# =============================================================================
# parser.py
# Parse a Vedabase.io verse page HTML into a clean structured dictionary.
#
# HOW VEDABASE PAGES ARE STRUCTURED:
#   Vedabase renders pages server-side. Each verse page has four main
#   content sections, each in a <div> with a specific CSS class.
#
#   Sanskrit / verse text : div.av-verse_text  (Roman IAST transliteration)
#   Word-for-word         : div.av-synonyms    (word; meaning pairs)
#   Translation           : div.av-translation (English translation)
#   Purport               : div.av-purport     (Prabhupada's commentary)
#
#   Vedabase uses an "av-" prefix (advanced viewer). If the site changes,
#   only update SELECTORS below — nothing else.
# =============================================================================

import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger("vedabase_scraper")


# ---------------------------------------------------------------------------
# CSS selector candidates — tried in order, first match wins.
# ---------------------------------------------------------------------------

SELECTORS = {
    "verse_sanskrit": [
        "div.av-verse_text",
        "div.av-devanagari",
        "[class*='verse_text']",
        "[class*='verse-text']",
    ],
    "word_for_word": [
        "div.av-synonyms",
        "div.r-synonyms",
        "[class*='synonyms']",
    ],
    "translation": [
        "div.av-translation",
        "div.r-translation",
        "[class*='translation']",
    ],
    "purport": [
        "div.av-purport",
        "div.r-purport",
        "[class*='purport']",
    ],
}


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Normalize whitespace. Preserves paragraph breaks as double newlines."""
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_leading_label(text: str, label: str) -> str:
    """
    Strip a leading section label injected by Vedabase into the element text.
    e.g. "Translation You have a right..." → "You have a right..."
    Case-insensitive. Only removes if the label is literally first.
    """
    if not text:
        return ""
    if text.lower().startswith(label.lower()):
        return text[len(label):].strip()
    return text


def extract_paragraphs(tag) -> str:
    """
    Extract text from a tag's <p> children joined by double newlines.
    Falls back to raw .get_text() when no <p> tags are present.
    """
    if tag is None:
        return ""
    paras = tag.find_all("p")
    if paras:
        return "\n\n".join(p.get_text(separator=" ", strip=True) for p in paras)
    return tag.get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

def find_section(soup: BeautifulSoup, field: str) -> str:
    """
    Try each CSS selector for a field; return cleaned text of the first match.
    """
    for selector in SELECTORS[field]:
        try:
            tag = soup.select_one(selector)
            if tag:
                if field == "purport":
                    return clean_text(extract_paragraphs(tag))
                else:
                    return clean_text(tag.get_text(separator=" ", strip=True))
        except Exception as e:
            logger.debug(f"Selector '{selector}' for '{field}' raised: {e}")
    return ""


# ---------------------------------------------------------------------------
# Reference and ID building
# ---------------------------------------------------------------------------

def build_reference(book_code: str, d1: int, d2) -> str:
    """
    Build a human-readable reference string for any book.

    d2 can be:
      - An integer (single BG verse):        "BG 2.47"
      - A string like "16-18" (grouped BG):  "BG 1.16-18"
      - None (ISO, NOI):                     "ISO 1" / "NOI 3"

    Uses the config's reference_fn where possible; handles grouped
    BG verses (string d2) explicitly.
    """
    from scraper.config import BOOKS
    cfg = BOOKS[book_code]

    if book_code == "bg":
        # d2 is either an int or a string like "16-18"
        return f"BG {d1}.{d2}"
    else:
        # ISO and NOI — d2 is always None
        return cfg["reference_fn"](d1)


def build_id(book_code: str, d1: int, d2) -> str:
    """
    Build a unique record ID string.

    Examples:
      bg  d1=2  d2=47       → "bg_2_47"
      bg  d1=1  d2="16-18"  → "bg_1_16-18"
      iso d1=1  d2=None     → "iso_1"
    """
    if d2 is not None:
        return f"{book_code}_{d1}_{d2}"
    return f"{book_code}_{d1}"


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_verse_page(html: str, book_code: str, d1: int, d2=None) -> dict:
    """
    Parse raw HTML of a Vedabase verse page into a structured dict.

    Args:
        html:       Raw HTML string of the page.
        book_code:  'bg', 'iso', or 'noi'.
        d1:         Division 1 — chapter (BG) or mantra/verse number (ISO/NOI).
        d2:         Division 2 — verse number or range string (BG only), else None.

    Returns:
        Dict with all fields. 'scrape_ok' is True when translation was found.
    """
    from scraper.config import BOOKS
    soup = BeautifulSoup(html, "lxml")

    verse_sanskrit = find_section(soup, "verse_sanskrit")
    word_for_word  = find_section(soup, "word_for_word")
    translation    = find_section(soup, "translation")
    purport        = find_section(soup, "purport")

    # Strip section labels Vedabase injects into element text
    verse_sanskrit = remove_leading_label(verse_sanskrit, "Devanagari")
    verse_sanskrit = remove_leading_label(verse_sanskrit, "Verse text")
    word_for_word  = remove_leading_label(word_for_word, "Synonyms")
    translation    = remove_leading_label(translation,   "Translation")
    purport        = remove_leading_label(purport,       "Purport")

    scrape_ok = bool(translation)

    if not scrape_ok:
        logger.warning(
            f"[{book_code}] d1={d1} d2={d2} — translation not found. "
            "Check selectors or consider Playwright fallback."
        )

    cfg       = BOOKS[book_code]
    reference = build_reference(book_code, d1, d2)
    record_id = build_id(book_code, d1, d2)

    return {
        "id":             record_id,
        "book":           cfg["name"],
        "book_code":      book_code,
        "division_1":     d1,
        "division_2":     d2,      # int, "16-18" string, or None
        "division_3":     None,    # reserved for future books
        "reference":      reference,
        "verse_sanskrit": verse_sanskrit,
        "word_for_word":  word_for_word,
        "translation":    translation,
        "purport":        purport,
        "scrape_ok":      scrape_ok,
    }


# ---------------------------------------------------------------------------
# Diagnostic helper
# ---------------------------------------------------------------------------

def diagnose_page(html: str):
    """
    Print all div class names found on the page.
    Call this when selectors stop working to identify what changed.

    Usage from a Python shell:
        from scraper.parser import diagnose_page
        diagnose_page(open("data/raw/bg/bg_2_47.html").read())
    """
    soup = BeautifulSoup(html, "lxml")
    classes = set()
    for div in soup.find_all("div", class_=True):
        for cls in div.get("class", []):
            classes.add(cls)
    print("=== All div classes on page ===")
    for c in sorted(classes):
        print(" ", c)