# Annual Reports Downloader

A utility package to scrape and download annual reports for listed companies from BSE (Bombay Stock Exchange).

## Features

- **Automated BSE Stock Navigation:** Uses Selenium WebDriver to navigate to BSE stock profiles.
- **Efficient Downloader:** Downloads and stores PDF annual reports using `ThreadPoolExecutor` for parallel downloading.
- **Duplication Prevention:** Tracks completed downloads in a CSV log to prevent downloading the same report multiple times.
- **Robust Networking:** Utilizes custom User-Agent headers to bypass standard direct download blocking.

---

## Directory Structure

```
annual_reports/
├── data/
│   ├── downloaded_reports/               # PDF annual reports downloaded from BSE
│   ├── BhavCopy_BSE_CM_0_0_0_20260624_F_0000.xlsx
│   ├── moneyworks4me.xlsx
│   ├── url.csv                           # Input BSE Stock URLs list
│   └── download_log.csv                  # Log of completed and pending downloads
├── src/
│   ├── main.py
│   └── download_reports.py               # BSE scraper & PDF downloader script
├── tests/
│   └── test_aRdownload.py                # Selenium verification script
├── pyproject.toml                        # Project configuration & dependencies
├── README.md                             # Documentation
└── uv.lock                               # Resolved dependency lockfile
```

---

## Getting Started

### Prerequisites

This project is configured with `pyproject.toml` and designed to run using [uv](https://github.com/astral-sh/uv) or standard pip.

Dependencies include:
- `requests`
- `selenium`

### Installation

Clone the repository and install dependencies:

```bash
# Using uv (Recommended)
uv sync

# Using standard pip
pip install -e .
```

---

## Usage

### Downloading Annual Reports

1. Add target stock profile URLs to `data/url.csv` (one URL per line).
2. Run the downloader script:

```bash
uv run python src/download_reports.py
```
