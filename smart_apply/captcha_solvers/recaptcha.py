from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from pydoll.exceptions import WaitElementTimeout, ElementNotFound
from smart_apply.browser_utils import wait_until, script_value
from smart_apply.logger import log_info, log_error


async def page_has_recaptcha(tab: Tab) -> bool:
    """Detect if ReCaptcha is present on the page."""
    markers = ['grecaptcha', 'recaptcha/api.js', 'recaptcha__', 'g-recaptcha']
    content = await tab.page_source
    return any(m in content for m in markers)


async def find_recaptcha_with_checkbox(container: WebElement) -> WebElement | None:
    """Find visible ReCaptcha V2 in the given container.
    Args:
        container (WebElement): The container to search within (usually a form).
    """
    try:
        iframe = await container.query('iframe[src*="recaptcha"]', timeout=15)
        await iframe.wait_until(is_visible=True, timeout=15)
        return iframe
    except (WaitElementTimeout, ElementNotFound):
        return None
    

async def recaptcha_already_solved(recaptcha_iframe: WebElement) -> bool:
    try:
        parent = await recaptcha_iframe.get_parent_element()
        textarea = await parent.query(
            'textarea[name="g-recaptcha-response"]', raise_exc=False
        )
        if not textarea:
            return False
        result = await textarea.execute_script("return this.value", return_by_value=True)
        value = script_value(result)
        return bool(value)
    except Exception as e:
        raise RuntimeError('Invalid ReCaptcha iframe.') from e


async def solve_recaptcha(recaptcha_iframe: WebElement) -> bool:
    # NOTE: As of now, only ReCaptcha V2(checkbox) is supported
    # For V3 or invisible V2 ReCaptcha validation is triggered by some action (form submit)
    # so we can't tell beforehand whether recaptcha solved or not.
    # V3 and invisible V2 need human-like behavior (human-like mouse movement)
    
    try:
        log_info('Clicking on ReCaptcha checkbox.')
        checkbox = await recaptcha_iframe.query('.recaptcha-checkbox-border', raise_exc=False)  # Wait until recaptcha loads
        await checkbox.click()
        log_info('Clicked on ReCaptcha checkbox.')
    except Exception as e:
        log_error(f'Failed to click ReCaptcha within timeout.\n{e}')
        return False
        
    try:
        # Wait until recaptcha gets response asynchronously after click
        await wait_until(lambda: recaptcha_already_solved(recaptcha_iframe), timeout=15)
        return True
    except Exception:
        log_error('Failed to solve ReCaptcha within timeout.')
        return False