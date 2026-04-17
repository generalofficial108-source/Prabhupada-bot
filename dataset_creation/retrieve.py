# =============================================================================
# retrieve.py
# Retrieval engine with direct reference lookup bypass.
#
# TWO RETRIEVAL MODES:
#
#   1. DIRECT LOOKUP — triggered when the query contains an explicit verse
#      reference like "BG 3.9", "NOI 2", "ISO 5", "BS 5.29".
#      Bypasses vector search entirely. Fetches the exact verse(s) from
#      ChromaDB by reference ID. This is why "give me BG 3.9" failed before
#      — semantic search cannot handle exact reference lookups.
#
#   2. SEMANTIC SEARCH — for all other natural language questions.
#      Embeds the query → vector search (top-K) → cross-encoder reranking.
# =============================================================================

import os
import re
import sys
import logging
from dataclasses import dataclass

import chromadb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import ACTIVE_PROVIDER, embed_texts

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHROMA_DIR       = "data/chromadb"
COLLECTION       = "prabhupada_rag"
RETRIEVAL_K      = 20
RERANK_TOP_N     = 5
RERANKER_MODEL   = "cross-encoder/ms-marco-MiniLM-L-6-v2"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

logger = logging.getLogger("retriever")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    chunk_id:        str
    reference:       str
    book:            str
    book_code:       str
    translation:     str
    purport:         str
    verse_sanskrit:  str
    word_for_word:   str
    part:            int
    total_parts:     int
    vector_score:    float
    rerank_score:    float
    chunk_text:      str
    direct_lookup:   bool = False   # True when fetched by exact reference


# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

_collection = None

def get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_collection(name=COLLECTION)
    return _collection


# =============================================================================
# DIRECT REFERENCE LOOKUP
# =============================================================================

# Patterns that detect an explicit verse reference in the query.
# Covers formats like: BG 3.9, bg3.9, Bg. 3.9, NOI 2, ISO 5, BS 5.29
# Also handles ranges: BG 1.16-18

REFERENCE_PATTERNS = [
    # BG chapter.verse  e.g. BG 3.9 / BG3.9 / bg 3.9
    (r'\bbg\.?\s*(\d+)\.(\d+(?:-\d+)?)\b', "bg"),
    # NOI verse  e.g. NOI 3 / noi3
    (r'\bnoi\.?\s*(\d+)\b', "noi"),
    # ISO / Isopanishad mantra  e.g. ISO 5 / iso5
    (r'\biso\.?\s*(\d+)\b', "iso"),
    # BS chapter.verse  e.g. BS 5.29 / bs 5.29
    (r'\bbs\.?\s*5\.(\d+)\b', "bs"),
]


def detect_reference(query: str) -> list[dict] | None:
    """
    Scan the query for explicit verse references.
    Returns a list of {book_code, d1, d2} dicts if found, else None.

    Handles multiple references in one query:
      "compare BG 2.47 and BG 3.9" → two entries
    """
    found = []
    q = query.lower()

    for pattern, book_code in REFERENCE_PATTERNS:
        for match in re.finditer(pattern, q, re.IGNORECASE):
            if book_code == "bg":
                d1 = int(match.group(1))
                d2 = match.group(2)          # may be "16-18"
                found.append({"book_code": book_code, "d1": d1, "d2": d2})
            elif book_code == "bs":
                d1 = int(match.group(1))     # verse within chapter 5
                found.append({"book_code": book_code, "d1": d1, "d2": None})
            else:
                d1 = int(match.group(1))
                found.append({"book_code": book_code, "d1": d1, "d2": None})

    return found if found else None


def build_chunk_id(book_code: str, d1: int, d2) -> str:
    """Reconstruct the chunk_id used during indexing."""
    if d2 is not None:
        return f"{book_code}_{d1}_{d2}"
    return f"{book_code}_{d1}"


def direct_lookup(refs: list[dict]) -> list[RetrievalResult]:
    """
    Fetch specific verses from ChromaDB by their chunk_id.
    Returns RetrievalResult objects with direct_lookup=True.
    """
    collection = get_collection()
    results    = []

    for ref in refs:
        chunk_id = build_chunk_id(ref["book_code"], ref["d1"], ref["d2"])
        logger.info(f"Direct lookup: {chunk_id}")

        try:
            response = collection.get(
                ids=[chunk_id],
                include=["metadatas", "documents"],
            )
        except Exception as e:
            logger.warning(f"Direct lookup failed for {chunk_id}: {e}")
            continue

        if not response["ids"]:
            # Try without d2 in case it was stored differently
            logger.warning(f"chunk_id '{chunk_id}' not found in DB")
            continue

        meta = response["metadatas"][0]
        doc  = response["documents"][0]

        results.append(RetrievalResult(
            chunk_id       = chunk_id,
            reference      = meta["reference"],
            book           = meta["book"],
            book_code      = meta["book_code"],
            translation    = meta["translation"],
            purport        = meta["purport"],
            verse_sanskrit = meta.get("verse_sanskrit", ""),
            word_for_word  = meta.get("word_for_word", ""),
            part           = meta.get("part", 1),
            total_parts    = meta.get("total_parts", 1),
            vector_score   = 1.0,    # exact match
            rerank_score   = 10.0,   # highest priority
            chunk_text     = doc,
            direct_lookup  = True,
        ))

    return results


# =============================================================================
# SEMANTIC SEARCH
# =============================================================================

def embed_query(query: str) -> list[float]:
    if ACTIVE_PROVIDER == "baai":
        prefixed = BGE_QUERY_PREFIX + query
        [vector] = embed_texts([prefixed], logger)
    else:
        [vector] = embed_texts([query], logger)
    return vector


def vector_search(
    query_vector: list[float],
    k: int = RETRIEVAL_K,
    book_filter: list[str] | None = None,
) -> list[dict]:
    collection = get_collection()

    where = None
    if book_filter and len(book_filter) == 1:
        where = {"book_code": {"$eq": book_filter[0]}}
    elif book_filter and len(book_filter) > 1:
        where = {"book_code": {"$in": book_filter}}

    query_kwargs = {
        "query_embeddings": [query_vector],
        "n_results":        min(k, collection.count()),
        "include":          ["metadatas", "documents", "distances"],
    }
    if where:
        query_kwargs["where"] = where

    raw = collection.query(**query_kwargs)

    candidates = []
    for meta, doc, dist in zip(
        raw["metadatas"][0],
        raw["documents"][0],
        raw["distances"][0],
    ):
        candidates.append({
            "metadata":     meta,
            "chunk_text":   doc,
            "vector_score": round(1 - dist, 4),
        })
    return candidates


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker: {RERANKER_MODEL}")
            _reranker = CrossEncoder(RERANKER_MODEL)
            logger.info("Reranker loaded.")
        except ImportError:
            logger.warning("sentence-transformers not installed — reranking disabled.")
    return _reranker


def rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    reranker = get_reranker()

    if reranker is None:
        for c in candidates:
            c["rerank_score"] = c["vector_score"]
        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_n]

    pairs  = [(query, c["chunk_text"]) for c in candidates]
    scores = reranker.predict(pairs)

    for c, score in zip(candidates, scores):
        c["rerank_score"] = round(float(score), 4)

    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_n]


def _candidates_to_results(candidates: list[dict]) -> list[RetrievalResult]:
    results = []
    for c in candidates:
        meta = c["metadata"]
        results.append(RetrievalResult(
            chunk_id       = meta.get("chunk_id", ""),
            reference      = meta["reference"],
            book           = meta["book"],
            book_code      = meta["book_code"],
            translation    = meta["translation"],
            purport        = meta["purport"],
            verse_sanskrit = meta.get("verse_sanskrit", ""),
            word_for_word  = meta.get("word_for_word", ""),
            part           = meta.get("part", 1),
            total_parts    = meta.get("total_parts", 1),
            vector_score   = c["vector_score"],
            rerank_score   = c["rerank_score"],
            chunk_text     = c["chunk_text"],
            direct_lookup  = False,
        ))
    return results


# =============================================================================
# PUBLIC API
# =============================================================================

def retrieve(
    query:       str,
    top_n:       int = RERANK_TOP_N,
    k:           int = RETRIEVAL_K,
    book_filter: list[str] | None = None,
) -> list[RetrievalResult]:
    """
    Unified retrieval: auto-detects direct reference queries and handles
    them with exact lookup; falls back to semantic search for everything else.
    """
    # --- Check for explicit verse references first ---
    refs = detect_reference(query)

    if refs:
        logger.info(f"Reference detected: {refs} — using direct lookup")
        direct_results = direct_lookup(refs)

        if direct_results:
            return direct_results
        else:
            logger.warning("Direct lookup found nothing — falling back to semantic search")
            # Fall through to semantic search below

    # --- Semantic search ---
    logger.info("Semantic search mode")
    query_vector = embed_query(query)
    candidates   = vector_search(query_vector, k=k, book_filter=book_filter)

    if not candidates:
        logger.warning("No candidates from vector search.")
        return []

    reranked = rerank(query, candidates, top_n=top_n)
    return _candidates_to_results(reranked)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?",
                        default="What is the nature of the eternal soul?")
    parser.add_argument("--top-n",  type=int, default=RERANK_TOP_N)
    parser.add_argument("--k",      type=int, default=RETRIEVAL_K)
    parser.add_argument("--books",  nargs="+", choices=["bg","iso","noi","bs"])
    args = parser.parse_args()

    results = retrieve(query=args.query, top_n=args.top_n, k=args.k,
                       book_filter=args.books)

    print(f"\n{'='*60}\nQuery: {args.query}\n{'='*60}")
    for i, r in enumerate(results, 1):
        mode = "[DIRECT]" if r.direct_lookup else f"[v:{r.vector_score:.2f} r:{r.rerank_score:.2f}]"
        print(f"\n[{i}] {r.reference} {mode}")
        print(f"    {r.translation[:180]}")