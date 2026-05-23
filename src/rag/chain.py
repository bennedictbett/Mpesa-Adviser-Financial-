"""
Wires the full RAG pipeline together — retrieves relevant chunks
from ChromaDB and calls Claude to generate a grounded answer.

Responsibilities:
  - Receive a user question and optional conversation history
  - Retrieve relevant chunks via retriever.py
  - Decide which prompt template to use (prompts.py)
  - Build the final prompt with context injected
  - Call Claude via llm.py
  - Return a structured response with answer, sources, and metadata

This is the brain of the application. Every user question
flows through this file exactly once per request.

Flow:
  question
    → retrieve chunks from ChromaDB (retriever.py)
    → if no chunks → NO_CONTEXT_PROMPT
    → if chunks found → RAG_PROMPT or CONVERSATIONAL_RAG_PROMPT
    → inject context into prompt
    → call Claude (llm.py)
    → return structured response

Only two files import from here:
  - app/routes.py   (API layer calls ask())
  - pipeline.py     (ingestion pipeline calls run_ingestion())
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage

from src.rag import settings
from src.rag.llm import get_llm
from src.rag.retriever import retrieve, format_context
from src.rag.prompts import (
    SYSTEM_PROMPT,
    RAG_PROMPT,
    CONVERSATIONAL_RAG_PROMPT,
    NO_CONTEXT_PROMPT,
    UPLOAD_CONFIRMATION,
)

logger = logging.getLogger(__name__)


def ask(
    question: str,
    history: list[dict] | None = None,
) -> dict:
    """
    Core RAG chain — answers a user question grounded in documents.

    Takes a question, retrieves the most relevant document chunks,
    builds a prompt, calls Claude, and returns a structured response.

    Handles three scenarios:
      1. No conversation history   → uses RAG_PROMPT
      2. Conversation history      → uses CONVERSATIONAL_RAG_PROMPT
      3. No relevant chunks found  → uses NO_CONTEXT_PROMPT

    Args:
        question: The user's question as a plain string
        history:  Optional list of previous messages for follow-up questions.
                  Each message is a dict with keys "role" and "content":
                  [
                      {"role": "user",      "content": "How much to send KES 100?"},
                      {"role": "assistant", "content": "Sending KES 100 costs..."},
                  ]

    Returns:
        dict: Structured response with keys:
              - "answer"       (str)       Claude's grounded answer
              - "sources"      (list[str]) list of source filenames cited
              - "chunks_used"  (int)       number of chunks retrieved
              - "has_context"  (bool)      whether relevant chunks were found
              - "question"     (str)       the original question echoed back

    Raises:
        ValueError: if question is empty or whitespace only
    """
    # Guard: question must not be empty 
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    clean_question = question.strip()
    history        = history or []

    logger.info(
        f"Processing question: "
        f"'{clean_question[:80]}{'...' if len(clean_question) > 80 else ''}'"
    )

    # Step 1: Retrieve relevant chunks
    results = retrieve(clean_question)
    has_context = len(results) > 0

    logger.info(
        f"Retrieval complete — "
        f"{len(results)} chunks found | "
        f"has_context: {has_context}"
    )

    # Step 2: Build the prompt 
    if not has_context:
        # No relevant chunks found — tell Claude to respond gracefully
        user_prompt = NO_CONTEXT_PROMPT.format(question=clean_question)
        logger.warning(
            f"No relevant chunks found for: '{clean_question[:80]}' — "
            f"using NO_CONTEXT_PROMPT"
        )

    elif history:
        # Follow-up question — include conversation history for context
        formatted_history = _format_history(history)
        context           = format_context(results)
        user_prompt       = CONVERSATIONAL_RAG_PROMPT.format(
            history=formatted_history,
            context=context,
            question=clean_question,
        )
        logger.info("Using CONVERSATIONAL_RAG_PROMPT (history present)")

    else:
        # Fresh question — standard RAG prompt
        context     = format_context(results)
        user_prompt = RAG_PROMPT.format(
            context=context,
            question=clean_question,
        )
        logger.info("Using RAG_PROMPT")

    # Step 3: Call Claude 
    llm = get_llm()

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    logger.info(
        f"Calling Claude | "
        f"model: {settings.llm.model} | "
        f"max_tokens: {settings.llm.max_tokens}"
    )

    response = llm.invoke(messages)
    answer   = response.content.strip()

    #  Step 4: Extract unique sources 
    sources = list({r["source"] for r in results}) if results else []

    logger.info(
        f"Response generated | "
        f"sources: {sources} | "
        f"answer length: {len(answer)} chars"
    )

    # Step 5: Return structured response 
    return {
        "answer":      answer,
        "sources":     sources,
        "chunks_used": len(results),
        "has_context": has_context,
        "question":    clean_question,
    }


def analyse_statement(question: str, history: list[dict] | None = None) -> dict:
    """
    Analyse a user's uploaded M-Pesa statement and give financial advice.

    This is a specialised version of ask() used when the user has uploaded
    their personal M-Pesa statement and wants spending analysis,
    budgeting advice, or financial insights from their own data.

    The same RAG pipeline runs — the difference is the question is
    framed around personal finance analysis so Claude gives advisory
    responses rather than just factual lookups.

    Common questions this handles:
      - "How much did I spend last month?"
      - "What do I spend most of my money on?"
      - "How can I save KES 5,000 this month?"
      - "How much did I send to family in April?"
      - "Am I spending more than I earn?"

    Args:
        question: The user's personal finance question
        history:  Optional conversation history for follow-up questions

    Returns:
        dict: Same structure as ask() —
              answer, sources, chunks_used, has_context, question
    """
    logger.info(f"Statement analysis request: '{question[:80]}'")

    # Enrich the question with financial analysis framing so Claude
    # knows to give advisory responses, not just factual citations
    enriched_question = (
        f"{question}\n\n"
        f"[Please analyse the transaction data in the context, identify spending "
        f"patterns, categorise transactions where possible, and give practical "
        f"financial advice based on the actual data. Be specific with amounts in KES.]"
    )

    return ask(enriched_question, history)


# Private helpers 

def _format_history(history: list[dict]) -> str:
    """
    Format conversation history into a readable string for the prompt.

    Converts the list of message dicts into a labelled dialogue string
    that CONVERSATIONAL_RAG_PROMPT injects into {history}.

    Args:
        history: List of message dicts with "role" and "content" keys

    Returns:
        str: Formatted dialogue string

    Example output:
        User: How much does it cost to send KES 500?
        Assistant: Sending KES 500 costs KES 6 according to the tariff guide.
        User: What about withdrawing that amount?
    """
    if not history:
        return ""

    lines = []
    for message in history:
        role    = message.get("role", "user").capitalize()
        content = message.get("content", "").strip()
        lines.append(f"{role}: {content}")

    return "\n".join(lines)