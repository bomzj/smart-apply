import json
import time
import tkinter
import logging
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Page

from apply_methods import apply_on_page
from page_parsers import extract_links_to_visit

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel

from cloudflare_challenge import find_cf_challenge, solve_cf_challenge
from result import safe_call


def hostname(url: str) -> str | None:
    return urlparse(url.strip() if '://' in url else f'https://{url.strip()}').hostname


def ensure_https(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f'https://{hostname(url)}'


def apply_on_site(ctx: dict, start_url: str):
    page = ctx['page']
    host = hostname(start_url)

    start_url = ensure_https(start_url)
    page.goto(start_url)
    
    # Detect and solve Cloudflare interstitial challenge if present
    cf_detected = find_cf_challenge(page)
    if cf_detected:
        captcha_locator, _ = cf_detected
        print(f"Cloudflare interstitial challenge detected on {host}, attempting to solve...")
        solved = solve_cf_challenge(captcha_locator)
    
    if cf_detected and solved:
        print(f"Successfully solved Cloudflare challenge on {host}.")
    elif cf_detected and not solved:
        print(f"Failed to solve Cloudflare challenge on {host}. Skipping this site.\n")
        return False

    # Extract page links related to jobs and contact info
    links = extract_links_to_visit(page)
    if links:
        formatted_links = json.dumps(links, indent=2, ensure_ascii=False)
        print(f"Extracted links for {host}:\n{formatted_links}\n")
    else:
        print(f"No links found on the page at {host}.\n")

    # Shows whether application was submitted or scheduled successfully
    applied = False
    
    for link in links[:5]:  # Limit to first 5 links to avoid excessive navigation
        print(f"Visiting page: {link}")
        page.goto(link)
        applied = apply_on_page(ctx)
        global sent_emails, submitted_forms
        sent_emails += 1 if applied == 'email' else 0
        submitted_forms += 1 if applied == 'form' else 0
        if applied: break

    if not applied:
        print(f"No email or form application were found on website {host}.\n")

    return bool(applied)


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

with open('urls.txt', 'r') as f:
    urls = [line.strip() for line in f if line.strip()]

if urls:
    print(f"Total URLs to process: {len(urls)}\n")
else:
    print("No URLs found in urls.txt. Exiting.")
    exit(0)

# Get the actual screen resolution dynamically
root = tkinter.Tk()
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.destroy()

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
        user_data_dir="./browser_session_data",
        headless=False,
        args=['--start-maximized'], # Maximize window
        no_viewport=True, # also required for maximized window
        slow_mo=50
    )

    failed_urls_log = logger('failed_urls', 'failed_urls.log')

    for url in urls:
        print(f"Processing website: {url}")
        
        # Create a new page for each website to ensure a clean state
        page = browser.new_page()
        ctx = {'page': page}
        
        host = hostname(url)
        applied, err = safe_call(apply_on_site, ctx, url)
        
        if not applied:
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