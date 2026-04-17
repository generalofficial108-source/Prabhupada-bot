# =============================================================================
# clean.py
# Phase 2, Step 1 — Data cleaning and validation.
#
# What this does:
#   1. Loads raw JSON for each book from data/scraped/*_raw.json
#   2. Removes the scraper-internal 'scrape_ok' field
#   3. Normalises all text fields (whitespace, encoding artifacts)
#   4. Validates every record — logs warnings for missing fields
#   5. Writes cleaned output to data/cleaned/*_clean.json
#
# Run:
#   python clean.py                  # clean all four books
#   python clean.py --books bg iso   # clean specific books
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

SCRAPED_DIR = "data/scraped"
CLEANED_DIR = "data/cleaned"
LOG_DIR     = "logs"

BOOKS = {
    "bg":  "Bhagavad Gita As It Is",
    "iso": "Sri Isopanishad",
    "noi": "Nectar of Instruction",
    "bs":  "Brahma Samhita",
}

# Fields that must be present and non-empty for a record to be considered valid.
# verse_sanskrit and word_for_word are NOT required (a few verses have none).
REQUIRED_FIELDS = ["translation", "purport"]

# All text fields that get cleaning applied
TEXT_FIELDS = ["verse_sanskrit", "word_for_word", "translation", "purport"]


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
            logging.FileHandler(f"{LOG_DIR}/clean.log", encoding="utf-8"),
        ]
    )
    return logging.getLogger("cleaner")


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalise_text(text: str) -> str:
    """
    Clean a single text field:
      - Strip leading/trailing whitespace
      - Collapse multiple spaces and tabs into one space
      - Collapse 3+ consecutive newlines into two (preserve paragraph breaks)
      - Remove zero-width and other invisible Unicode characters
      - Normalise fancy quotes to straight equivalents (optional — commented out;
        enable if downstream embedding tokeniser handles them poorly)
    """
    if not text:
        return ""

    # Remove zero-width spaces and other invisible characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u00ad]', '', text)

    # Collapse horizontal whitespace
    text = re.sub(r'[ \t]+', ' ', text)

    # Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def clean_record(record: dict) -> dict:
    """
    Return a new cleaned record dict:
      - 'scrape_ok' field removed
      - All text fields normalised
      - Null text fields converted to empty string
    """
    cleaned = {}

    for key, value in record.items():
        # Drop the scraper-internal flag — it has no place in the dataset
        if key == "scrape_ok":
            continue

        if key in TEXT_FIELDS:
            cleaned[key] = normalise_text(value or "")
        else:
            cleaned[key] = value

    return cleaned


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_record(record: dict, logger: logging.Logger) -> bool:
    """
    Check a cleaned record for required content.
    Logs a warning for each issue found.
    Returns True if the record is fully valid.
    """
    ref = record.get("reference", record.get("id", "unknown"))
    valid = True

    for field in REQUIRED_FIELDS:
        if not record.get(field, "").strip():
            logger.warning(f"  [{ref}] Missing required field: '{field}'")
            valid = False

    # Sanity check: translation should not be suspiciously short
    translation = record.get("translation", "")
    if translation and len(translation) < 20:
        logger.warning(f"  [{ref}] Translation suspiciously short ({len(translation)} chars): {translation!r}")

    return valid


# ---------------------------------------------------------------------------
# Main clean function
# ---------------------------------------------------------------------------

def clean_book(book_code: str, logger: logging.Logger) -> list[dict]:
    """
    Load, clean, and validate all records for one book.
    Returns the list of cleaned records.
    """
    input_path  = os.path.join(SCRAPED_DIR, f"{book_code}_raw.json")
    output_path = os.path.join(CLEANED_DIR, f"{book_code}_clean.json")

    if not os.path.exists(input_path):
        logger.error(f"Raw file not found: {input_path}")
        return []

    with open(input_path, encoding="utf-8") as f:
        raw_records = json.load(f)

    logger.info(f"{'='*55}")
    logger.info(f"{BOOKS[book_code]}  ({len(raw_records)} raw records)")
    logger.info(f"{'='*55}")

    cleaned_records = []
    invalid_count   = 0

    for record in raw_records:
        cleaned  = clean_record(record)
        is_valid = validate_record(cleaned, logger)

        if not is_valid:
            invalid_count += 1

        # We keep ALL records even if invalid — just log the warning.
        # Dropping records would silently create gaps in the dataset.
        cleaned_records.append(cleaned)

    # Write cleaned output
    Path(CLEANED_DIR).mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_records, f, ensure_ascii=False, indent=2)

    logger.info(f"  Total records   : {len(cleaned_records)}")
    logger.info(f"  Invalid records : {invalid_count}  (kept with warnings)")
    logger.info(f"  Output          : {output_path}")
    logger.info("")

    return cleaned_records


def print_sample(records: list[dict], book_code: str):
    """Print a sample record to visually confirm cleaning."""
    if not records:
        return
    r = records[0]
    print(f"\n--- Sample: {r['reference']} ---")
    for field in ["verse_sanskrit", "word_for_word", "translation", "purport"]:
        val = r.get(field, "")
        preview = val[:120].replace('\n', ' ') + ("..." if len(val) > 120 else "")
        print(f"  {field:<20}: {preview}")

    # Confirm scrape_ok is gone
    if "scrape_ok" in r:
        print("  ⚠ WARNING: scrape_ok field still present!")
    else:
        print("  ✓ scrape_ok field removed")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Clean raw scraped JSON files")
    parser.add_argument(
        "--books", nargs="+",
        choices=list(BOOKS.keys()) + ["all"],
        default=["all"],
    )
    args = parser.parse_args()

    logger = setup_logger()
    books_to_clean = list(BOOKS.keys()) if "all" in args.books else args.books

    all_counts = {}
    for book_code in books_to_clean:
        records = clean_book(book_code, logger)
        all_counts[book_code] = len(records)
        print_sample(records, book_code)

    logger.info("=" * 55)
    logger.info("CLEANING COMPLETE")
    for book_code, count in all_counts.items():
        logger.info(f"  {BOOKS[book_code]:<35} {count} records")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
