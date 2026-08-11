import csv
import os
import re
import time
import urllib.parse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup path resolution relative to script directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DOWNLOAD_DIR = str(PROJECT_ROOT / "data" / "downloaded_reports")
LOG_FILE = str(PROJECT_ROOT / "data" / "download_log.csv")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Log file path
log_lock = threading.Lock()

def sanitize_filename(name):
    """Remove characters that are invalid for Windows filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def clean_company_name(name):
    """Clean up company name to make it look nice and professional."""
    name = re.sub(r'\b(Live Stock Price|Live Share Price|Live Price)\b.*', '', name, flags=re.IGNORECASE)
    name = name.strip().strip(',. ')
    name = re.sub(r'\s+', ' ', name)
    return name

def extract_company_name(driver, url):
    """Try to get the company name from page title or URL slug."""
    try:
        title = driver.title
        if title and "Live Stock Price" in title:
            name = title.split("Live Stock Price")[0].strip()
            return clean_company_name(name)
    except Exception:
        pass
    
    # Fallback to URL slug
    try:
        parts = url.split("/stock-share-price/")
        if len(parts) > 1:
            slug = parts[1].split("/")[0]
            name = slug.replace("-", " ").title()
            return clean_company_name(name)
    except Exception:
        pass
        
    return "Unknown_Company"

def download_pdf(url, filepath):
    """Download PDF file with custom User-Agent."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 200:
        with open(filepath, "wb") as f:
            f.write(response.content)
        return True
    return False

def log_result(url, company_name, status, year_found, filename, err_msg):
    """Thread-safe logging of results to CSV."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_lock:
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as log_f:
            log_writer = csv.writer(log_f)
            log_writer.writerow([timestamp, url, company_name, status, year_found, filename, err_msg])

def load_completed_urls():
    """Read the log file and return a set of URLs that have been successfully downloaded."""
    completed = set()
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                # Skip header
                next(reader, None)
                for row in reader:
                    if len(row) >= 4 and row[3] == "Downloaded":
                        completed.add(row[1])
        except Exception:
            pass
    return completed

def process_url(url, idx, total_urls):
    """Process a single URL: navigate, click tabs, find and download PDF."""
    if not url.startswith("http"):
        return "Skipped", "Invalid URL"
        
    print(f"[{idx}/{total_urls}] Starting: {url}")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1366, 768)
    
    status = "Pending"
    year_found = ""
    filename = ""
    err_msg = ""
    company_name = "Unknown"
    
    try:
        driver.get(url)
        time.sleep(3) # Wait for initial page load
        
        company_name = extract_company_name(driver, url)
        
        # Wait and Click 'afi' button
        afi_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "afi"))
        )
        driver.execute_script("arguments[0].click();", afi_btn)
        time.sleep(2)
        
        # Wait and Click 'Annual Reports'
        ar_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Annual Reports"))
        )
        driver.execute_script("arguments[0].click();", ar_link)
        time.sleep(3)
        
        # Inspect table rows
        rows = driver.find_elements(By.CSS_SELECTOR, "tr")
        
        report_found = False
        for row in rows:
            text = row.text
            if not text:
                continue
                
            tokens = text.split()
            if not tokens:
                continue
                
            first_token = tokens[0]
            # Check if first token is a 4-digit number (year)
            if first_token.isdigit() and len(first_token) == 4:
                year = int(first_token)
                # We want 2026, 2025, or 2024
                if year in [2026, 2025, 2024]:
                    links = row.find_elements(By.TAG_NAME, "a")
                    if links:
                        pdf_href = links[0].get_attribute("href")
                        if pdf_href:
                            pdf_url = urllib.parse.urljoin("https://www.bseindia.com", pdf_href)
                            
                            # Formulate filename
                            safe_co_name = sanitize_filename(company_name)
                            filename = f"{safe_co_name}_{year}.pdf"
                            filepath = os.path.join(DOWNLOAD_DIR, filename)
                            
                            # Check if file already exists on disk
                            if os.path.exists(filepath):
                                print(f"[{idx}/{total_urls}] Already exists on disk: {filename}")
                                status = "Downloaded"
                                year_found = str(year)
                                report_found = True
                                break
                            
                            print(f"[{idx}/{total_urls}] Found report for {company_name} ({year}): {pdf_url}")
                            if download_pdf(pdf_url, filepath):
                                status = "Downloaded"
                                year_found = str(year)
                                report_found = True
                                print(f"[{idx}/{total_urls}] Success: {filename}")
                            else:
                                status = "Failed Download"
                                err_msg = "Direct HTTP download failed"
                                print(f"[{idx}/{total_urls}] Error: Download failed for {company_name}")
                            break
        
        if not report_found and status == "Pending":
            status = "Skipped"
            err_msg = "No report found for 2026/2025/2024"
            print(f"[{idx}/{total_urls}] Skipped: No report found for {company_name}")
            
    except Exception as e:
        status = "Failed"
        err_msg = str(e)
        print(f"[{idx}/{total_urls}] Error: {company_name} - {err_msg}")
        
    finally:
        driver.quit()
        
    log_result(url, company_name, status, year_found, filename, err_msg)
    return status, err_msg

def main():
    # Read URLs
    urls = []
    url_csv_path = PROJECT_ROOT / "data" / "url.csv"
    if not url_csv_path.exists():
        print(f"Error: {url_csv_path.name} not found at {url_csv_path}.")
        return
        
    with open(url_csv_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                urls.append(row[0].strip())
                
    limit = int(os.environ.get("LIMIT", "0"))
    if limit > 0:
        urls = urls[:limit]
        print(f"Limiting execution to the first {limit} URLs.")
                
    total_urls = len(urls)
    
    # Ensure log directory and file header exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as log_f:
            log_writer = csv.writer(log_f)
            log_writer.writerow(["Timestamp", "URL", "Company Name", "Status", "Year", "Filename", "Error"])
            
    # Load already completed URLs
    completed_urls = load_completed_urls()
    print(f"Loaded {total_urls} total URLs.")
    print(f"Found {len(completed_urls)} already completed downloads in logs.")
    
    # Filter tasks to run
    tasks_to_run = []
    for idx, url in enumerate(urls, 1):
        if url in completed_urls:
            # We already have this
            continue
        tasks_to_run.append((url, idx))
        
    print(f"Remaining URLs to process: {len(tasks_to_run)}")
    if not tasks_to_run:
        print("All URLs have already been completed!")
        return
            
    # Max concurrent browser instances
    max_workers = int(os.environ.get("MAX_WORKERS", "4"))
    print(f"Starting concurrent downloads with {max_workers} worker threads...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks
        futures = [executor.submit(process_url, url, idx, total_urls) for url, idx in tasks_to_run]
        # Wait for all tasks to complete and gather results
        results = [f.result() for f in futures]
        
    # Summarize results
    success_count = sum(1 for r in results if r[0] == "Downloaded")
    skipped_count = sum(1 for r in results if r[0] == "Skipped")
    failed_count = sum(1 for r in results if r[0] in ["Failed", "Failed Download"])
    
    duration = time.time() - start_time
    print("\n" + "="*40)
    print("Process Complete!")
    print(f"Duration:        {duration:.2f} seconds")
    print(f"Downloaded in this run: {success_count}")
    print(f"Skipped in this run:    {skipped_count}")
    print(f"Failed in this run:     {failed_count}")
    print(f"Logs written to: {LOG_FILE}")
    print("="*40)

if __name__ == "__main__":
    main()
