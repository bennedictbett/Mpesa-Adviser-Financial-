"""
Wraps analytics_service.py functions as LLM-callable tools.

Jarvis never touches raw transactions or does arithmetic itself —
it only ever sees the tool schemas below and whatever plain-value
result get_tool_dispatcher() returns after calling the real
analytics_service.py function. This is the enforcement point for
"the LLM explains, Python calculates."
"""

from backend.services.analytics_service import (
    get_spending_summary,
    get_spending_by_category,
    get_category_breakdown,
    get_monthly_comparison,
)

# OpenAI/Groq-compatible tool schemas.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_spending_summary",
            "description": "Total spent, total received, and net for a given month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Format YYYY-MM, e.g. 2026-08"},
                },
                "required": ["month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spending_by_category",
            "description": "Total amount spent in ONE specific category (e.g. Food, Transport) for a given month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "e.g. Food, Transport, Utilities, Airtime, Banking, Business, Cash Withdrawal, Other"},
                    "month": {"type": "string", "description": "Format YYYY-MM"},
                },
                "required": ["category", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_breakdown",
            "description": "Spending broken down by ALL categories for a given month, sorted highest first. Use this for questions like 'what do I spend most on'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Format YYYY-MM"},
                },
                "required": ["month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_comparison",
            "description": "Per-category spending change between two months. Use for questions like 'did I spend more this month than last'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "description": "Earlier month, format YYYY-MM"},
                    "month_b": {"type": "string", "description": "Later month, format YYYY-MM"},
                },
                "required": ["month_a", "month_b"],
            },
        },
    },
]

TOOL_SCHEMAS.append({
    "type": "function",
    "function": {
        "name": "get_budget_status",
        "description": (
            "Whether spending in a category is under, near, or over budget "
            "for a given month. If the user hasn't set a budget, this uses "
            "an average of their past months' spending as a suggested budget."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "month": {"type": "string", "description": "Format YYYY-MM"},
            },
            "required": ["category", "month"],
        },
    },
})


def make_tool_dispatcher(transactions: list[dict], budget_overrides: dict[str, float] | None = None):
    from backend.services.budget_service import get_budget_status  # avoid circular import

    budget_overrides = budget_overrides or {}

    handlers = {
        "get_spending_summary": lambda args: get_spending_summary(transactions, month=args["month"]),
        "get_spending_by_category": lambda args: get_spending_by_category(
            transactions, category=args["category"], month=args["month"]
        ),
        "get_category_breakdown": lambda args: get_category_breakdown(transactions, month=args["month"]),
        "get_monthly_comparison": lambda args: get_monthly_comparison(
            transactions, month_a=args["month_a"], month_b=args["month_b"]
        ),
        "get_budget_status": lambda args: get_budget_status(
            transactions,
            category=args["category"],
            month=args["month"],
            override_amount=budget_overrides.get(args["category"]),
        ),
    }

    def dispatch(name: str, arguments: dict):
        if name not in handlers:
            raise ValueError(f"Unknown tool: {name}")
        return handlers[name](arguments)

    return dispatch


def make_tool_dispatcher(transactions: list[dict], budget_overrides: dict[str, float] | None = None):
    from backend.services.budget_service import get_budget_status  # avoid circular import

    budget_overrides = budget_overrides or {}

    handlers = {
        "get_spending_summary": lambda args: get_spending_summary(transactions, month=args["month"]),
        "get_spending_by_category": lambda args: get_spending_by_category(
            transactions, category=args["category"], month=args["month"]
        ),
        "get_category_breakdown": lambda args: get_category_breakdown(transactions, month=args["month"]),
        "get_monthly_comparison": lambda args: get_monthly_comparison(
            transactions, month_a=args["month_a"], month_b=args["month_b"]
        ),
        "get_budget_status": lambda args: get_budget_status(
            transactions,
            category=args["category"],
            month=args["month"],
            override_amount=budget_overrides.get(args["category"]),
        ),
    }

    def dispatch(name: str, arguments: dict):
        if name not in handlers:
            raise ValueError(f"Unknown tool: {name}")
        return handlers[name](arguments)

    return dispatch