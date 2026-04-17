# =============================================================================
# config.py
# Book configurations and verse maps for the Vedabase scraper.
# To add a new book later (e.g. Srimad Bhagavatam), just add a new entry here.
# =============================================================================

# ---------------------------------------------------------------------------
# Bhagavad Gita — 18 chapters, variable verse counts
# Source: https://vedabase.io/en/library/bg/{chapter}/{verse}/
# ---------------------------------------------------------------------------
BG_VERSE_MAP = {
    1:  47,
    2:  72,
    3:  43,
    4:  42,
    5:  29,
    6:  47,
    7:  30,
    8:  28,
    9:  34,
    10: 42,
    11: 55,
    12: 20,
    13: 35,
    14: 27,
    15: 20,
    16: 24,
    17: 28,
    18: 78,
}

# ---------------------------------------------------------------------------
# Sri Isopanishad — 18 mantras + invocation (mantra 0)
# Source: https://vedabase.io/en/library/iso/{mantra}/
# ---------------------------------------------------------------------------
ISO_MANTRA_MAP = list(range(0, 19))   # 0 = invocation, 1–18 = mantras

# ---------------------------------------------------------------------------
# Nectar of Instruction — 11 verses
# Source: https://vedabase.io/en/library/noi/{verse}/
# ---------------------------------------------------------------------------
NOI_VERSE_MAP = list(range(1, 12))    # verses 1–11

# ---------------------------------------------------------------------------
# Brahma Samhita — Chapter 5 only, 60 verses
# Source: https://vedabase.io/en/library/bs/5/{verse}/
# ---------------------------------------------------------------------------
BS_VERSE_MAP = list(range(1, 63))    # verses 1–62

# ---------------------------------------------------------------------------
# Master book config dictionary
# Each key is the book_code used everywhere in the project.
# ---------------------------------------------------------------------------
BOOKS = {

    "bg": {
        "name":         "Bhagavad Gita As It Is",
        "book_code":    "bg",
        "base_url":     "https://vedabase.io/en/library/bg/{d1}/{d2}/",
        "divisions":    2,          # chapter + verse
        "verse_map":    BG_VERSE_MAP,
        "div1_label":   "chapter",
        "div2_label":   "verse",
        "reference_fn": lambda d1, d2: f"BG {d1}.{d2}",
        "id_fn":        lambda d1, d2: f"bg_{d1}_{d2}",
    },

    "iso": {
        "name":         "Sri Isopanishad",
        "book_code":    "iso",
        "base_url":     "https://vedabase.io/en/library/iso/{d1}/",
        "divisions":    1,          # mantra only
        "verse_map":    ISO_MANTRA_MAP,
        "div1_label":   "mantra",
        "div2_label":   None,
        "reference_fn": lambda d1, d2=None: f"ISO {d1}",
        "id_fn":        lambda d1, d2=None: f"iso_{d1}",
    },

    "noi": {
        "name":         "Nectar of Instruction",
        "book_code":    "noi",
        "base_url":     "https://vedabase.io/en/library/noi/{d1}/",
        "divisions":    1,          # verse only
        "verse_map":    NOI_VERSE_MAP,
        "div1_label":   "verse",
        "div2_label":   None,
        "reference_fn": lambda d1, d2=None: f"NOI {d1}",
        "id_fn":        lambda d1, d2=None: f"noi_{d1}",
    },

    "bs": {
        "name":         "Brahma Samhita",
        "book_code":    "bs",
        "base_url":     "https://vedabase.io/en/library/bs/5/{d1}/",
        "divisions":    1,
        "verse_map":    BS_VERSE_MAP,
        "div1_label":   "verse",
        "div2_label":   None,
        "reference_fn": lambda d1, d2=None: f"BS 5.{d1}",
        "id_fn":        lambda d1, d2=None: f"bs_{d1}",
    },
}

# ---------------------------------------------------------------------------
# Scraper behaviour defaults (can be overridden via CLI args)
# ---------------------------------------------------------------------------
DEFAULT_DELAY     = 1.5     # seconds between requests — be respectful
MAX_RETRIES       = 3       # retry a failed page this many times
RETRY_BACKOFF     = 5       # seconds to wait before each retry
REQUEST_TIMEOUT   = 30      # seconds before giving up on a single request

# ---------------------------------------------------------------------------
# Directory layout (relative to project root)
# ---------------------------------------------------------------------------
RAW_HTML_DIR    = "data/raw"
SCRAPED_DIR     = "data/scraped"
LOG_DIR         = "logs"
LOG_FILE        = "logs/scraper.log"
