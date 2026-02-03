import pytest
from typing import Literal
from playwright.async_api import async_playwright, Page
import pytest_asyncio
from recaptcha import *


NO_RECAPTCHA_URL = 'https://example.com'
RECAPTCHA_V2_URL = 'https://2captcha.com/demo/recaptcha-v2'
RECAPTCHA_V2_INVISIBLE_URL = 'https://2captcha.com/demo/recaptcha-v2-invisible'
RECAPTCHA_V3_URL = 'https://2captcha.com/demo/recaptcha-v3'


@pytest_asyncio.fixture(loop_scope="session")
async def playwright_instance():
    """Start Playwright once per session"""
    async with async_playwright() as pw:
        yield pw


@pytest_asyncio.fixture(loop_scope="session")
async def browser(playwright_instance):
    """Create one shared browser instance for the entire test session"""
    browser = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str('../../.browser_session_data'),
        headless=False,
        args=['--start-maximized'], # Maximize window
        no_viewport=True, # also required for maximized window
        slow_mo=50
    )
    yield browser
    await browser.close()

@pytest_asyncio.fixture(loop_scope="session")
async def page(browser):
    "fresh page per test/function (most common and safe)"
    page = await browser.new_page()
    yield page
    await page.close()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "url, expected",
    [
        (NO_RECAPTCHA_URL, False),
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, True),
        (RECAPTCHA_V3_URL, True),
    ]
)
async def test_page_has_recaptcha(page, url, expected):
    await page.goto(url)
    detected = await page_has_recaptcha(page)
    assert detected is expected


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "url, checkbox_visible",
    [
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, False),
        (RECAPTCHA_V3_URL, False),
    ]
)
async def test_find_recaptcha_with_checkbox(page: Page, url, checkbox_visible):
    await page.goto(url)
    recaptcha = find_recaptcha_with_checkbox(page.locator('.g-recaptcha'))
    assert bool(recaptcha) is checkbox_visible
    

@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "url, expected",
    [
        (RECAPTCHA_V2_URL, True),
        # (RECAPTCHA_V2_INVISIBLE_URL, False),
        # (RECAPTCHA_V3_URL, False),
    ]
)
async def test_solve_recaptcha(page: Page, url, expected):
    await page.goto(url)
    recaptcha = find_recaptcha_with_checkbox(page.locator('.g-recaptcha'))
    solved = await solve_recaptcha(recaptcha)
    assert solved is expected