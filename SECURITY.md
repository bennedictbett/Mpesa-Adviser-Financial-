# Security Overview

This document describes the security measures built into the M-Pesa
Financial Advisor backend, and is honest about what is **not** yet
in place. It's written for both contributors and anyone evaluating
this project's engineering practices.

## Threat model

This is a portfolio/demo project handling **real financial statement
data** (M-Pesa transactions), with an LLM (Jarvis) that can query —
but never modify — that data. The primary risks considered:

1. An LLM inventing or miscalculating financial figures
2. Uncontrolled API cost exposure from LLM calls
3. Malformed or malicious input crashing the service or leaking
   internals
4. Unauthorized access to another user's financial data

---

## 1. Jarvis is read-only by design

Jarvis (the LLM adviser layer, `backend/agents/`) can only call a
fixed, explicit allow-list of functions defined in
`backend/agents/tools.py`:

- `get_spending_summary`
- `get_spending_by_category`
- `get_category_breakdown`
- `get_monthly_comparison`
- `get_budget_status`

**Every one of these is a read-only query.** There is no tool that
inserts, updates, or deletes a transaction, and no mechanism for the
LLM to construct or execute arbitrary SQL — it can only call
pre-defined Python functions with pre-defined argument shapes. The
LLM never sees raw transaction rows directly; it only receives the
numeric/dict result of a real calculation performed by
`analytics_service.py` or `budget_service.py`.

The system prompt (`backend/agents/prompts.py`) additionally
instructs the model to never calculate a number itself — every
figure in its response must come from a tool result — but this is a
**behavioral guardrail, not a security boundary**. The real
enforcement is structural: even if the model ignored the prompt, it
has no tool available that could alter data or run unrestricted
queries.

This is tested in `tests/test_jarvis.py`
(`test_tool_result_passed_to_model_is_the_real_computed_value`,
`test_all_schemas_have_matching_handlers`).

## 2. Rate limiting

The `/api/v1/{session_id}/ask` endpoint — the only endpoint that
calls the Groq API and therefore the only one with a real per-request
cost — is rate-limited to **10 requests/minute per client IP** via
`slowapi` (see `backend/rate_limit.py`). Since a single request can
trigger up to `MAX_TOOL_ROUNDS` (4) LLM calls internally, this caps
worst-case cost exposure from any one client to a bounded amount
rather than leaving it open-ended.

Ingestion and analytics endpoints are not currently rate-limited, as
they don't call any paid external API.

## 3. Input validation

- **Month strings** (`YYYY-MM`) are validated in `analytics_service.py`
  and raise `ValueError` on malformed input; every route that accepts
  a month string catches this and returns a clean `422` rather than
  letting it surface as an unhandled `500` (see
  `backend/api/routes/analytics.py`).
- **Budget amounts** are bounded via Pydantic (`gt=0, le=10_000_000`)
  in `backend/api/routes/budget.py` — rejects negative, zero, and
  implausibly large values before they reach any business logic.
- **File uploads** are restricted to `.pdf` extension and capped at
  10MB, checked against the actual byte count read into memory
  (not a client-supplied `Content-Length` header, which can be
  missing or spoofed) — see `backend/api/routes/transactions.py`.
- **Category strings** have a minimum length requirement, rejecting
  empty-string categories on budget overrides.

Covered by `tests/test_api_validation.py`.

## 4. Statement parsing is defensive, not trusting

`src/rag/statement_parser.py`'s block parser was fixed to require at
least one digit in a candidate "receipt number" token, after testing
revealed that all-uppercase merchant names (e.g. `SUPERMARKET`,
`QUICKMART`) could be misidentified as receipt-number boundaries and
silently split a transaction into unparseable, dropped fragments.
Regression-tested in `tests/test_statement_parser.py`.

Malformed or unparseable dates never crash the pipeline or get
defaulted to a guessed date — they're excluded from month-based
calculations entirely (`parsed_date = None`), so a single bad row
can't corrupt an aggregate figure. Regression-tested throughout
`tests/test_analytics_service.py` and `tests/test_database.py`.

---

## Known limitations (not yet addressed)

Being explicit about these rather than leaving them implicit:

1. **No authentication.** `session_id` (a UUID4) isolates one
   upload's data from another's, but it is not an access-control
   mechanism — anyone who obtains a valid `session_id` can query or
   set budgets for that session. UUID4 is unguessable by brute force,
   but this is security-through-obscurity, not real authorization.
   A production version would need a login/auth layer.

2. **The LLM-fallback categoriser path is stubbed.**
   `transaction_service.categorise_by_llm` currently returns
   `"Other"` for any transaction the keyword rules can't place,
   rather than actually calling an LLM. This was a deliberate
   sequencing choice (validate the deterministic pipeline before
   adding a non-deterministic fallback) but means the real
   "uncategorised" rate on messy, real-world statements hasn't yet
   been measured.

3. **No CORS configuration or HTTPS enforcement** — appropriate for
   local development, not for a public deployment.

4. **The ingestion/analytics/budget endpoints are not
   rate-limited** — only `/ask` is, since it's the only one with a
   direct external API cost. A public deployment would want limits
   on upload volume too, to prevent storage/DB abuse.

5. **Budget overrides have no history or audit trail** — setting a
   new override for a category silently replaces the old one.