import json
import time
import tkinter
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Page
from camoufox.sync_api import NewBrowser

from apply_methods import apply_on_page
from page_parsers import extract_links_to_visit

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel

from cloudflare_challenge import find_cf_challenge, solve_cf_challenge


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
        print(f"Cloudflare interstitial challenge detected on {host}, attempting to solve...")
        solved = solve_cf_challenge(page, timeout=60000)
    
    if cf_detected and solved:
        print(f"Successfully solved Cloudflare challenge on {host}.")
    elif cf_detected and not solved:
        print(f"Failed to solve Cloudflare challenge on {host}. Skipping this site.\n")
        return

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
    browser = NewBrowser(
        pw, 
        headless=False, 
        humanize=True, 
        window=(screen_width, screen_height),
        # Allow cookies/session to persist to avoid repeated captcha challenges
        persistent_context=True, 
        user_data_dir="./browser_session_data"
    )

    for url in urls:
        print(f"Processing website: {url}")
        
        # Create a new page for each website to ensure a clean state
        page = browser.new_page()
        ctx = {'page': page}
        
        try:
            host = hostname(url)
            apply_on_site(ctx, url)
        except Exception as e:
            print(f"Failed to apply on website: {host} \n{e}\n")
        finally:
            processed_sites += 1
            print(f"Finished processing website: {host}\n")
            live.update(stats_panel())
            page.close()

    browser.close()
    pw.stop()

    print("All websites have been processed.\n")