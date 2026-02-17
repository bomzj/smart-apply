from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from smart_apply.browser_utils import wait_until
from smart_apply.logger import log_info

async def wait_until_cloudflare_resolved(tab: Tab):
    # Wait for Cloudflare challenge to be auto-solved by Pydoll if present
    if not await cf_challenge(tab):
        return 
    
    log_info(f"Cloudflare challenge detected, waiting to be solved...")
    await wait_until(lambda: no_cf_challenge(tab))
    log_info(f"Cloudflare challenge solved.")
    # After solving Cloudflare, reload(wait) the page to ensure all content is accessible
    await tab.go_to(await tab.current_url, timeout=30)


async def cf_challenge(tab: Tab) -> bool:
    # Interstitial challenge indicator
    title = await tab.title
    if title == "Just a moment...": 
        return True

    # Turnstile indicator
    turnstile = await tab.find(class_name='cf-turnstile', raise_exc=False)

    if not turnstile:
        return False  # No challenge detected
    
    hidden: WebElement = await tab.find(name='cf-turnstile-response', raise_exc=False)
    
    if hidden and hidden.value:
        return False  # Challenge solved, hidden input has value
    
    return True  # Challenge detected and not solved


async def no_cf_challenge(tab: Tab) -> bool:
    """Returns True if the Cloudflare challenge is no longer present."""
    return not await cf_challenge(tab)