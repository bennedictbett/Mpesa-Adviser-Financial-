"""
Jarvis: the LLM-as-adviser layer. ...
"""

import json
import logging
import os
from functools import lru_cache

from groq import Groq

from backend.agents.prompts import JARVIS_SYSTEM_PROMPT
from backend.agents.tools import TOOL_SCHEMAS, make_tool_dispatcher

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-120b"
MAX_TOOL_ROUNDS = 4  # safety cap against runaway tool-call loops


@lru_cache(maxsize=1)
def get_client() -> Groq:
    """
    Lazily creates the Groq client on first use, not at import time.

    This matters for two reasons:
      1. Importing this module (e.g. in tests) must not require
         GROQ_API_KEY to be set — only actually calling ask_jarvis()
         should need it.
      2. Tests can patch this function directly instead of needing
         the real environment variable present.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Set it in your .env file — "
            "see console.groq.com for a free key."
        )
    return Groq(api_key=api_key)


def ask_jarvis(question: str, transactions: list[dict]) -> str:
    """
    Args:
        question: the user's natural-language question
        transactions: the full list of transactions for this session

    Returns:
        Jarvis's final plain-language answer.
    """
    client = get_client()
    dispatch = make_tool_dispatcher(transactions)

    messages = [
        {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

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