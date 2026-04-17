# # =============================================================================
# # backend/config.py
# # Single source of truth for all backend configuration.
# # All values can be overridden via environment variables.
# # =============================================================================

# import os
# from pathlib import Path

# # ---------------------------------------------------------------------------
# # Paths — backend sits one level below project root
# # ---------------------------------------------------------------------------
# PROJECT_ROOT = Path(__file__).parent.parent
# CHROMA_DIR   = str(PROJECT_ROOT / "data" / "chromadb")
# LOG_DIR      = str(PROJECT_ROOT / "logs")

# # ---------------------------------------------------------------------------
# # ISKCON Contact
# # ---------------------------------------------------------------------------
# ISKCON_NAME    = os.getenv("ISKCON_NAME",    "ISKCON Pune NVCC")
# ISKCON_PHONE   = os.getenv("ISKCON_PHONE",   "+91-XXXXXXXXXX")
# ISKCON_EMAIL   = os.getenv("ISKCON_EMAIL",   "nvcc@iskconpune.org")
# ISKCON_WEBSITE = os.getenv("ISKCON_WEBSITE", "https://iskconpune.com")

# # ---------------------------------------------------------------------------
# # LLM Provider
# # Change ACTIVE_LLM to switch provider. Options: groq | openai | gemini | anthropic
# # ---------------------------------------------------------------------------
# ACTIVE_LLM  = os.getenv("ACTIVE_LLM", "groq")
# MAX_TOKENS  = int(os.getenv("MAX_TOKENS",  "1500"))
# TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

# LLM_SPECS = {
#     "groq":      {"model": "llama-3.3-70b-versatile",  "key_env": "GROQ_API_KEY"},
#     "openai":    {"model": "gpt-4o-mini",               "key_env": "OPENAI_API_KEY"},
#     "gemini":    {"model": "gemini-2.0-flash",          "key_env": "GEMINI_API_KEY"},
#     "anthropic": {"model": "claude-haiku-4-5-20251001", "key_env": "ANTHROPIC_API_KEY"},
# }

# # ---------------------------------------------------------------------------
# # Embedding Provider
# # Must match what was used during embed.py indexing run.
# # ---------------------------------------------------------------------------
# ACTIVE_PROVIDER = os.getenv("ACTIVE_PROVIDER", "baai")

# # ---------------------------------------------------------------------------
# # Retrieval defaults
# # ---------------------------------------------------------------------------
# RETRIEVAL_K    = int(os.getenv("RETRIEVAL_K",    "20"))
# RERANK_TOP_N   = int(os.getenv("RERANK_TOP_N",   "5"))
# RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
# BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# # ---------------------------------------------------------------------------
# # Rate limiting (requests per minute per IP)
# # ---------------------------------------------------------------------------
# RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

# # ---------------------------------------------------------------------------
# # CORS — allowed origins for the web frontend
# # ---------------------------------------------------------------------------
# ALLOWED_ORIGINS = os.getenv(
#     "ALLOWED_ORIGINS",
#     "http://localhost:3000,http://localhost:5173,https://your-vercel-app.vercel.app"
# ).split(",")

# # ---------------------------------------------------------------------------
# # WhatsApp (Meta Cloud API)
# # ---------------------------------------------------------------------------
# WHATSAPP_VERIFY_TOKEN  = os.getenv("WHATSAPP_VERIFY_TOKEN",  "")
# WHATSAPP_ACCESS_TOKEN  = os.getenv("WHATSAPP_ACCESS_TOKEN",  "")
# WHATSAPP_PHONE_ID      = os.getenv("WHATSAPP_PHONE_ID",      "")
# WHATSAPP_API_VERSION   = os.getenv("WHATSAPP_API_VERSION",   "v19.0")

# =============================================================================
# backend/config.py
# Single source of truth for all backend configuration.
# All values can be overridden via environment variables.
# =============================================================================

import os
from pathlib import Path

from dotenv import load_dotenv
# load env variables
load_dotenv()

# ---------------------------------------------------------------------------
# Paths — backend sits one level below project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_DIR   = str(PROJECT_ROOT / "data" / "chromadb")
LOG_DIR      = str(PROJECT_ROOT / "logs")

# ---------------------------------------------------------------------------
# ISKCON Contact
# ---------------------------------------------------------------------------
ISKCON_NAME    = os.getenv("ISKCON_NAME",    "ISKCON Pune NVCC")
ISKCON_PHONE   = os.getenv("ISKCON_PHONE",   "+91-XXXXXXXXXX")
ISKCON_EMAIL   = os.getenv("ISKCON_EMAIL",   "nvcc@iskconpune.org")
ISKCON_WEBSITE = os.getenv("ISKCON_WEBSITE", "https://iskconpune.com")

# ---------------------------------------------------------------------------
# LLM Provider
# Change ACTIVE_LLM to switch provider. Options: groq | openai | gemini | anthropic
# ---------------------------------------------------------------------------
ACTIVE_LLM  = os.getenv("ACTIVE_LLM", "groq")
MAX_TOKENS  = int(os.getenv("MAX_TOKENS",  "700"))   # per-task budgets in core.py override this
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))

LLM_SPECS = {
    "groq":      {"model": "llama-3.3-70b-versatile",  "key_env": "GROQ_API_KEY"},
    "openai":    {"model": "gpt-4o-mini",               "key_env": "OPENAI_API_KEY"},
    "gemini":    {"model": "gemini-2.0-flash",          "key_env": "GEMINI_API_KEY"},
    "anthropic": {"model": "claude-haiku-4-5-20251001", "key_env": "ANTHROPIC_API_KEY"},
}

# ---------------------------------------------------------------------------
# Embedding Provider
# Must match what was used during embed.py indexing run.
# ---------------------------------------------------------------------------
ACTIVE_PROVIDER = os.getenv("ACTIVE_PROVIDER", "baai")

# ---------------------------------------------------------------------------
# Retrieval defaults
# RETRIEVAL_K: candidates fetched from vector DB before reranking.
#              Lower = faster, but misses some relevant passages.
# RERANK_TOP_N: how many to keep after reranking (fed to LLM).
#               Capped further in core.py for free-tier token budget.
# ---------------------------------------------------------------------------
RETRIEVAL_K    = int(os.getenv("RETRIEVAL_K",    "15"))   # was 20
RERANK_TOP_N   = int(os.getenv("RERANK_TOP_N",   "4"))    # was 5
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Hybrid retrieval tuning
# hybrid_score = (vector_weight * vector_norm) + (bm25_weight * bm25_norm)
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.65"))
HYBRID_BM25_WEIGHT   = float(os.getenv("HYBRID_BM25_WEIGHT",   "0.35"))

# MMR diversification tuning
# Higher lambda = more relevance, lower lambda = more diversity
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.75"))

# ---------------------------------------------------------------------------
# Rate limiting (requests per minute per IP)
# ---------------------------------------------------------------------------
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))

# ---------------------------------------------------------------------------
# CORS — allowed origins for the web frontend
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://your-vercel-app.vercel.app"
).split(",")

# ---------------------------------------------------------------------------
# WhatsApp (Meta Cloud API)
# ---------------------------------------------------------------------------
WHATSAPP_VERIFY_TOKEN  = os.getenv("WHATSAPP_VERIFY_TOKEN",  "")
WHATSAPP_ACCESS_TOKEN  = os.getenv("WHATSAPP_ACCESS_TOKEN",  "")
WHATSAPP_PHONE_ID      = os.getenv("WHATSAPP_PHONE_ID",      "")
WHATSAPP_API_VERSION   = os.getenv("WHATSAPP_API_VERSION",   "v19.0")