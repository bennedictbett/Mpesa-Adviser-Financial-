cat > /mnt/user-data/outputs/README.md << 'EOF'
# M-Pesa Financial Advisor 

> A RAG-powered personal finance coach for Kenyans. Upload your M-Pesa statement PDF and ask natural language questions about your spending, saving, and sending habits. Answers are cited directly from your real transaction data — no guessing, no generic advice.

**Live demo:** [mpesa-adviser-financial.vercel.app](https://mpesa-adviser-financial.vercel.app)

---

## The Problem

Kenya has 30M+ active M-Pesa users. Yet most Kenyans have no clear picture of their financial health. Your M-Pesa statement is a PDF sitting in your email — full of valuable data about your spending, saving, and sending habits — but nobody reads it. Most people have no idea how much they spend on food, transport, or airtime every month, making it impossible to budget, save, or make better financial decisions.

General-purpose AI chatbots make this worse by answering financial questions from outdated training data with no source to verify against.

---

## The Solution

Upload your M-Pesa statement and ask:

- *"How much did I spend last month?"*
- *"What do I spend most of my money on?"*
- *"How can I save KES 5,000 this month?"*
- *"How much did I send to family in April?"*
- *"How much does it cost to send KES 2,500?"*

The advisor reads your actual transaction history, categorises every transaction, and gives you grounded, practical advice cited directly from your own data and official Safaricom/CBK documents.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  INGESTION PIPELINE                      │
│                 (runs once at setup)                     │
│                                                          │
│  PDF docs → pdf_parser → splitter → embeddings          │
│                                    ↓                     │
│                              ChromaDB                    │
│                           (vector store)                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   QUERY PIPELINE                         │
│                (runs on every question)                  │
│                                                          │
│  User question → embed → similarity search → ChromaDB   │
│                                    ↓                     │
│              retrieved chunks → prompt builder           │
│                                    ↓                     │
│                    Groq / Llama 3.3 70B                  │
│                                    ↓                     │
│                  Grounded answer + citations             │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| RAG Framework | LangChain | Orchestrates the full pipeline |
| Vector Database | ChromaDB | Stores and searches embeddings locally |
| Embeddings | HuggingFace all-MiniLM-L6-v2 | Converts text to vectors (free, local) |
| LLM | Groq / Llama 3.3 70B | Generates grounded answers |
| PDF Parsing | pdfplumber | Extracts text and tables from PDFs |
| Categoriser | Keyword + LLM inference | Classifies transactions into spending categories |
| API | FastAPI | Serves 6 REST endpoints |
| Frontend | Next.js + Tailwind CSS | 4-page chat and dashboard UI |
| Containerisation | Docker | Reproducible deployment |
| CI/CD | GitHub Actions | Automated testing and build checks |
| Backend hosting | Railway | Always-on Python deployment |
| Frontend hosting | Vercel | Global Next.js deployment |

---

## Project Structure

```
mpesa-advisor/
├── src/rag/
│   ├── __init__.py          # central config loader
│   ├── prompts.py           # all prompt templates
│   ├── llm.py               # Groq LLM client
│   ├── embeddings.py        # HuggingFace embeddings
│   ├── pdf_parser.py        # PDF text + table extraction
│   ├── loader.py            # loads PDFs from data/raw/
│   ├── splitter.py          # chunks text with overlap
│   ├── vectorstore.py       # ChromaDB build, load, update
│   ├── retriever.py         # similarity search
│   ├── chain.py             # RAG chain + financial advisor
│   ├── pipeline.py          # ingestion script
│   ├── categoriser.py       # transaction categorisation
│   └── statement_parser.py  # M-Pesa statement parser
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── routes.py            # /chat, /analyse, /upload, /parse-text
│   ├── schemas.py           # Pydantic request/response models
│   └── dependencies.py      # shared FastAPI dependencies
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # landing page
│   │   ├── upload/          # PDF upload + paste text
│   │   ├── dashboard/       # spending breakdown + charts
│   │   └── chat/            # AI advisor chat
│   └── components/
├── tests/                   # 28 passing tests
├── data/
│   ├── raw/                 # source PDFs
│   └── chroma_db/           # vector store
├── config/config.yaml       # all non-secret settings
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/chat` | General M-Pesa and CBK regulation questions |
| POST | `/api/v1/analyse` | Personal finance analysis from uploaded statement |
| POST | `/api/v1/upload` | Upload a PDF and ingest it into ChromaDB |
| POST | `/api/v1/parse-text` | Parse pasted M-Pesa statement text |
| GET | `/api/v1/health` | Health check |
| GET | `/` | API info |

Interactive docs: `https://mpesa-adviser-financial-production.up.railway.app/docs`

---

## Transaction Categories

The categoriser uses keyword matching + LLM inference to classify every transaction:

| Category | Examples |
|---|---|
| Food | NAIVAS, Quickmart, Java, restaurants |
| Transport | Uber, Bolt, matatu, fuel stations |
| Utilities | Kenya Power, Zuku, DSTV, water |
| Airtime | Safaricom airtime, data bundles |
| Banking | Equity, KCB, loan repayments, Fuliza |
| Family | Phone number transfers (07xx/01xx) |
| Business | Paybill, Buy Goods, Ltd companies |
| Other | Unrecognised transactions |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/bennedictbett/Mpesa-Adviser-Financial-.git
cd Mpesa-Adviser-Financial-

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt --prefer-binary

# Set up environment variables
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Add PDFs to data/raw/ then run ingestion
python -m src.rag.pipeline

# Start the API
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local
npm run dev
```

### Docker

```bash
docker-compose up --build
```

---

## Testing

```bash
pytest tests/ -v
```

28 tests covering loader, vectorstore, retriever, and pipeline modules.

---

## Deployment

| Service | Platform | URL |
|---|---|---|
| Frontend | Vercel | [mpesa-adviser-financial.vercel.app](https://mpesa-adviser-financial.vercel.app) |
| Backend | Railway | [mpesa-adviser-financial-production.up.railway.app](https://mpesa-adviser-financial-production.up.railway.app) |

---

## Skills Demonstrated

- **RAG architecture** — end-to-end retrieval augmented generation pipeline
- **LangChain** — document loading, text splitting, vector store integration
- **ChromaDB** — local vector database, similarity search, persistent storage
- **LLM integration** — Groq/Llama with structured prompting and citation grounding
- **Transaction categorisation** — keyword matching + LLM inference layers
- **Statement parsing** — PDF and pasted text support
- **FastAPI** — REST API with file upload, Pydantic validation, dependency injection
- **Next.js + Tailwind** — responsive 4-page frontend with charts and chat UI
- **Docker** — multi-stage containerised deployment
- **CI/CD** — GitHub Actions with structure checks and test enforcement
- **Full-stack deployment** — Railway (backend) + Vercel (frontend)

---

## Author

**Benedict Bett**

[Portfolio](https://bennedictbett.github.io/portfolio-project/) · [GitHub](https://github.com/bennedictbett) · [LinkedIn](https://www.linkedin.com/in/benedict-bett-a9899038a/)

---

*Built with LangChain · ChromaDB · Groq · FastAPI · Next.js*
EOF
Output

exit code 0