from random import randint
from playwright.sync_api import Page, Locator
from playwright_utils import wait_until


def find_recaptcha(page: Page):
    markers = ['grecaptcha', 'recaptcha/api.js', 'recaptcha__', 'g-recaptcha']
    content = page.content()
    recaptcha_found = any(m in content for m in markers)
   
    if not recaptcha_found:
        return None
    
    try:
        response_input = page.locator('textarea[name="g-recaptcha-response"]')
        response_input.wait_for(state="attached", timeout=10000)

        # Check if already solved
        if response_input.input_value():
            return None  # already solved
        
        return response_input
    except:
        print("Could not find ReCaptcha.")
        return None


def solve_recaptcha(recaptcha_response: Locator) -> bool:
    page = recaptcha_response.page

    # NOTE: As of now, only ReCaptcha V2(checkbox) is supported
    # For V3 or invisible V2 ReCaptcha validation is triggered by some action (form submit)
    # so we can't tell beforehand whether recaptcha solved or not.
    # V3 and invisible V2 need human-like behavior which is done by camoufox browser already.
    
    # Behave like a human to pass invisible recaptcha
    # w, h = (vp := page.viewport_size)["width"], vp["height"]
    # page.mouse.move(randint(0, w), randint(0, h))

    # We don't know whether we have visible or invisible recaptcha 
    # So try to wait for visible recaptcha to appear and then click the checkbox
    iframe = recaptcha_response.locator('..').locator('iframe[src*="recaptcha"]')
    try:
        iframe.wait_for(state="attached")
    except:
        pass

    if iframe.count():
        # Where to click, checkbox is 27x27 px and offset 12px from left side of iframe
        box = iframe.bounding_box()
        click_x = box['x'] + 12 + 27 / 2 # center of checkbox
        click_y = box['y'] + box['height'] / 2
        print(f'Clicking on ReCaptcha checkbox.')
        page.mouse.click(click_x, click_y)
        
    try:
        # Wait until recaptcha gets response
        wait_until(lambda: recaptcha_response.input_value(), timeout=10000)
        return True
    except:
        print('Failed to solve ReCaptcha within timeout.')
        return False