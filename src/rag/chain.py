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
        "Calling %s | model: %s | max_tokens: %d",
        settings.llm.provider,
        settings.llm.model,
        settings.llm.max_tokens,
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


def analyse_statement(
    question: str,
    history: list[dict] | None = None,
    transactions: list[dict] | None = None,
) -> dict:
    """
    Analyse an uploaded M-Pesa statement and give financial advice.

    Full pipeline:
      1. If transactions provided → categorise them
      2. Build a rich context string with spending breakdown
      3. Pass context + question to Claude/Llama for grounded advice

    Args:
        question:     The user's personal finance question
        history:      Optional conversation history for follow-up questions
        transactions: Optional pre-parsed transaction list from statement_parser.py
                      If not provided, falls back to RAG retrieval only

    Returns:
        dict: answer, sources, chunks_used, has_context, question
              Plus optional: categories, summary (if transactions provided)
    """
    logger.info("Statement analysis request: '%s'", question[:80])

    # ── If transactions provided, categorise and summarise ────
    extra_context = ""
    categories    = {}
    summary       = {}

    if transactions:
        from src.rag.categoriser import categorise_transactions, summarise_by_category
        from src.rag.statement_parser import get_statement_summary

        # Categorise every transaction
        categorised = categorise_transactions(transactions)
        categories  = summarise_by_category(categorised)
        summary     = get_statement_summary(transactions)

        # Build a structured context string for the LLM
        category_lines = "\n".join(
            f"  - {cat}: KES {amount:,.2f}"
            for cat, amount in categories.items()
        )

        extra_context = f"""
STATEMENT ANALYSIS:
Total transactions: {summary.get('total_transactions', 0)}
Total spent:        KES {summary.get('total_spent', 0):,.2f}
Total received:     KES {summary.get('total_received', 0):,.2f}
Date range:         {summary.get('date_range', {}).get('from')} → {summary.get('date_range', {}).get('to')}

SPENDING BY CATEGORY:
{category_lines}

TOP TRANSACTIONS:
{_format_top_transactions(categorised)}
"""

    # ── Enrich question with financial analysis framing ───────
    enriched_question = (
        f"{question}\n\n"
        f"{extra_context}\n"
        f"[Analyse the data above and give practical financial advice. "
        f"Be specific with KES amounts. Suggest concrete ways to save or budget better.]"
    )

    result = ask(enriched_question, history)

    # Attach category and summary data to response
    if categories:
        result["categories"] = categories
    if summary:
        result["summary"] = summary

    return result


def _format_top_transactions(transactions: list[dict], top_n: int = 5) -> str:
    """
    Format the top N transactions by amount for prompt context.

    Args:
        transactions: Categorised transaction list
        top_n:        Number of top transactions to include

    Returns:
        str: Formatted string of top transactions
    """
    if not transactions:
        return "No transactions available"

    sorted_txns = sorted(
        transactions,
        key=lambda x: x.get("amount", 0),
        reverse=True,
    )[:top_n]

    lines = []
    for t in sorted_txns:
        lines.append(
            f"  - {t.get('recipient', 'Unknown'):25s} "
            f"KES {t.get('amount', 0):>10,.2f}  "
            f"[{t.get('category', 'Other')}]"
        )

    return "\n".join(lines)


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