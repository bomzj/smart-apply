import pytest
from typing import Literal
from playwright.async_api import async_playwright, Page
import pytest_asyncio
from cloudflare_challenge import *


CLOUDFLARE_INTERSTITIAL_URL = 'https://2captcha.com/demo/cloudflare-turnstile-challenge'
CLOUDFLARE_TURNSTILE_URL = 'https://2captcha.com/demo/cloudflare-turnstile'


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
async def test_cloudflare_interstitial_detection(page):
    await page.goto(CLOUDFLARE_INTERSTITIAL_URL)
    _, type = await find_cf_challenge(page)
    assert type == "interstitial", "Cloudflare interstitial challenge was not detected when expected."
    

@pytest.mark.asyncio(loop_scope="session")
async def test_cloudflare_turnstile_detection(page):
    await page.goto(CLOUDFLARE_TURNSTILE_URL)
    _, type = await find_cf_challenge(page)
    assert type == "turnstile", "Cloudflare turnstile challenge was not detected when expected."


@pytest.mark.asyncio(loop_scope="session")
async def test_cloudflare_interstitial_solver(page):
    await page.goto(CLOUDFLARE_INTERSTITIAL_URL)
    captcha, type = await find_cf_challenge(page)
    solved = await solve_cf_challenge(captcha, type) # Assuming solve_cf_challenge is async too
    assert solved, "Failed to solve Cloudflare interstitial challenge."


@pytest.mark.asyncio(loop_scope="session")
async def test_cloudflare_turnstile_solver(page):
    await page.goto(CLOUDFLARE_TURNSTILE_URL)
    captcha, type = await find_cf_challenge(page)
    solved = await solve_cf_challenge(captcha, type) # Assuming solve_cf_challenge is async too
    assert solved, "Failed to solve Cloudflare turnstile challenge."