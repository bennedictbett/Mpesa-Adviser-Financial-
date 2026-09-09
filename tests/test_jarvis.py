"""
Unit tests for backend/agents/jarvis.py and tools.py.

Mocks the Groq client entirely — no real API calls, no cost, no
network dependency, and deterministic results regardless of what
model Groq has available this week. Tests the actual logic we
control: tool dispatch correctness, the tool-call loop, and the
MAX_TOOL_ROUNDS safety cap.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.tools import make_tool_dispatcher, TOOL_SCHEMAS
from backend.agents.jarvis import ask_jarvis, MAX_TOOL_ROUNDS


# --- Fixtures -----------------------------------------------------

@pytest.fixture
def sample_transactions():
    """Minimal set matching the real schema — enough for tools.py to compute against."""
    from datetime import datetime
    return [
        {
            "amount": 500.0, "trans_type": "payment", "category": "Food",
            "parsed_date": datetime(2026, 8, 1, 12, 0),
        },
        {
            "amount": 200.0, "trans_type": "sent", "category": "Transport",
            "parsed_date": datetime(2026, 8, 10, 9, 0),
        },
    ]


def _make_tool_call(name: str, arguments: dict, call_id: str = "call_1"):
    """Builds a mock tool_call object matching Groq/OpenAI's response shape."""
    tool_call = MagicMock()
    tool_call.id = call_id
    tool_call.function.name = name
    tool_call.function.arguments = json.dumps(arguments)
    return tool_call


def _make_response(content: str | None = None, tool_calls: list | None = None):
    """Builds a mock chat.completions.create() response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls or []

    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


# --- tools.py: dispatcher correctness (no mocking needed — pure functions) --

class TestToolDispatcher:
    def test_dispatches_get_spending_by_category(self, sample_transactions):
        dispatch = make_tool_dispatcher(sample_transactions)
        result = dispatch("get_spending_by_category", {"category": "Food", "month": "2026-08"})
        assert result == 500.0

    def test_dispatches_get_category_breakdown(self, sample_transactions):
        dispatch = make_tool_dispatcher(sample_transactions)
        result = dispatch("get_category_breakdown", {"month": "2026-08"})
        assert result == {"Food": 500.0, "Transport": 200.0}

    def test_unknown_tool_raises(self, sample_transactions):
        dispatch = make_tool_dispatcher(sample_transactions)
        with pytest.raises(ValueError, match="Unknown tool"):
            dispatch("not_a_real_tool", {})

    def test_dispatcher_is_scoped_to_its_own_transactions(self, sample_transactions):
        """
        Two dispatchers built from different transaction lists must never
        leak data between them — this is the session-isolation guarantee
        the whole make_tool_dispatcher() design exists for.
        """
        other_transactions = [
            {"amount": 9999.0, "trans_type": "payment", "category": "Food",
             "parsed_date": sample_transactions[0]["parsed_date"]}
        ]
        dispatch_a = make_tool_dispatcher(sample_transactions)
        dispatch_b = make_tool_dispatcher(other_transactions)

        assert dispatch_a("get_spending_by_category", {"category": "Food", "month": "2026-08"}) == 500.0
        assert dispatch_b("get_spending_by_category", {"category": "Food", "month": "2026-08"}) == 9999.0

    def test_all_schemas_have_matching_handlers(self, sample_transactions):
        """
        Tripwire: every tool declared in TOOL_SCHEMAS must have a working
        handler in the dispatcher, or Jarvis would advertise a tool to
        the LLM that then fails when called.
        """
        dispatch = make_tool_dispatcher(sample_transactions)
        schema_names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}

        # Minimal valid args per tool, just to prove dispatch doesn't raise "Unknown tool"
        sample_args = {
            "get_spending_summary": {"month": "2026-08"},
            "get_spending_by_category": {"category": "Food", "month": "2026-08"},
            "get_category_breakdown": {"month": "2026-08"},
            "get_monthly_comparison": {"month_a": "2026-07", "month_b": "2026-08"},
        }
        for name in schema_names:
            dispatch(name, sample_args[name])  # raises if handler missing


# --- jarvis.py: the tool-call loop, with Groq mocked ---------------

@patch("backend.agents.jarvis.get_client")
class TestAskJarvis:
    def test_direct_answer_no_tool_call(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response(
            content="I need more information to answer that."
        )

        result = ask_jarvis("What's the meaning of life?", sample_transactions)

        assert result == "I need more information to answer that."
        assert mock_client.chat.completions.create.call_count == 1

    def test_single_tool_call_then_final_answer(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tool_call = _make_tool_call("get_spending_by_category", {"category": "Food", "month": "2026-08"})

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tool_call]),
            _make_response(content="You spent 500.0 KES on Food in August 2026."),
        ]

        result = ask_jarvis("How much did I spend on Food in August?", sample_transactions)

        assert result == "You spent 500.0 KES on Food in August 2026."
        assert mock_client.chat.completions.create.call_count == 2

    def test_tool_result_passed_to_model_is_the_real_computed_value(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tool_call = _make_tool_call("get_spending_by_category", {"category": "Food", "month": "2026-08"})

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tool_call]),
            _make_response(content="Done."),
        ]

        ask_jarvis("How much did I spend on Food?", sample_transactions)

        second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_result_messages = [m for m in second_call_messages if m.get("role") == "tool"]

        assert len(tool_result_messages) == 1
        assert json.loads(tool_result_messages[0]["content"]) == 500.0

    def test_multiple_tool_calls_in_one_round(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tool_call_1 = _make_tool_call(
            "get_spending_by_category", {"category": "Food", "month": "2026-08"}, call_id="call_1"
        )
        tool_call_2 = _make_tool_call(
            "get_spending_by_category", {"category": "Transport", "month": "2026-08"}, call_id="call_2"
        )

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tool_call_1, tool_call_2]),
            _make_response(content="Food: 500, Transport: 200."),
        ]

        result = ask_jarvis("Compare Food and Transport spending.", sample_transactions)

        assert result == "Food: 500, Transport: 200."

    def test_tool_execution_error_is_caught_and_passed_back(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tool_call = _make_tool_call("get_spending_by_category", {"category": "Food", "month": "not-a-month"})

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tool_call]),
            _make_response(content="I couldn't understand that month — could you clarify?"),
        ]

        result = ask_jarvis("How much did I spend last blorp?", sample_transactions)

        assert "clarify" in result.lower()
        second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_result = next(m for m in second_call_messages if m.get("role") == "tool")
        assert "error" in json.loads(tool_result["content"])

    def test_hits_max_tool_rounds_and_returns_fallback_message(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        tool_call = _make_tool_call("get_spending_by_category", {"category": "Food", "month": "2026-08"})
        mock_client.chat.completions.create.return_value = _make_response(tool_calls=[tool_call])

        result = ask_jarvis("Loop forever?", sample_transactions)

        assert mock_client.chat.completions.create.call_count == MAX_TOOL_ROUNDS
        assert "wasn't able" in result.lower() or "rephrase" in result.lower()

    def test_system_prompt_is_included(self, mock_get_client, sample_transactions):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response(content="Fine.")

        ask_jarvis("Anything", sample_transactions)

        sent_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert sent_messages[0]["role"] == "system"
        assert "NEVER calculate" in sent_messages[0]["content"]