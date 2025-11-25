import json
import time
import tkinter
from playwright.sync_api import sync_playwright, Page
from camoufox.sync_api import NewBrowser

from apply_methods import apply_on_page
from page_parsers import extract_links_to_visit
from urllib.parse import urlparse

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel


def hostname(url: str) -> str | None:
    return urlparse(url.strip() if '://' in url else f'https://{url.strip()}').hostname


def ensure_https(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f'https://{hostname(url)}'


def apply_on_site(ctx: dict, start_url: str):
    page = ctx['page']
    host = hostname(start_url)

    start_url = ensure_https(start_url)
    page.goto(start_url)

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


def wait_for_network_idle(page: Page, timeout=30000, idle_time=1000):
    start_time = time.time()
    last_activity_time = time.time()

    def on_request_finished(request):
        nonlocal last_activity_time
        last_activity_time = time.time()

    page.on("requestfinished", on_request_finished)

    while True:
        page.wait_for_timeout(1000)
        now = time.time()
        if now - start_time > timeout / 1000:
            print("Timeout reached while waiting for network to be idle.")
            break
        if now - last_activity_time >= idle_time / 1000:
            print("Network is idle.")
            break

    page.remove_listener("requestfinished", on_request_finished)


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
        window=(screen_width, screen_height)
    )

    for url in urls:
        print(f"Processing website: {url}")
        
        # Create a new page for each website to ensure a clean state
        page = browser.new_page(no_viewport=True)
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