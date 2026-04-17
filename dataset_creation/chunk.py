# =============================================================================
# chunk.py
# Phase 2, Step 2 — Build embedding chunks from cleaned records.
#
# CHUNKING STRATEGY:
#   Each verse/mantra becomes exactly one chunk. The chunk text contains the
#   reference, translation, and purport — the three fields that carry
#   semantic meaning for retrieval.
#
#   verse_sanskrit and word_for_word are excluded from the chunk text because:
#     - Sanskrit IAST text adds noise to English semantic search
#     - Word-for-word is technical linguistic content, not doctrinal prose
#   Both fields are still stored in the chunk metadata for display in the UI.
#
#   LONG PURPORT HANDLING:
#   Some Gita purports exceed 3,000 words. We embed the full purport as one
#   chunk (modern embedding models handle up to 8,192 tokens). If a purport
#   exceeds MAX_CHUNK_TOKENS, it is split into overlapping sub-chunks, each
#   tagged with a part number. This is rare — only ~15 BG purports need it.
#
# OUTPUT FORMAT (data/chunks/all_chunks.json):
#   [
#     {
#       "chunk_id":    "bg_2_47",          # unique ID
#       "reference":   "BG 2.47",          # human-readable citation
#       "book":        "Bhagavad Gita As It Is",
#       "book_code":   "bg",
#       "division_1":  2,
#       "division_2":  "47",
#       "chunk_text":  "...",              # text sent to the embedder
#       "translation": "...",             # stored for display
#       "purport":     "...",             # stored for display
#       "verse_sanskrit": "...",          # stored for display
#       "word_for_word":  "...",          # stored for display
#       "part":        1,                 # 1 for most; 1,2,3... for split chunks
#       "total_parts": 1,
#     },
#     ...
#   ]
#
# Run:
#   python chunk.py
#   python chunk.py --books bg iso
#   python chunk.py --max-tokens 512   # adjust split threshold
# =============================================================================

import os
import re
import json
import argparse
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CLEANED_DIR = "data/cleaned"
CHUNKS_DIR  = "data/chunks"
LOG_DIR     = "logs"

BOOKS = {
    "bg":  "Bhagavad Gita As It Is",
    "iso": "Sri Isopanishad",
    "noi": "Nectar of Instruction",
    "bs":  "Brahma Samhita",
}

# Approximate token limit per chunk.
# text-embedding-3-small supports 8,191 tokens.
# We use a conservative limit to leave headroom.
# At ~1.3 tokens/word, 1,500 tokens ≈ ~1,150 words of purport text.
# Most purports are under this. Those over it get split.
MAX_CHUNK_TOKENS = 1500

# Overlap in words between sub-chunks when splitting long purports.
# Overlap preserves context across chunk boundaries.
OVERLAP_WORDS = 80


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger():
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{LOG_DIR}/chunk.log", encoding="utf-8"),
        ]
    )
    return logging.getLogger("chunker")


# ---------------------------------------------------------------------------
# Token estimation
# Exact tokenisation requires the tiktoken library (optional dependency).
# We use a word-based approximation that is accurate to within ~10%.
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count. ~1.3 tokens per word for English prose."""
    word_count = len(text.split())
    return int(word_count * 1.3)


# ---------------------------------------------------------------------------
# Chunk text builder
# ---------------------------------------------------------------------------

def build_chunk_text(reference: str, translation: str, purport: str) -> str:
    """
    Build the text string that will be embedded.

    Format:
        Reference: BG 2.47
        Translation: You have a right to perform...
        Purport: Every man is in difficulty...
    """
    parts = [f"Reference: {reference}"]

    if translation.strip():
        parts.append(f"Translation: {translation.strip()}")

    if purport.strip():
        parts.append(f"Purport: {purport.strip()}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Long purport splitter
# ---------------------------------------------------------------------------

def split_purport_into_parts(purport: str, max_tokens: int, overlap_words: int) -> list[str]:
    """
    Split a long purport into overlapping parts.

    Splitting strategy:
      1. Try to split on paragraph boundaries (double newlines) first.
         This keeps Prabhupada's natural thought units intact.
      2. If a single paragraph still exceeds the limit, fall back to
         word-level splitting with overlap.

    Returns a list of purport text parts.
    """
    # Try paragraph-level splitting first
    paragraphs = [p.strip() for p in purport.split('\n\n') if p.strip()]

    parts    = []
    current  = []
    cur_toks = 0

    for para in paragraphs:
        para_toks = estimate_tokens(para)

        if cur_toks + para_toks > max_tokens and current:
            parts.append('\n\n'.join(current))
            # Overlap: carry the last paragraph into the next part
            current  = current[-1:] if overlap_words > 0 else []
            cur_toks = estimate_tokens('\n\n'.join(current))

        current.append(para)
        cur_toks += para_toks

    if current:
        parts.append('\n\n'.join(current))

    # Edge case: a single paragraph exceeded the limit
    # Fall back to word-level splitting
    final_parts = []
    for part in parts:
        if estimate_tokens(part) <= max_tokens:
            final_parts.append(part)
        else:
            words      = part.split()
            chunk_size = int(max_tokens / 1.3)  # words per chunk
            i = 0
            while i < len(words):
                chunk_words = words[i: i + chunk_size]
                final_parts.append(' '.join(chunk_words))
                i += chunk_size - overlap_words

    return final_parts if final_parts else [purport]


# ---------------------------------------------------------------------------
# Single record → one or more chunks
# ---------------------------------------------------------------------------

def record_to_chunks(record: dict, max_tokens: int, overlap_words: int, logger: logging.Logger) -> list[dict]:
    """
    Convert one cleaned record into one or more chunk dicts.

    Most records produce exactly one chunk.
    Records with very long purports produce multiple chunks (rare).
    """
    reference   = record["reference"]
    translation = record.get("translation", "")
    purport     = record.get("purport", "")

    # Estimate full chunk size
    full_text   = build_chunk_text(reference, translation, purport)
    full_tokens = estimate_tokens(full_text)

    # --- Single chunk (the common case) ---
    if full_tokens <= max_tokens:
        return [{
            "chunk_id":       record["id"],
            "reference":      reference,
            "book":           record["book"],
            "book_code":      record["book_code"],
            "division_1":     record["division_1"],
            "division_2":     record["division_2"],
            "division_3":     record["division_3"],
            "chunk_text":     full_text,
            "translation":    translation,
            "purport":        purport,
            "verse_sanskrit": record.get("verse_sanskrit", ""),
            "word_for_word":  record.get("word_for_word", ""),
            "part":           1,
            "total_parts":    1,
        }]

    # --- Multi-chunk: split the purport ---
    logger.info(
        f"  Long purport: {reference} ({full_tokens} est. tokens) — splitting..."
    )

    purport_parts = split_purport_into_parts(purport, max_tokens, overlap_words)
    total_parts   = len(purport_parts)

    chunks = []
    for i, purport_part in enumerate(purport_parts, start=1):
        chunk_text = build_chunk_text(reference, translation, purport_part)
        chunk_id   = f"{record['id']}_part{i}" if total_parts > 1 else record["id"]

        chunks.append({
            "chunk_id":       chunk_id,
            "reference":      reference,
            "book":           record["book"],
            "book_code":      record["book_code"],
            "division_1":     record["division_1"],
            "division_2":     record["division_2"],
            "division_3":     record["division_3"],
            "chunk_text":     chunk_text,
            "translation":    translation,
            "purport":        purport_part,
            "verse_sanskrit": record.get("verse_sanskrit", ""),
            "word_for_word":  record.get("word_for_word", ""),
            "part":           i,
            "total_parts":    total_parts,
        })

    logger.info(f"    → {total_parts} chunks produced")
    return chunks


# ---------------------------------------------------------------------------
# Main chunking function
# ---------------------------------------------------------------------------

def chunk_book(book_code: str, max_tokens: int, overlap_words: int, logger: logging.Logger) -> list[dict]:
    """Load cleaned records for one book and produce chunks."""
    input_path = os.path.join(CLEANED_DIR, f"{book_code}_clean.json")

    if not os.path.exists(input_path):
        logger.error(f"Cleaned file not found: {input_path} — run clean.py first")
        return []

    with open(input_path, encoding="utf-8") as f:
        records = json.load(f)

    logger.info(f"{'='*55}")
    logger.info(f"{BOOKS[book_code]}  ({len(records)} records)")
    logger.info(f"{'='*55}")

    all_chunks   = []
    split_count  = 0

    for record in records:
        chunks = record_to_chunks(record, max_tokens, overlap_words, logger)
        all_chunks.extend(chunks)
        if len(chunks) > 1:
            split_count += 1

    logger.info(f"  Records processed : {len(records)}")
    logger.info(f"  Chunks produced   : {len(all_chunks)}")
    logger.info(f"  Records split     : {split_count}")
    logger.info("")

    return all_chunks


# ---------------------------------------------------------------------------
# Token stats report
# ---------------------------------------------------------------------------

def print_token_stats(all_chunks: list[dict]):
    """Print token length distribution across all chunks."""
    token_counts = [estimate_tokens(c["chunk_text"]) for c in all_chunks]

    if not token_counts:
        return

    token_counts.sort()
    n      = len(token_counts)
    total  = sum(token_counts)

    print(f"\n{'='*45}")
    print(f"Chunk token statistics ({n} total chunks)")
    print(f"{'='*45}")
    print(f"  Min     : {token_counts[0]}")
    print(f"  Max     : {token_counts[-1]}")
    print(f"  Mean    : {total // n}")
    print(f"  Median  : {token_counts[n // 2]}")
    print(f"  p95     : {token_counts[int(n * 0.95)]}")
    print(f"  p99     : {token_counts[int(n * 0.99)]}")

    # Distribution buckets
    buckets = [(0, 200), (200, 500), (500, 1000), (1000, 1500), (1500, 99999)]
    print(f"\n  Distribution:")
    for lo, hi in buckets:
        count = sum(1 for t in token_counts if lo <= t < hi)
        label = f"{lo}–{hi}" if hi < 99999 else f"{lo}+"
        bar   = "█" * (count * 30 // n)
        print(f"    {label:>10} tokens : {count:>4} chunks  {bar}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build embedding chunks from cleaned JSON")
    parser.add_argument(
        "--books", nargs="+",
        choices=list(BOOKS.keys()) + ["all"],
        default=["all"],
    )
    parser.add_argument(
        "--max-tokens", type=int, default=MAX_CHUNK_TOKENS,
        help=f"Max tokens per chunk before splitting (default: {MAX_CHUNK_TOKENS})"
    )
    parser.add_argument(
        "--overlap-words", type=int, default=OVERLAP_WORDS,
        help=f"Word overlap between split chunks (default: {OVERLAP_WORDS})"
    )
    args = parser.parse_args()

    logger = setup_logger()
    Path(CHUNKS_DIR).mkdir(parents=True, exist_ok=True)

    books_to_chunk = list(BOOKS.keys()) if "all" in args.books else args.books

    all_chunks = []
    for book_code in books_to_chunk:
        chunks = chunk_book(book_code, args.max_tokens, args.overlap_words, logger)
        all_chunks.extend(chunks)

    # Save combined chunk file (used by the embedder in Phase 3)
    output_path = os.path.join(CHUNKS_DIR, "all_chunks.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(all_chunks)} total chunks → {output_path}")

    # Also save per-book chunk files for debugging
    for book_code in books_to_chunk:
        book_chunks = [c for c in all_chunks if c["book_code"] == book_code]
        per_book_path = os.path.join(CHUNKS_DIR, f"{book_code}_chunks.json")
        with open(per_book_path, "w", encoding="utf-8") as f:
            json.dump(book_chunks, f, ensure_ascii=False, indent=2)

    print_token_stats(all_chunks)

    logger.info("=" * 55)
    logger.info("CHUNKING COMPLETE")
    logger.info(f"  Total chunks : {len(all_chunks)}")
    logger.info(f"  Output       : {output_path}")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
