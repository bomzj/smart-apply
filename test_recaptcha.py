import tkinter
import pytest
from typing import Literal
from playwright.sync_api import sync_playwright, Page
from camoufox.sync_api import NewBrowser
from recaptcha import *


NO_RECAPTCHA_URL = 'https://example.com'
RECAPTCHA_V2_URL = 'https://2captcha.com/demo/recaptcha-v2'
RECAPTCHA_V2_INVISIBLE_URL = 'https://2captcha.com/demo/recaptcha-v2-invisible'
RECAPTCHA_V3_URL = 'https://2captcha.com/demo/recaptcha-v3'

@pytest.fixture(scope="session")
def screen_resolution():
    """Get screen resolution once per test session"""
    root = tkinter.Tk()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return width, height


@pytest.fixture(scope="session")
def playwright_instance():
    """Start Playwright once per session"""
    pw = sync_playwright().start()
    yield pw
    pw.stop()


@pytest.fixture(scope="session")
def browser(playwright_instance, screen_resolution):
    """Create one shared browser instance for the entire test session"""
    width, height = screen_resolution
    browser = NewBrowser(
        playwright_instance,
        headless=False,
        humanize=True,
        window=(width, height),
        # uncomment if you want cookies/profile persistence
        # persistent_context=True,           
        # user_data_dir="./browser_session_data"
    )
    yield browser
    browser.close()

@pytest.fixture(scope="function")
def page(browser):
    "fresh page per test/function (most common and safe)"
    page = browser.new_page()
    yield page
    page.close()


def test_no_recaptcha_on_standard_page(page: Page):
    """Verify that find_recaptcha returns nothing on a clean page."""
    page.goto(NO_RECAPTCHA_URL)
    
    # We expect find_recaptcha to return None or a falsy value
    recaptcha = find_recaptcha(page.locator('body'))
    
    assert not recaptcha, f"Expected no reCAPTCHA on {NO_RECAPTCHA_URL}, but found: {recaptcha}"


@pytest.mark.parametrize(
    "url, expected",
    [
        (RECAPTCHA_V2_URL, "reCaptcha v2 not found."),
        (RECAPTCHA_V2_INVISIBLE_URL, "reCaptcha v2 invisible not found."),
        (RECAPTCHA_V3_URL, "reCaptcha v3 not found.")
    ]
)
def test_recaptcha_detection(page, url, expected):
    page.goto(url)
    loc = page.locator('.g-recaptcha')
    recaptcha = find_recaptcha(loc)
    assert recaptcha, expected
    

@pytest.mark.parametrize(
    "url",
    [
        RECAPTCHA_V2_URL,
        #RECAPTCHA_V2_INVISIBLE_URL,
        #RECAPTCHA_V3_URL,
    ]
)
def test_recaptcha_solver(page, url):
    page.goto(url)
    recaptcha = find_recaptcha(page)
    solved = solve_recaptcha(recaptcha)
    assert solved
