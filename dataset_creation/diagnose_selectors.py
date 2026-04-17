#!/usr/bin/env python3
# =============================================================================
# diagnose_selectors.py
#
# Run this FIRST before the full scrape to verify that the HTML parser
# is correctly extracting content from Vedabase pages.
#
# This script fetches ONE verse, saves the HTML, and shows you what each
# selector extracts. If selectors are wrong, you fix them in parser.py
# before running the full 900+ verse scrape.
#
# Usage:
#   python diagnose_selectors.py
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup
from scraper.scraper import fetch_page
from scraper.parser import parse_verse_page, diagnose_page, SELECTORS


def test_verse(book_code: str, d1: int, d2=None):
    """
    Fetch and parse one verse, printing a detailed report.
    """
    from scraper.config import BOOKS
    from scraper.scraper import build_url

    cfg = BOOKS[book_code]
    url = build_url(book_code, d1, d2)
    ref = cfg["reference_fn"](d1, d2)

    print(f"\n{'='*60}")
    print(f"Testing: {ref}")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    html = fetch_page(url)
    if not html:
        print("ERROR: Could not fetch page.")
        return

    # Save HTML for manual inspection
    os.makedirs("diagnose_output", exist_ok=True)
    html_file = f"diagnose_output/{book_code}_{d1}_{d2}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Raw HTML saved to: {html_file}")
    print(f"HTML size: {len(html):,} bytes\n")

    # Show all div classes (helps identify selector names)
    print("--- All div class names on page ---")
    diagnose_page(html)

    # Test each selector individually
    soup = BeautifulSoup(html, "lxml")
    print("\n--- Selector test results ---")
    for field, selectors in SELECTORS.items():
        print(f"\n[{field}]")
        found = False
        for selector in selectors:
            try:
                tag = soup.select_one(selector)
                if tag:
                    text_preview = tag.get_text(separator=" ", strip=True)[:150]
                    print(f"  ✓ '{selector}' → {text_preview!r}")
                    found = True
                    break
                else:
                    print(f"  ✗ '{selector}' → no match")
            except Exception as e:
                print(f"  ✗ '{selector}' → error: {e}")
        if not found:
            print(f"  ⚠ ALL SELECTORS FAILED for '{field}'")

    # Full parse result
    print("\n--- Full parse result ---")
    record = parse_verse_page(html, book_code, d1, d2)
    for key, val in record.items():
        if isinstance(val, str) and len(val) > 200:
            print(f"  {key:20}: {val[:200]}... [{len(val)} chars total]")
        else:
            print(f"  {key:20}: {val!r}")


if __name__ == "__main__":
    # Test one verse from each book
    # These are representative verses — adjust if needed
    print("Testing Bhagavad Gita 2.47...")
    test_verse("bg", 2, 47)

    print("\n\nTesting Sri Isopanishad mantra 1...")
    test_verse("iso", 1)

    print("\n\nTesting Nectar of Instruction verse 1...")
    test_verse("noi", 1)
