# Mpesa-Adviser-Financial-

> Upload your M-Pesa statement. Get a personal financial advisor.

## The Problem

Millions of Kenyans transact daily on M-Pesa but have no clear picture of their
financial health. Your M-Pesa statement is a PDF sitting in your email — full of
valuable data about your spending, saving, and sending habits — but nobody reads
it. Most people have no idea how much they spend on food, transport, or airtime
every month, making it impossible to budget, save, or make better financial decisions.

## The Solution

The **M-Pesa Financial Advisor** turns your M-Pesa statement into a personal
finance coach. Upload your statement PDF and ask it:

- *"How much did I spend last month?"*
- *"What do I spend most of my money on?"*
- *"How much did I send to family in April?"*
- *"Am I spending more than I earn?"*
- *"How can I save KES 5,000 this month based on my habits?"*

It reads your actual transaction history, identifies your spending patterns,
and gives you grounded, practical advice — cited directly from your own data.
It also answers general M-Pesa and CBK regulation questions from official
documents when needed.

## My Approach

I built a RAG (Retrieval Augmented Generation) pipeline with two knowledge sources:

1. **Your M-Pesa statement** — uploaded at runtime, parsed and indexed instantly
   so the advisor can answer personal finance questions from your real data
2. **Official documents** — Safaricom tariff guides and CBK mobile money
   regulations ingested at setup for general M-Pesa questions

Both sources live in the same ChromaDB vector store. When you ask a question,
the system retrieves the most relevant chunks from either source, passes them
to Claude, and generates a cited, grounded answer — no guessing, no hallucination,
no generic advice that ignores your actual situation.

**Stack:** LangChain · ChromaDB · Claude API · OpenAI Embeddings · FastAPI · Streamlit
