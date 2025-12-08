from random import randint
from typing import Literal
from playwright.sync_api import Page, TimeoutError, Locator
from playwright_utils import wait_for_network_idle

type CaptchaType = Literal['interstitial', 'turnstile']

def find_cf_challenge(page: Page) -> tuple[Locator, CaptchaType] | None:
    # Interstitial challenge indicator
    interstitial = page.title() == "Just a moment..."
    
    # Turnstile indicator
    turnstile = page.locator('.cf-turnstile').count()

    if not (interstitial or turnstile):
        return None

    try:
        # Random move helps to trigger loading actual captcha checkbox
        page.mouse.move(randint(0, 200), randint(0, 200))
        
        hidden = page.locator('input[name="cf-turnstile-response"]')
        hidden.wait_for(state="attached", timeout=10000)

        # Check if already solved
        if hidden.input_value():
            return None  # already solved
        
        # parent container of hidden input contains the captcha iframe
        # NOTE: We can't target checkbox via playwright without hack directly 
        # since it's under closed shadow DOM
        return hidden.locator("xpath=.."), 'turnstile' if turnstile else 'interstitial'
    except:
        print("Could not find Cloudflare challenge iframe.")
        return None


def solve_cf_challenge(captcha: Locator, 
                       type: CaptchaType = 'interstitial', 
                       attempts: int = 2) -> bool:
    page = captcha.page
    
    # TODO: track only relevant network requests
    # Wait until challenge is fully loaded and ready for interaction
    try:           
        wait_for_network_idle(page, timeout=10000, idle_time=3000)
    except:
        print("Timed out while waiting for Cloudflare challenge to be ready.")
        return False

    try:
        # Where to click, checkbox is 24x24 px and offset 16px from left side of iframe
        box = captcha.bounding_box()
        click_x = box['x'] + 16 + 24 / 2 # center of checkbox
        click_y = box['y'] + box['height'] / 2

        print("Clicking on Cloudflare challenge checkbox...")
        match type:
            case 'interstitial':
                with page.expect_event("load", timeout=30000):
                    page.mouse.click(click_x, click_y)

            case 'turnstile':
                page.mouse.click(click_x, click_y)
                wait_for_network_idle(page, timeout=10000, idle_time=3000)
    except:
        print("No navigation after clicking challenge, continuing...")

    captcha, type = find_cf_challenge(page)

    if not captcha:
        #print("Cloudflare challenge is solved.")
        return True
        
    print("Cloudflare challenge still present, retrying...")

    # Retry solving the challenge
    attempts -= 1
    if attempts > 0:
        return solve_cf_challenge(captcha, type, attempts)

    return False