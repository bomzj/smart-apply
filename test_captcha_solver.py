import tkinter
import pytest
from typing import Literal
from playwright.sync_api import sync_playwright, Page
from camoufox.sync_api import NewBrowser
from captcha_solver import *


# List of URLs that are known to trigger Cloudflare interstitial/Challenge
CLOUDFLARE_TEST_URLS = [
    "https://scrapingtest.com/cloudflare-challenge",
    "https://www.scrapingcourse.com/login/cf-antibot",
]


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


@pytest.mark.parametrize("url", CLOUDFLARE_TEST_URLS)
def test_cloudflare_interstitial_detection(url, page):
    #print(f"\nDetecting Cloudflare challenge on: {url}")
    page.goto(url)
    detected = detect_cloudflare_interstitial_challenge(page)
    assert detected, "Cloudflare interstitial challenge was not detected when expected."
    

@pytest.mark.parametrize("url", CLOUDFLARE_TEST_URLS)
def test_cloudflare_interstitial_solver(url, page):
    print(f"Navigating to {url}...")
    page.goto(url)
    solved = solve_cloudflare_interstitial_challenge(page, timeout=60000)
    assert solved, "Failed to solve Cloudflare interstitial challenge."