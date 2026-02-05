import json
import logging
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from googleapiclient.errors import HttpError

from result import Err, Ok
from apply_methods import apply_on_site, hostname

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel


PROJECT_ROOT = Path(__file__).parent.parent
URLS_FILE = PROJECT_ROOT / 'data' / 'urls.txt'
LOGS_DIR = PROJECT_ROOT / 'logs'
BROWSER_DATA_DIR = PROJECT_ROOT / '.browser_session_data'


async def main():
    with open(URLS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    if urls:
        print(f"Total URLs to process: {len(urls)}\n")
    else:
        print("No URLs found in urls.txt. Exiting.")
        exit(0)

    print('Launching browser...')

    # Counters
    stats = {
        "total_sites": len(urls),
        "processed_sites": 0,
        "sent_emails": 0,
        "submitted_forms": 0
    }
 
    # Start the live stats display (wraps all processing)
    with Live(stats_panel(stats), auto_refresh=True) as live:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch_persistent_context(
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
                page = await browser.new_page()
                ctx = {'page': page}
                
                host = hostname(url)
                res = await apply_on_site(ctx, url)
                
                match res:
                    case Ok(method):
                        match method:
                            case 'email':
                                stats["sent_emails"] += 1
                            case 'form':
                                stats["submitted_forms"] += 1
                            case _:
                                print(f"No email or form application were found on website {host}.\n")
                                failed_urls_log.info(url)
                    
                    case Err(e):
                        match e:
                            # handle gmail 429 limit exceeded error specifically
                            case HttpError() as e:
                                print(f"Error sending email: {e}\n")
                                if e.content:
                                    error_json = json.loads(e.content.decode('utf-8'))
                                    print(f"API error details: {error_json}")
                                print(f"Failed to apply on website: {host}\n")
                                print("Exitting due to potential Gmail API limit has reached.")
                                exit(0)
                            case _:
                                print(f"Failed to apply on website: {host}\n{e}\n")
                                failed_urls_log.info(url)
            
                stats["processed_sites"] += 1
                print(f"Finished processing website: {host}\n")
                live.update(stats_panel(stats))
                await page.close()

            await browser.close()
            # pw.stop() is automatic with context manager

    print("All websites have been processed.\n")


def stats_panel(stats: dict[str, int]) -> Panel:
    total_sites, processed_sites, sent_emails, submitted_forms = stats.values()

    applied = sent_emails + submitted_forms
    return Panel(
        f"Processed: {processed_sites} / {total_sites} websites\n"
        f"Emails Sent: {sent_emails}\n"
        f"Forms Submitted: {submitted_forms}\n"
        f"Total Applied: {applied}",
        title="Apply to Jobs Progress",
        border_style="blue"
    )

# logger is used for logging failed URLs only as of now
def logger(name: str, path: str, fmt: str = '%(message)s') -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)

    if not log.handlers:
        handler = logging.FileHandler(path, mode="a", encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(fmt))
        log.addHandler(handler)

    return log


if __name__ == "__main__":
    asyncio.run(main())