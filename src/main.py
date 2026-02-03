import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

from result import safe_call
from apply_methods import apply_on_site, ApplyMethod, hostname

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel


def stats_panel():
    applied = sent_emails + submitted_forms
    return Panel(
        f"Processed: {processed_sites} / {total_sites} websites\n"
        f"Emails Sent: {sent_emails}\n"
        f"Forms Submitted: {submitted_forms}\n"
        f"Total Applied: {applied}",
        title="Apply to Jobs Progress",
        border_style="blue"
    )


def logger(name: str, path: str, fmt: str = '%(message)s') -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)

    if not log.handlers:
        handler = logging.FileHandler(path, mode="a", encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(fmt))
        log.addHandler(handler)

    return log


## Main

PROJECT_ROOT = Path(__file__).parent.parent
URLS_FILE = PROJECT_ROOT / 'data' / 'urls.txt'
LOGS_DIR = PROJECT_ROOT / 'logs'
BROWSER_DATA_DIR = PROJECT_ROOT / '.browser_session_data'

with open(URLS_FILE, 'r') as f:
    urls = [line.strip() for line in f if line.strip()]

if urls:
    print(f"Total URLs to process: {len(urls)}\n")
else:
    print("No URLs found in urls.txt. Exiting.")
    exit(0)

print('Launching browser...')

# Global Counters
total_sites = len(urls)
processed_sites = 0
sent_emails = 0
submitted_forms = 0

# Start the live stats display (wraps all processing)
with Live(stats_panel(), auto_refresh=True) as live:

    pw = sync_playwright().start()
    browser = pw.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_DATA_DIR),
        headless=False,
        args=['--start-maximized'], # Maximize window
        no_viewport=True, # also required for maximized window
        slow_mo=50
    )

    failed_urls_log = logger('failed_urls', str(LOGS_DIR / 'failed_urls.log'))

    for url in urls:
        print(f"Processing website: {url}")
        
        # Create a new page for each website to ensure a clean state
        page = browser.new_page()
        ctx = {'page': page}
        
        host = hostname(url)
        applied, err = safe_call(apply_on_site, ctx, url)
        
        # Update counters based on application type
        match applied:
            case 'email':
                sent_emails += 1
            case 'form':
                submitted_forms += 1
            case _:
                print(f"No email or form application were found on website {host}.\n")
                failed_urls_log.info(url)

        if err:
            print(f"Failed to apply on website: {host} \n{err}\n")
    
        processed_sites += 1
        print(f"Finished processing website: {host}\n")
        live.update(stats_panel())
        page.close()

    browser.close()
    pw.stop()

    print("All websites have been processed.\n")