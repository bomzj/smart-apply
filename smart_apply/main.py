import json
import asyncio
from pathlib import Path
from googleapiclient.errors import HttpError

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

from smart_apply.result import Err, Ok
from smart_apply.apply_methods import (
    ApplyContext, AppliedViaEmail, AppliedViaForm, 
    NoLinksFound, FailedAttempt, NoApplicationMethod,
    apply_on_site, hostname
)
from smart_apply.config import settings
from smart_apply.logger import setup_logging, set_host, log_info, log_error, log_failed_url, log_blank_line, console

# Rich imports for fixed stats display
from rich.live import Live
from rich.panel import Panel
from rich.padding import Padding


PROJECT_ROOT = Path(__file__).parent.parent
URLS_FILE = PROJECT_ROOT / 'data' / 'urls.txt'
BROWSER_DATA_DIR = PROJECT_ROOT / '.browser_session_data'


async def main():
    setup_logging()

    with open(URLS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    if urls:
        log_info(f"Total URLs to process: {len(urls)}")
    else:
        log_info("No URLs found in urls.txt. Exiting.")
        exit(0)

    log_info('Launching browser...')

    # Counters
    stats = {
        "total_sites": len(urls),
        "processed_sites": 0,
        "sent_emails": 0,
        "submitted_forms": 0
    }

    options = ChromiumOptions()
    options.add_argument('--start-maximized')

    # Start the live stats display (wraps all processing)
    with Live(stats_panel(stats), console=console, auto_refresh=True) as live:
        async with Chrome(options=options) as browser:
            # Start the initial tab (required by PyDoll)
            await browser.start()

            for url in urls:
                host = hostname(url)
                set_host(host)

                log_blank_line()
                log_info(f"Processing website: {host}...")
                
                # Create a new tab for each website to ensure a clean state
                tab = await browser.new_tab()

                ctx = ApplyContext(tab, None)
                
                res = await apply_on_site(ctx, url)
                
                match res:
                    case Ok(status):
                        match status:
                            case AppliedViaEmail(email):
                                stats["sent_emails"] += 1
                            case AppliedViaForm(url):
                                stats["submitted_forms"] += 1
                            case NoLinksFound():
                                log_info(f"No relevant links found on {host}.")
                            case FailedAttempt():
                                pass
                            case NoApplicationMethod():
                                log_info(f"No email or form application were found on website {host}.")
                    
                    case Err(e):
                        match e:
                            # TODO: handle the case when site is not available
                            # handle gmail 429 limit exceeded error specifically
                            case HttpError() as e:
                                log_error(f"Error sending email: {e}")
                                if e.content:
                                    error_json = json.loads(e.content.decode('utf-8'))
                                    log_error(f"API error details: {error_json}")
                                log_failed_url(url)
                                log_error("Exiting due to potential Gmail API limit has reached.")
                                exit(0)
                            case _:
                                log_error(f"Failed to apply on website {host}: {e}")
                                log_failed_url(url)
            
                stats["processed_sites"] += 1
                log_info(f"Finished processing website.")
                live.update(stats_panel(stats))
                await tab.close()
                set_host('')

            log_info("All websites have been processed.")


def stats_panel(stats: dict[str, int]) -> Padding:
    total_sites, processed_sites, sent_emails, submitted_forms = stats.values()

    applied = sent_emails + submitted_forms
    return Padding(
        Panel(
            f"Processed: {processed_sites} / {total_sites} websites\n"
            f"Emails Sent: {sent_emails}\n"
            f"Forms Submitted: {submitted_forms}\n"
            f"Total Applied: {applied}",
            title="Apply to Jobs Progress",
            border_style="white"
        ),
        (1, 0, 0, 0)
    )

if __name__ == "__main__":
    asyncio.run(main())