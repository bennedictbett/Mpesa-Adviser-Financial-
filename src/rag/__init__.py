"""
Central configuration loader for the M-Pesa Financial Advisor RAG pipeline.

Loads:
  - config/config.yaml  → non-secret settings (chunk size, model names, paths)
  - .env                → secret settings (API keys)

Every file in src/rag/ imports `settings` from here:
    from src.rag import settings
"""

import yaml
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


load_dotenv()

 
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"

with open(CONFIG_PATH, "r") as f:
    _cfg = yaml.safe_load(f)


# Pydantic settings secctions

class AppSettings:
    name: str        = _cfg["app"]["name"]
    version: str     = _cfg["app"]["version"]
    description: str = _cfg["app"]["description"]
    debug: bool      = _cfg["app"]["debug"]


class PathSettings:
    raw_data:  str = _cfg["paths"]["raw_data"]
    chroma_db: str = _cfg["paths"]["chroma_db"]


class PDFSettings:
    supported_extensions: list = _cfg["pdf"]["supported_extensions"]
    extract_tables: bool        = _cfg["pdf"]["extract_tables"]
    min_page_chars: int         = _cfg["pdf"]["min_page_chars"]


class SplitterSettings:
    chunk_size:    int  = _cfg["splitter"]["chunk_size"]
    chunk_overlap: int  = _cfg["splitter"]["chunk_overlap"]
    separators:    list = _cfg["splitter"]["separators"]


class EmbeddingSettings:
    provider:   str = _cfg["embeddings"]["provider"]
    model:      str = _cfg["embeddings"]["model"]
    dimensions: int = _cfg["embeddings"]["dimensions"]


class VectorStoreSettings:
    collection_name: str = _cfg["vectorstore"]["collection_name"]
    distance_metric: str = _cfg["vectorstore"]["distance_metric"]


class RetrieverSettings:
    top_k:           int   = _cfg["retriever"]["top_k"]
    score_threshold: float = _cfg["retriever"]["score_threshold"]


class LLMSettings:
    provider:    str   = _cfg["llm"]["provider"]
    model:       str   = _cfg["llm"]["model"]
    max_tokens:  int   = _cfg["llm"]["max_tokens"]
    temperature: float = _cfg["llm"]["temperature"]


class APISettings:
    host:   str  = _cfg["api"]["host"]
    port:   int  = _cfg["api"]["port"]
    reload: bool = _cfg["api"]["reload"]


class FrontendSettings:
    api_url:           str = _cfg["frontend"]["api_url"]
    page_title:        str = _cfg["frontend"]["page_title"]
    page_icon:         str = _cfg["frontend"]["page_icon"]
    max_upload_size_mb: int = _cfg["frontend"]["max_upload_size_mb"]


# Secret settings loaded from .env 
class SecretSettings(BaseSettings):
    OPENAI_API_KEY:    str = Field(..., env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: str = Field(..., env="ANTHROPIC_API_KEY")
    APP_ENV:           str = Field("development", env="APP_ENV")

    class Config:
        env_file = ".env"
        extra = "ignore"


# Master settings object
class Settings:
    """
    Single settings object used across the entire project.

    Usage in any file:
        from src.rag import settings

        print(settings.llm.model)           # claude-sonnet-4-20250514
        print(settings.splitter.chunk_size) # 800
        print(settings.secrets.OPENAI_API_KEY)
    """
    app:         AppSettings         = AppSettings()
    paths:       PathSettings        = PathSettings()
    pdf:         PDFSettings         = PDFSettings()
    splitter:    SplitterSettings    = SplitterSettings()
    embeddings:  EmbeddingSettings   = EmbeddingSettings()
    vectorstore: VectorStoreSettings = VectorStoreSettings()
    retriever:   RetrieverSettings   = RetrieverSettings()
    llm:         LLMSettings         = LLMSettings()
    api:         APISettings         = APISettings()
    frontend:    FrontendSettings    = FrontendSettings()
    secrets:     SecretSettings      = SecretSettings()

settings = Settings()