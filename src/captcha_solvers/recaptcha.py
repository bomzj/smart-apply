from random import randint
from playwright.sync_api import Page, Locator, TimeoutError, Error
from playwright_utils import wait_until


def page_has_recaptcha(page: Page) -> bool:
    """Detect if ReCaptcha is present on the page."""
    markers = ['grecaptcha', 'recaptcha/api.js', 'recaptcha__', 'g-recaptcha']
    content = page.content()
    return any(m in content for m in markers)


def find_recaptcha_with_checkbox(container: Locator) -> Locator | None:
    """Find visible ReCaptcha V2 in the given container.
    Args:
        container (Locator): The locator representing the container to search within(usually a form).
    """
    iframe = container.locator('iframe[src*="recaptcha"]')

    try:
        iframe.wait_for(state="visible", timeout=15000)
        return iframe
    except TimeoutError as e:
        return None
    

def recaptcha_already_solved(recaptcha_iframe: Locator) -> bool:
    try:
        recaptcha_response = (
            recaptcha_iframe
            .locator('..')
            .locator('textarea[name="g-recaptcha-response"]')
            .input_value()
        )
        return True if recaptcha_response else False
    except Error as e:
        raise RuntimeError('ReCaptcha detection failed.') from e


def solve_recaptcha(recaptcha_iframe: Locator) -> bool:
    # NOTE: As of now, only ReCaptcha V2(checkbox) is supported
    # For V3 or invisible V2 ReCaptcha validation is triggered by some action (form submit)
    # so we can't tell beforehand whether recaptcha solved or not.
    # V3 and invisible V2 need human-like behavior (human-like mouse movement)
    
    # Behave like a human to pass invisible recaptcha (V3 and V2)
    # w, h = (vp := page.viewport_size)["width"], vp["height"]
    # page.mouse.move(randint(0, w), randint(0, h))

    # We don't know whether we have visible or invisible recaptcha 
    # So try to wait for visible recaptcha to appear and then click the checkbox
    
    try:
        print(f'Clicking on ReCaptcha checkbox.')
        recaptcha_iframe.click(position={"x": 12 + 27 / 2, "y": 78 / 2})
        print(f'Clicked on ReCaptcha checkbox.')
    except TimeoutError as e:
        print(f'Failed to click ReCaptcha within timeout.\n{e}')
        return False
        
    try:
        # Wait until recaptcha gets response asynchronously after click
        wait_until(lambda: recaptcha_already_solved(recaptcha_iframe), timeout=15000)
        return True
    except:
        print('Failed to solve ReCaptcha within timeout.')
        return False