# =============================================================================
# utils.py
# Shared utilities: logging setup, rate limiting, retry logic, file helpers.
# =============================================================================

import os
import time
import logging
import functools
from pathlib import Path

from scraper.config import LOG_FILE, LOG_DIR, DEFAULT_DELAY, MAX_RETRIES, RETRY_BACKOFF


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(name: str = "vedabase_scraper") -> logging.Logger:
    """
    Configure and return a logger that writes to both console and log file.
    Call this once at startup from run_scraper.py.
    """
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler — INFO and above
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # File handler — DEBUG and above (captures everything)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger


logger = logging.getLogger("vedabase_scraper")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_last_request_time = 0.0

def rate_limit(delay: float = DEFAULT_DELAY):
    """
    Sleep if needed so consecutive requests are at least `delay` seconds apart.
    Call this before every HTTP request.
    """
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _last_request_time = time.time()


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def with_retry(max_retries: int = MAX_RETRIES, backoff: float = RETRY_BACKOFF):
    """
    Decorator that retries a function on exception up to max_retries times.
    Uses exponential-ish back-off: backoff * attempt seconds.

    Usage:
        @with_retry(max_retries=3, backoff=5)
        def fetch_page(url): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    wait = backoff * attempt
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {fn.__name__}: "
                        f"{exc}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
            logger.error(f"All {max_retries} attempts failed for {fn.__name__}: {last_exc}")
            return None   # Caller must handle None gracefully
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def ensure_dirs(*dirs: str):
    """Create directories if they don't already exist."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def raw_html_path(book_code: str, filename: str) -> str:
    """Return the path where raw HTML for a verse should be saved."""
    from scraper.config import RAW_HTML_DIR
    return os.path.join(RAW_HTML_DIR, book_code, filename)


def already_scraped(path: str) -> bool:
    """Return True if a raw HTML file already exists and is non-empty."""
    return os.path.exists(path) and os.path.getsize(path) > 0


def save_raw_html(path: str, html: str):
    """Save raw HTML content to disk, creating parent dirs as needed."""
    ensure_dirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.debug(f"Saved raw HTML → {path}")


def load_raw_html(path: str) -> str:
    """Load raw HTML from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
