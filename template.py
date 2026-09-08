import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s')

project_name = "mpesa_advisor"

# Files from earlier iterations that are no longer needed.
# (Nothing removed this pass — new structure is additive to the existing RAG/app layout.)
files_to_remove = [
    "src/visualization.py",
]

for f in files_to_remove:
    p = Path(f)
    if p.exists():
        p.unlink()
        logging.info(f"Removed unwanted file: {f}")

list_of_files = [
    # CI/CD
    ".github/workflows/ci.yml",

    # --- Existing RAG core (LangChain) — unchanged ---
    "src/rag/__init__.py",
    "src/rag/loader.py",
    "src/rag/pdf_parser.py",
    "src/rag/splitter.py",
    "src/rag/embeddings.py",
    "src/rag/vectorstore.py",
    "src/rag/retriever.py",
    "src/rag/pipeline.py",
    "src/rag/llm.py",
    "src/rag/prompts.py",

    # --- Existing API (app/) — kept during transition ---
    "app/__init__.py",
    "app/main.py",
    "app/routes.py",
    "app/schemas.py",
    "app/dependencies.py",

    # --- NEW: backend/ (Jarvis architecture) ---
    "backend/__init__.py",
    "backend/main.py",

    "backend/api/__init__.py",
    "backend/api/routes/__init__.py",
    "backend/api/routes/transactions.py",
    "backend/api/routes/analytics.py",
    "backend/api/routes/agent.py",

    "backend/agents/__init__.py",
    "backend/agents/jarvis.py",
    "backend/agents/prompts.py",
    "backend/agents/tools.py",

    "backend/services/__init__.py",
    "backend/services/transaction_service.py",
    "backend/services/analytics_service.py",
    "backend/services/financial_adviser.py",

    "backend/models/__init__.py",
    "backend/models/schemas.py",

    "backend/database/__init__.py",
    "backend/database/connection.py",
    "backend/database/models.py",

    # Frontend
    "frontend/app.py",
    "frontend/utils.py",

    # Data
    "data/raw/.gitkeep",
    "data/chroma_db/.gitkeep",

    # --- Tests: existing + new backend coverage ---
    "tests/__init__.py",
    "tests/test_loader.py",
    "tests/test_vectorstore.py",
    "tests/test_retriever.py",
    "tests/test_pipeline.py",
    "tests/test_transaction_service.py",
    "tests/test_analytics_service.py",
    "tests/test_agent_tools.py",
    "tests/test_jarvis.py",

    # Config
    "config/config.yaml",

    # Docker
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",

    # Project files
    "requirements.txt",
    "setup.py",
    ".env.example",
    ".gitignore",
    "README.md",
    "DEPLOYMENT.md",
    "SECURITY.md",
]

for filepath in list_of_files:
    filepath = Path(filepath)
    filedir, filename = os.path.split(filepath)

    if filedir != "":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory: {filedir} for the file: {filename}")

    if (not os.path.exists(filepath)) or (os.path.getsize(filepath) == 0):
        with open(filepath, "w") as f:
            pass
        logging.info(f"Creating empty file: {filepath}")
    else:
        logging.info(f"{filename} already exists")

logging.info("Project structure created successfully!")