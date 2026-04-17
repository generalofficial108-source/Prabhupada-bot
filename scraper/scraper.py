# =============================================================================
# scraper.py
# Core scraping engine.
#
# BG STRATEGY (URL-based):
#   Vedabase groups some BG verses under a single page (e.g. /bg/1/16-18/).
#   We cannot reliably enumerate verse URLs from a static config.
#   So for BG: fetch each chapter index page → extract all verse URLs from it
#   → scrape each URL individually.
#
# ISO / NOI STRATEGY (index-based):
#   These books have simple sequential mantra/verse numbers with no grouping.
#   We build URLs directly from the config and scrape them one by one.
#
# RESUME SUPPORT:
#   Raw HTML is saved to disk keyed by a sanitised filename derived from
#   the URL path. On resume, existing HTML files are reused — no re-fetch.
# =============================================================================

import os
import re
import json
import logging
import requests

from bs4 import BeautifulSoup
from tqdm import tqdm

from scraper.config import (
    BOOKS, DEFAULT_DELAY, REQUEST_TIMEOUT, SCRAPED_DIR, RAW_HTML_DIR
)
from scraper.parser import parse_verse_page
from scraper.utils import (
    rate_limit, with_retry, ensure_dirs,
    already_scraped, save_raw_html, load_raw_html
)

logger = logging.getLogger("vedabase_scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def build_url(book_code: str, d1: int, d2=None) -> str:
    """
    Build a verse URL from book code/divisions for diagnose helpers.
    """
    cfg = BOOKS[book_code]
    if cfg["divisions"] == 2:
        if d2 is None:
            raise ValueError(f"{book_code} requires both d1 and d2")
        return cfg["base_url"].format(d1=d1, d2=d2)
    return cfg["base_url"].format(d1=d1)


# =============================================================================
# HTTP LAYER
# =============================================================================

@with_retry(max_retries=3, backoff=5)
def fetch_with_requests(url: str) -> str | None:
    rate_limit()
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    try:
        rate_limit()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS)
            page.goto(url, timeout=REQUEST_TIMEOUT * 1000)
            try:
                page.wait_for_selector(
                    "[class*='translation'], [class*='purport']",
                    timeout=15000
                )
            except Exception:
                pass
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.error(f"Playwright fetch failed for {url}: {e}")
        return None


def fetch_page(url: str) -> str | None:
    """
    Fetch a page. Tries requests first; falls back to Playwright if the
    response contains no recognisable content markers.
    """
    logger.debug(f"HTTP fetch: {url}")
    html = fetch_with_requests(url)

    if html is None:
        logger.warning(f"requests failed for {url}, trying Playwright...")
        return fetch_with_playwright(url)

    content_markers = ["translation", "purport", "synonyms", "verse_text", "verse-text"]
    if not any(m in html.lower() for m in content_markers):
        logger.info(f"No content markers found for {url} — falling back to Playwright")
        return fetch_with_playwright(url)

    return html


# =============================================================================
# FILENAME HELPERS
# =============================================================================

def url_to_filename(url: str) -> str:
    """
    Convert a Vedabase verse URL to a safe filename for caching raw HTML.

    Examples:
        https://vedabase.io/en/library/bg/1/16-18/  →  bg_1_16-18.html
        https://vedabase.io/en/library/iso/1/       →  iso_1.html
    """
    match = re.search(r'/library/(.+?)/?$', url)
    if not match:
        safe = re.sub(r'[^\w\-]', '_', url)
        return safe + ".html"
    path = match.group(1)           # e.g. "bg/1/16-18"
    safe = path.replace("/", "_")   # e.g. "bg_1_16-18"
    return safe + ".html"


def raw_html_path_for_url(book_code: str, url: str) -> str:
    filename = url_to_filename(url)
    return os.path.join(RAW_HTML_DIR, book_code, filename)


# =============================================================================
# BG: CHAPTER INDEX SCRAPING
# =============================================================================

def get_chapter_verse_urls(chapter: int) -> list[str]:
    """
    Fetch the BG chapter index page and return all verse page URLs.

    Filters strictly for URLs matching /bg/{chapter}/{verse_or_range}/
    to exclude nav/breadcrumb links.
    """
    index_url = f"https://vedabase.io/en/library/bg/{chapter}/"
    logger.info(f"Fetching chapter index: {index_url}")

    html = fetch_page(index_url)
    if not html:
        logger.error(f"Failed to fetch chapter {chapter} index")
        return []

    soup = BeautifulSoup(html, "lxml")

    # Match ONLY verse URLs: /en/library/bg/{chapter}/{digits or digits-digits}/
    # This deliberately excludes the chapter index URL itself and nav links.
    verse_url_pattern = re.compile(
        rf'^/en/library/bg/{chapter}/([\d]+(?:-[\d]+)?)/?$'
    )

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if verse_url_pattern.match(href):
            full_url = "https://vedabase.io" + href.rstrip("/") + "/"
            links.add(full_url)

    sorted_links = sorted(links, key=_verse_url_sort_key)
    logger.info(f"  Chapter {chapter}: found {len(sorted_links)} verse URLs")
    return sorted_links


def _verse_url_sort_key(url: str) -> int:
    """Sort verse URLs numerically by the first verse number in the path."""
    match = re.search(r'/bg/\d+/(\d+)', url)
    return int(match.group(1)) if match else 0


def parse_verse_ref_from_url(url: str) -> tuple[int, str]:
    """
    Extract (chapter, verse_part) from a BG URL.

    /en/library/bg/2/47/    → (2, "47")
    /en/library/bg/1/16-18/ → (1, "16-18")
    """
    match = re.search(r'/bg/(\d+)/([\d\-]+)/', url)
    if not match:
        raise ValueError(f"Cannot parse BG verse ref from URL: {url}")
    return int(match.group(1)), match.group(2)


# =============================================================================
# SCRAPE ONE VERSE — BG (URL-based)
# =============================================================================

def scrape_bg_verse_from_url(url: str, resume: bool = True) -> dict | None:
    """
    Fetch, cache, and parse a single BG verse page identified by its URL.
    Handles both single verses (/bg/2/47/) and grouped verses (/bg/1/16-18/).
    """
    raw_path = raw_html_path_for_url("bg", url)

    if resume and already_scraped(raw_path):
        logger.debug(f"Cache hit: {raw_path}")
        html = load_raw_html(raw_path)
    else:
        html = fetch_page(url)
        if html is None:
            logger.error(f"FAILED to fetch {url}")
            return None
        save_raw_html(raw_path, html)

    try:
        chapter, verse_part = parse_verse_ref_from_url(url)
    except ValueError as e:
        logger.error(str(e))
        return None

    record = parse_verse_page(html, "bg", chapter, verse_part)

    if not record["scrape_ok"]:
        logger.warning(f"Content missing for {record['reference']}")

    return record


# =============================================================================
# SCRAPE ONE VERSE — ISO / NOI (index-based)
# =============================================================================

def scrape_indexed_verse(book_code: str, d1: int, resume: bool = True) -> dict | None:
    """
    Fetch, cache, and parse a single ISO or NOI verse page.
    """
    cfg = BOOKS[book_code]
    url = cfg["base_url"].format(d1=d1)
    raw_path = raw_html_path_for_url(book_code, url)

    if resume and already_scraped(raw_path):
        logger.debug(f"Cache hit: {raw_path}")
        html = load_raw_html(raw_path)
    else:
        logger.info(f"Fetching {cfg['reference_fn'](d1)} → {url}")
        html = fetch_page(url)
        if html is None:
            logger.error(f"FAILED to fetch {url}. Skipping.")
            return None
        save_raw_html(raw_path, html)

    record = parse_verse_page(html, book_code, d1, d2=None)

    if not record["scrape_ok"]:
        logger.warning(f"Content missing for {record['reference']}")

    return record


# =============================================================================
# SCRAPE AN ENTIRE BOOK
# =============================================================================

def scrape_book(book_code: str, delay: float = DEFAULT_DELAY, resume: bool = True) -> list[dict]:
    """
    Scrape an entire book and return a list of parsed record dicts.
    """
    cfg = BOOKS[book_code]

    logger.info("=" * 60)
    logger.info(f"Starting scrape: {cfg['name']}")
    logger.info("=" * 60)

    ensure_dirs(os.path.join(RAW_HTML_DIR, book_code))

    records = []
    failed  = []

    # ------------------------------------------------------------------
    # BG — URL-based
    # ------------------------------------------------------------------
    if book_code == "bg":

        # Collect all verse URLs across all 18 chapters first
        all_verse_urls = []
        for chapter in cfg["verse_map"].keys():
            chapter_urls = get_chapter_verse_urls(chapter)
            all_verse_urls.extend(chapter_urls)

        logger.info(f"Total BG verse pages found: {len(all_verse_urls)}")

        for url in tqdm(all_verse_urls, desc=cfg["name"], unit="verse"):
            record = scrape_bg_verse_from_url(url, resume=resume)

            if record is not None:
                records.append(record)
                logger.debug(f"  {'✓' if record['scrape_ok'] else '✗'} {record['reference']}")
            else:
                failed.append(url)
                logger.error(f"  ✗ FAILED: {url}")

    # ------------------------------------------------------------------
    # ISO / NOI — index-based
    # ------------------------------------------------------------------
    else:
        for d1 in tqdm(cfg["verse_map"], desc=cfg["name"], unit="verse"):
            record = scrape_indexed_verse(book_code, d1, resume=resume)

            if record is not None:
                records.append(record)
                logger.debug(f"  {'✓' if record['scrape_ok'] else '✗'} {record['reference']}")
            else:
                ref = cfg["reference_fn"](d1)
                failed.append(ref)
                logger.error(f"  ✗ FAILED: {ref}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 60)
    logger.info(f"{cfg['name']} scrape complete.")
    logger.info(f"  Pages scraped : {len(records)}")
    logger.info(f"  Failed        : {len(failed)}")
    if failed:
        logger.warning(f"  Failed items  : {failed}")
    logger.info("=" * 60 + "\n")

    return records


# =============================================================================
# SAVE / VERIFY
# =============================================================================

def save_scraped_json(book_code: str, records: list[dict]) -> str:
    ensure_dirs(SCRAPED_DIR)
    output_path = os.path.join(SCRAPED_DIR, f"{book_code}_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(records)} records → {output_path}")
    return output_path


def verify_output(book_code: str):
    output_path = os.path.join(SCRAPED_DIR, f"{book_code}_raw.json")
    if not os.path.exists(output_path):
        print(f"No output file found at {output_path}")
        return

    with open(output_path, encoding="utf-8") as f:
        records = json.load(f)

    total  = len(records)
    fields = ["verse_sanskrit", "word_for_word", "translation", "purport"]

    print(f"\n{'='*50}")
    print(f"Verification: {BOOKS[book_code]['name']}")
    print(f"{'='*50}")
    print(f"Total records : {total}")
    for field in fields:
        filled = sum(1 for r in records if r.get(field, "").strip())
        pct    = (filled / total * 100) if total else 0
        status = "✓" if pct > 95 else ("⚠" if pct > 50 else "✗")
        print(f"  {status} {field:<20} {filled:>4}/{total}  ({pct:.1f}%)")
    print()
    if records:
        r = records[0]
        print(f"Sample record ({r['reference']}):")
        print(f"  translation : {r['translation'][:120]}...")
        print(f"  purport     : {r['purport'][:120]}...")
    print()