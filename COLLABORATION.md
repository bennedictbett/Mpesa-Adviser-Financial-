# M-Pesa Financial Advisor — Frontend Collaboration Guide

> This document is for the frontend developer joining the project.
> It covers what's already built, what you need to build,
> how the API works, and how to get running locally in minutes.

---

## What This Project Is

A RAG-powered personal finance advisor for Kenyan M-Pesa users.

A user uploads their M-Pesa statement PDF. The app reads their
transaction history and answers questions like:

- *"How much did I spend last month?"*
- *"What do I spend most of my money on?"*
- *"How can I save KES 5,000 this month?"*
- *"How much did I send to family in April?"*

It also answers general M-Pesa questions from official Safaricom
and CBK documents — fees, limits, regulations — with cited sources.

---

## What's Already Built (Backend — Do Not Touch)

```
src/rag/
├── __init__.py        ✅ config loader
├── prompts.py         ✅ Claude prompt templates
├── llm.py             ✅ Groq LLM client (Llama 3.1 70B)
├── embeddings.py      ✅ HuggingFace embeddings (free, local)
├── pdf_parser.py      ✅ PDF text + table extraction
├── loader.py          ✅ loads PDFs from data/raw/
├── splitter.py        ✅ chunks text with overlap
├── vectorstore.py     ✅ ChromaDB vector store
├── retriever.py       ✅ similarity search
├── chain.py           ✅ RAG chain + financial advisor logic
└── pipeline.py        ✅ ingestion script

app/
├── main.py            ✅ FastAPI entry point (runs on port 8000)
├── routes.py          ✅ /chat, /analyse, /upload, /health endpoints
├── schemas.py         ✅ request/response data shapes
└── dependencies.py    ✅ shared FastAPI dependencies
```

**You do not need to touch any of these files.**
The API is fully built and running. Your job is to build
the frontend that talks to it.

---

## What You Need to Build (Frontend)

```
frontend/
├── app/
│   ├── page.tsx              ← landing page
│   ├── chat/
│   │   └── page.tsx          ← main chat interface
│   └── upload/
│       └── page.tsx          ← PDF upload page
├── components/
│   ├── ChatWindow.tsx         ← chat message list
│   ├── ChatInput.tsx          ← message input + send button
│   ├── MessageBubble.tsx      ← individual message with citations
│   ├── UploadZone.tsx         ← drag-and-drop PDF upload
│   ├── SourceBadge.tsx        ← shows source document name
│   └── SpendingChart.tsx      ← spending breakdown chart (optional)
├── lib/
│   └── api.ts                 ← all API calls in one place
├── types/
│   └── index.ts               ← TypeScript types matching schemas.py
└── public/
    └── mpesa-logo.svg
```

**Tech stack:** Next.js 14 · TypeScript · Tailwind CSS

---

## API Reference — Everything You Need to Know

Base URL (local): `http://localhost:8000`

All endpoints are prefixed with `/api/v1`

---

### POST `/api/v1/chat`
General M-Pesa and CBK regulation questions.

**Request:**
```typescript
{
  question: string          // max 1000 chars
  history?: {               // optional — for follow-up questions
    role: "user" | "assistant"
    content: string
  }[]
}
```

**Response:**
```typescript
{
  answer:      string       // Claude's grounded answer
  sources:     string[]     // e.g. ["mpesa_tariff_2024.pdf"]
  chunks_used: number       // how many doc chunks were used
  has_context: boolean      // false = no relevant docs found
  question:    string       // original question echoed back
}
```

**Example:**
```typescript
const res = await fetch("http://localhost:8000/api/v1/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "How much does it cost to send KES 500?"
  })
})
const data = await res.json()
// data.answer → "Sending KES 500 costs KES 6 according to..."
// data.sources → ["mpesa_tariff_2024.pdf"]
```

---

### POST `/api/v1/analyse`
Personal finance analysis from an uploaded M-Pesa statement.
Use this endpoint after the user has uploaded their statement.

**Request:** same shape as `/chat`
```typescript
{
  question: string
  history?: { role: string, content: string }[]
}
```

**Response:** same shape as `/chat`
```typescript
{
  answer:      string
  sources:     string[]     // will include the uploaded statement filename
  chunks_used: number
  has_context: boolean
  question:    string
}
```

**Example:**
```typescript
const res = await fetch("http://localhost:8000/api/v1/analyse", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "How much did I spend on food last month?"
  })
})
```

---

### POST `/api/v1/upload`
Upload a PDF (M-Pesa statement or any document).
The file is ingested into the knowledge base immediately.

**Request:** `multipart/form-data`
```typescript
FormData with field "file" → PDF file (max 10MB)
```

**Response:**
```typescript
{
  message:      string    // "Successfully ingested 'statement.pdf'..."
  filename:     string    // "statement.pdf"
  chunks_added: number    // how many chunks were stored
}
```

**Example:**
```typescript
const formData = new FormData()
formData.append("file", pdfFile)

const res = await fetch("http://localhost:8000/api/v1/upload", {
  method: "POST",
  body: formData          // no Content-Type header — browser sets it
})
const data = await res.json()
// data.message → "Successfully ingested 'statement.pdf'. 47 chunks stored."
```

---

### GET `/api/v1/health`
Check if the API is running. Call this on app load to show
a connection status indicator in the UI.

**Response:**
```typescript
{
  status:  "ok"
  version: "1.0.0"
}
```

---

## TypeScript Types (copy into `types/index.ts`)

```typescript
export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export interface ChatRequest {
  question: string
  history?: ChatMessage[]
}

export interface ChatResponse {
  answer:      string
  sources:     string[]
  chunks_used: number
  has_context: boolean
  question:    string
}

export interface UploadResponse {
  message:      string
  filename:     string
  chunks_added: number
}

export interface HealthResponse {
  status:  string
  version: string
}
```

---

## Getting Started Locally

### 1. Clone the repo
```bash
git clone https://github.com/bennedictbett/Mpesa-Adviser-Financial-.git
cd Mpesa-Adviser-Financial-
```

### 2. Start the backend API
```bash
# create and activate venv
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# install dependencies
pip install -r requirements.txt --prefer-binary

# set up environment
cp .env.example .env
# add your GROQ_API_KEY to .env (get free key at console.groq.com)

# run ingestion pipeline (builds the knowledge base)
python -m src.rag.pipeline

# start the API
uvicorn app.main:app --reload
```

API is now running at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

### 3. Set up the frontend
```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint
npm run dev
```

Frontend runs at `http://localhost:3000`

---

## UI Flow

```
Landing page
    │
    ▼
Upload page ──── user uploads M-Pesa statement PDF
    │               │
    │               └── POST /api/v1/upload
    │                   show success + chunks_added
    ▼
Chat page ──────────── two modes:
    │
    ├── General questions  → POST /api/v1/chat
    │   "How much to send KES 500?"
    │
    └── Statement analysis → POST /api/v1/analyse
        "How much did I spend last month?"
```

---

## Key UI Details

**Show sources under every answer**

Every API response includes a `sources` array. Always render these
below the answer so users can see which document the answer came from.

```tsx
{response.sources.map(source => (
  <SourceBadge key={source} name={source} />
))}
```

**Handle `has_context: false`**

When `has_context` is `false`, the API could not find relevant
information. Show a friendly message instead of the raw answer:

```tsx
{!response.has_context && (
  <p>I couldn't find that in my documents.
     Try rephrasing or check safaricom.co.ke</p>
)}
```

**Conversation history for follow-up questions**

Store messages in state and pass them with every request so the
AI understands follow-up questions:

```tsx
const [history, setHistory] = useState<ChatMessage[]>([])

// on every new question:
const response = await chat({ question, history })
setHistory(prev => [
  ...prev,
  { role: "user",      content: question        },
  { role: "assistant", content: response.answer },
])
```

---

## Environment Variables (Frontend)

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Use in code:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL
```

---

## Questions?

**Backend:** Benedict Bett
[GitHub](https://github.com/bennedictbett) ·
[Portfolio](https://bennedictbett.github.io/portfolio-project/)