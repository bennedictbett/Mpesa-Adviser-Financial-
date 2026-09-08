"""
Jarvis: the LLM-as-adviser layer. Calls Groq with function-calling,
executes real analytics_service.py functions for any tool the model
requests, and returns the model's final explanation.

Architecture (see also backend/agents/tools.py):
    User question
        -> Jarvis (LLM decides which tool(s) to call)
        -> real analytics_service.py function executes
        -> real number goes back to the LLM
        -> Jarvis explains the real number in plain language

The LLM is never shown raw transactions and never does arithmetic
itself — see prompts.py's system prompt for the explicit constraint.
"""

import json
import logging
import os

from groq import Groq

from backend.agents.prompts import JARVIS_SYSTEM_PROMPT
from backend.agents.tools import TOOL_SCHEMAS, make_tool_dispatcher

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-120b"
MAX_TOOL_ROUNDS = 4  # safety cap against runaway tool-call loops

_client = Groq(api_key=os.environ["GROQ_API_KEY"])


def ask_jarvis(question: str, transactions: list[dict]) -> str:
    """
    Args:
        question: the user's natural-language question
        transactions: the full list of transactions for this session
                       (already categorised + date-normalised)

    Returns:
        Jarvis's final plain-language answer.
    """
    dispatch = make_tool_dispatcher(transactions)

    messages = [
        {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        response = _client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = response.choices[0].message

        if not message.tool_calls:
            # No more tools requested — this is Jarvis's final answer.
            return message.content

        # Model wants to call one or more tools. Append its request,
        # execute each real function, append the results, loop back.
        messages.append(message)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            logger.info("Jarvis calling tool: %s(%s)", name, arguments)

            try:
                result = dispatch(name, arguments)
            except Exception as e:
                logger.exception("Tool call failed: %s", name)
                result = {"error": str(e)}

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    logger.warning("Jarvis hit MAX_TOOL_ROUNDS without a final answer")
    return "I wasn't able to work out an answer to that — could you rephrase or ask about a specific month?"