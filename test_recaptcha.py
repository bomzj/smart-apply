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


@pytest.mark.parametrize(
    "url, expected",
    [
        (NO_RECAPTCHA_URL, False),
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, True),
        (RECAPTCHA_V3_URL, True),
    ]
)
def test_page_has_recaptcha(page, url, expected):
    page.goto(url)
    detected = page_has_recaptcha(page)
    assert detected is expected


@pytest.mark.parametrize(
    "url, checkbox_visible",
    [
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, False),
        (RECAPTCHA_V3_URL, False),
    ]
)
def test_find_recaptcha_with_checkbox(page: Page, url, checkbox_visible):
    page.goto(url)
    recaptcha = find_recaptcha_with_checkbox(page.locator('.g-recaptcha'))
    assert bool(recaptcha) is checkbox_visible
    

@pytest.mark.parametrize(
    "url, expected",
    [
        (RECAPTCHA_V2_URL, True),
        # (RECAPTCHA_V2_INVISIBLE_URL, False),
        # (RECAPTCHA_V3_URL, False),
    ]
)
def test_solve_recaptcha(page: Page, url, expected):
    page.goto(url)
    recaptcha = find_recaptcha_with_checkbox(page.locator('.g-recaptcha'))
    solved = solve_recaptcha(recaptcha)
    assert solved is expected