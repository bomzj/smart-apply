from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from smart_apply.logger import log_info

async def cf_challenge(tab: Tab) -> bool:
    log_info("Checking for Cloudflare challenge...")
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