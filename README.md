# Prabhupada RAG — Phase 1: Scraper

## Project Structure
```
prabhupada_rag/
├── scraper/
│   ├── config.py           # Book configs and verse maps
│   ├── scraper.py          # Main scraper engine
│   ├── parser.py           # HTML parsing logic
│   └── utils.py            # Helpers: rate limit, retry, logging
├── data/
│   ├── raw/                # Raw HTML saved per verse (auto-created)
│   │   ├── bg/
│   │   ├── iso/
│   │   └── noi/
│   └── scraped/            # Parsed JSON output (auto-created)
│       ├── bg_raw.json
│       ├── iso_raw.json
│       └── noi_raw.json
├── logs/
│   └── scraper.log         # All activity logged here
├── requirements.txt
└── run_scraper.py          # Entry point
```

## Setup
```bash
pip install -r requirements.txt
```

## Usage
```bash
# Scrape all three books
python run_scraper.py --books all

# Scrape specific book
python run_scraper.py --books bg
python run_scraper.py --books iso
python run_scraper.py --books noi

# Scrape with custom delay (seconds between requests)
python run_scraper.py --books all --delay 2.0

# Resume from where you left off (skips already-saved raw HTML)
python run_scraper.py --books all --resume
```

## Output
Each book produces a JSON file in `data/scraped/` with this structure per record:
```json
{
  "id": "bg_2_47",
  "book": "Bhagavad Gita As It Is",
  "book_code": "bg",
  "division_1": 2,
  "division_2": 47,
  "division_3": null,
  "reference": "BG 2.47",
  "verse_sanskrit": "...",
  "word_for_word": "...",
  "translation": "...",
  "purport": "..."
}
```
