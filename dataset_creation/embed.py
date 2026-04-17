# =============================================================================
# embed.py
# Phase 3 — Generate embeddings and build the ChromaDB vector store.
#
# SWITCHING PROVIDERS — only ONE line to change:
#   At the top of this file, set ACTIVE_PROVIDER to one of:
#
#     "baai"   → BAAI/bge-large-en-v1.5  (free, local, no API key needed)
#     "gemini" → Google text-embedding-004 (free tier via AI Studio API key)
#     "openai" → text-embedding-3-small   (paid, ~$0.02 for entire corpus)
#
#   Then set the corresponding API key env variable if required:
#     Gemini : export GEMINI_API_KEY=...
#     OpenAI : export OPENAI_API_KEY=...
#     BAAI   : no key needed
#
# Run:
#   python embed.py                  # embed everything
#   python embed.py --reset          # wipe ChromaDB and rebuild from scratch
#   python embed.py --verify-only    # run a test query, skip embedding
# =============================================================================

import os
import json
import time
import logging
import argparse
from pathlib import Path

import chromadb

# =============================================================================
# ┌─────────────────────────────────────────────────────┐
# │              CHANGE ONLY THIS ONE LINE              │
# │   Options: "baai"  |  "gemini"  |  "openai"        │
ACTIVE_PROVIDER = "baai"
# └─────────────────────────────────────────────────────┘
# =============================================================================

# ---------------------------------------------------------------------------
# Provider specs — dimensions and display names
# ---------------------------------------------------------------------------
PROVIDER_SPECS = {
    "baai": {
        "name":       "BAAI/bge-large-en-v1.5",
        "dimensions": 1024,
        "requires_key": False,
        "key_env":    None,
    },
    "gemini": {
        "name":       "models/text-embedding-004",
        "dimensions": 768,
        "requires_key": True,
        "key_env":    "GEMINI_API_KEY",
    },
    "openai": {
        "name":       "text-embedding-3-small",
        "dimensions": 1536,
        "requires_key": True,
        "key_env":    "OPENAI_API_KEY",
    },
}

# ---------------------------------------------------------------------------
# Paths and settings
# ---------------------------------------------------------------------------
CHUNKS_FILE  = "data/chunks/all_chunks.json"
CHROMA_DIR   = "data/chromadb"
COLLECTION   = "prabhupada_rag"
LOG_DIR      = "logs"
BATCH_SIZE   = 100     # chunks per batch (all providers handle this fine)
RETRY_DELAY  = 10      # seconds to wait after a rate-limit error


# =============================================================================
# LOGGING
# =============================================================================

def setup_logger():
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/embed.log", encoding="utf-8"),
        ]
    )
    return logging.getLogger("embedder")


# =============================================================================
# PROVIDER IMPLEMENTATIONS
# Each returns a flat list[list[float]] in the same order as the input texts.
# =============================================================================

def embed_baai(texts: list[str], logger: logging.Logger) -> list[list[float]]:
    """
    BAAI/bge-large-en-v1.5 via sentence-transformers.
    Runs fully locally. No API key. First call downloads the model (~1.3 GB).

    Install: pip install sentence-transformers
    """
    from sentence_transformers import SentenceTransformer

    # Model is cached after first download — subsequent calls are instant
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")

    # BGE models perform better with this query prefix during encoding
    # For documents (not queries) the prefix is empty — correct here
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_gemini(texts: list[str], logger: logging.Logger) -> list[list[float]]:
    """
    Google text-embedding-004 via the Gemini API (free tier).
    Rate limit on free tier: 1,500 requests/minute — well within our needs.

    Install: pip install google-generativeai
    Set env: export GEMINI_API_KEY=your_key_from_aistudio.google.com
    """
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set.\n"
            "Get a free key at: https://aistudio.google.com/app/apikey\n"
            "Then run: export GEMINI_API_KEY=your_key"
        )
    genai.configure(api_key=api_key)

    vectors = []
    for attempt in range(3):
        try:
            # Gemini embedding API takes one text at a time or a batch
            # task_type RETRIEVAL_DOCUMENT is correct for indexing content
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=texts,
                task_type="retrieval_document",
            )
            vectors = result["embedding"] if len(texts) == 1 else [r for r in result["embedding"]]
            break
        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e) and attempt < 2:
                logger.warning(f"Rate limited. Waiting {RETRY_DELAY}s... (attempt {attempt + 1}/3)")
                time.sleep(RETRY_DELAY)
            else:
                raise

    # Gemini returns a single list for single input — normalise to list-of-lists
    if vectors and isinstance(vectors[0], float):
        vectors = [vectors]

    return vectors


def embed_openai(texts: list[str], logger: logging.Logger) -> list[list[float]]:
    """
    OpenAI text-embedding-3-small.
    Cost: ~$0.02 for the entire corpus (one-time).

    Install: pip install openai
    Set env: export OPENAI_API_KEY=sk-...
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set.\n"
            "Set it with: export OPENAI_API_KEY=sk-..."
        )

    client = OpenAI(api_key=api_key)

    for attempt in range(3):
        try:
            response = client.embeddings.create(
                input=texts,
                model="text-embedding-3-small",
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if "rate" in str(e).lower() and attempt < 2:
                logger.warning(f"Rate limited. Waiting {RETRY_DELAY}s... (attempt {attempt + 1}/3)")
                time.sleep(RETRY_DELAY)
            else:
                raise
    return []


# =============================================================================
# UNIFIED EMBED FUNCTION — calls the right provider
# =============================================================================

def embed_texts(texts: list[str], logger: logging.Logger) -> list[list[float]]:
    """Route to the active provider. Called for every batch."""
    if ACTIVE_PROVIDER == "baai":
        return embed_baai(texts, logger)
    elif ACTIVE_PROVIDER == "gemini":
        return embed_gemini(texts, logger)
    elif ACTIVE_PROVIDER == "openai":
        return embed_openai(texts, logger)
    else:
        raise ValueError(f"Unknown provider: '{ACTIVE_PROVIDER}'. Choose: baai | gemini | openai")


# =============================================================================
# CHROMADB
# =============================================================================

def get_collection(reset: bool = False) -> chromadb.Collection:
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if reset:
        try:
            client.delete_collection(COLLECTION)
            logging.getLogger("embedder").info("Existing collection deleted.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def build_metadata(chunk: dict) -> dict:
    """
    Flatten chunk fields into ChromaDB metadata.
    ChromaDB only accepts str, int, float, bool — no None or lists.
    """
    return {
        "reference":      chunk["reference"],
        "book":           chunk["book"],
        "book_code":      chunk["book_code"],
        "division_1":     chunk["division_1"] if chunk["division_1"] is not None else -1,
        "division_2":     str(chunk["division_2"]) if chunk["division_2"] is not None else "",
        "division_3":     str(chunk["division_3"]) if chunk["division_3"] is not None else "",
        "translation":    chunk["translation"],
        "purport":        chunk["purport"],
        "verse_sanskrit": chunk["verse_sanskrit"],
        "word_for_word":  chunk["word_for_word"],
        "part":           chunk["part"],
        "total_parts":    chunk["total_parts"],
        "provider":       ACTIVE_PROVIDER,   # record which model was used
    }


# =============================================================================
# MAIN EMBED FLOW
# =============================================================================

def embed_all(reset: bool, logger: logging.Logger):
    spec = PROVIDER_SPECS[ACTIVE_PROVIDER]

    logger.info("=" * 55)
    logger.info(f"Provider   : {ACTIVE_PROVIDER.upper()}  ({spec['name']})")
    logger.info(f"Dimensions : {spec['dimensions']}")
    logger.info("=" * 55)

    # Load chunks
    if not os.path.exists(CHUNKS_FILE):
        logger.error(f"Chunks file not found: {CHUNKS_FILE} — run chunk.py first")
        return

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)
    logger.info(f"Loaded {len(chunks)} chunks")

    # ChromaDB collection
    collection   = get_collection(reset=reset)
    existing_ids = set(collection.get(include=[])["ids"])
    logger.info(f"Existing vectors in DB: {len(existing_ids)}")

    # Filter already-embedded chunks (resume support)
    to_embed = [c for c in chunks if c["chunk_id"] not in existing_ids]

    if not to_embed:
        logger.info("All chunks already embedded. Use --reset to rebuild.")
        return

    logger.info(f"Chunks to embed: {len(to_embed)}  (skipping {len(existing_ids)} cached)")
    logger.info("")

    # Embed in batches
    total_batches = (len(to_embed) + BATCH_SIZE - 1) // BATCH_SIZE
    embedded = 0

    for batch_num, i in enumerate(range(0, len(to_embed), BATCH_SIZE), start=1):
        batch  = to_embed[i: i + BATCH_SIZE]
        texts  = [c["chunk_text"] for c in batch]
        ids    = [c["chunk_id"]   for c in batch]
        metas  = [build_metadata(c) for c in batch]

        logger.info(f"Batch {batch_num}/{total_batches}: {len(batch)} chunks...")

        vectors = embed_texts(texts, logger)

        if len(vectors) != len(batch):
            logger.error(f"Vector count mismatch in batch {batch_num} — skipping.")
            continue

        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metas,
        )

        embedded += len(batch)
        logger.info(f"  ✓ {embedded}/{len(to_embed)} stored")

    logger.info("")
    logger.info("=" * 55)
    logger.info("EMBEDDING COMPLETE")
    logger.info(f"  Embedded   : {embedded}")
    logger.info(f"  Total in DB: {collection.count()}")
    logger.info(f"  DB path    : {CHROMA_DIR}")
    logger.info("=" * 55)


# =============================================================================
# VERIFY: test query against the index
# =============================================================================

def verify_index(logger: logging.Logger):
    collection = get_collection(reset=False)

    if collection.count() == 0:
        logger.warning("Collection is empty — nothing to verify.")
        return

    test_query = "What is the nature of the eternal soul?"
    logger.info(f"\nVerification query: '{test_query}'")

    [query_vector] = embed_texts([test_query], logger)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=3,
        include=["metadatas", "distances"],
    )

    print(f"\n--- Top 3 results ---")
    for i, (meta, dist) in enumerate(
        zip(results["metadatas"][0], results["distances"][0]), start=1
    ):
        score = 1 - dist
        print(f"\n  [{i}] {meta['reference']}  (similarity: {score:.3f})")
        print(f"      {meta['translation'][:120]}...")
    print()


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Embed chunks into ChromaDB")
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe the ChromaDB collection and rebuild from scratch"
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Run a test query only — skip embedding"
    )
    args = parser.parse_args()

    logger = setup_logger()

    if args.verify_only:
        verify_index(logger)
        return

    embed_all(reset=args.reset, logger=logger)
    verify_index(logger)


if __name__ == "__main__":
    main()
