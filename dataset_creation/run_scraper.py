#!/usr/bin/env python3
# =============================================================================
# run_scraper.py
# Entry point for Phase 1 data collection.
#
# Usage:
#   python run_scraper.py --books all
#   python run_scraper.py --books bg
#   python run_scraper.py --books bg iso
#   python run_scraper.py --books all --delay 2.0
#   python run_scraper.py --books all --resume
#   python run_scraper.py --verify bg        # verify existing output only
#   python run_scraper.py --diagnose bg 2 47 # debug HTML selectors for one verse
# =============================================================================

import sys
import argparse
import logging

# Make sure project root is on path when running from any directory
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.utils import setup_logger, ensure_dirs
from scraper.config import BOOKS, DEFAULT_DELAY, RAW_HTML_DIR, SCRAPED_DIR, LOG_DIR
from scraper.scraper import scrape_book, save_scraped_json, verify_output


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vedabase scraper for Prabhupada RAG project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scraper.py --books all
  python run_scraper.py --books bg --delay 2.0
  python run_scraper.py --books all --resume
  python run_scraper.py --verify bg
  python run_scraper.py --diagnose bg 2 47
        """
    )
    parser.add_argument(
        "--books", nargs="+",
        choices=list(BOOKS.keys()) + ["all"],
        default=["all"],
        help="Which books to scrape. Use 'all' for all three."
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help=f"Seconds between requests (default: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--resume", action="store_true", default=True,
        help="Resume: skip verses whose raw HTML is already saved (default: True)"
    )
    parser.add_argument(
        "--no-resume", action="store_false", dest="resume",
        help="Re-scrape everything even if raw HTML exists"
    )
    parser.add_argument(
        "--verify", metavar="BOOK_CODE",
        help="Just verify an already-scraped book's output JSON (no scraping)"
    )
    parser.add_argument(
        "--diagnose", nargs=3, metavar=("BOOK_CODE", "D1", "D2"),
        help="Print all div classes on one verse page to debug selectors"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Set up logger first
    logger = setup_logger()

    # Create required directories
    ensure_dirs(RAW_HTML_DIR, SCRAPED_DIR, LOG_DIR)
    for book_code in BOOKS:
        ensure_dirs(os.path.join(RAW_HTML_DIR, book_code))

    # --- Diagnose mode: inspect HTML of one verse ---
    if args.diagnose:
        book_code, d1_str, d2_str = args.diagnose
        d1 = int(d1_str)
        d2 = int(d2_str) if d2_str != "None" else None
        from scraper.scraper import fetch_page, build_url
        from scraper.parser import diagnose_page
        url = build_url(book_code, d1, d2)
        print(f"Fetching {url} ...")
        html = fetch_page(url)
        if html:
            diagnose_page(html)
            # Also save for manual inspection
            with open("diagnose_output.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("\nFull HTML saved to diagnose_output.html")
        else:
            print("Failed to fetch page.")
        return

    # --- Verify mode: check existing JSON output ---
    if args.verify:
        verify_output(args.verify)
        return

    # --- Normal scrape mode ---
    books_to_scrape = list(BOOKS.keys()) if "all" in args.books else args.books

    logger.info(f"Books to scrape : {books_to_scrape}")
    logger.info(f"Request delay   : {args.delay}s")
    logger.info(f"Resume mode     : {args.resume}")
    logger.info("")

    all_results = {}

    for book_code in books_to_scrape:
        records = scrape_book(
            book_code=book_code,
            delay=args.delay,
            resume=args.resume
        )
        output_path = save_scraped_json(book_code, records)
        all_results[book_code] = len(records)

        # Auto-verify after each book
        verify_output(book_code)

    # Final summary
    logger.info("=" * 60)
    logger.info("ALL SCRAPING COMPLETE")
    for book_code, count in all_results.items():
        logger.info(f"  {BOOKS[book_code]['name']:<35} {count} records")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
