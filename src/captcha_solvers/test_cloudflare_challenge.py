import tkinter
import pytest
from typing import Literal
from playwright.sync_api import sync_playwright, Page
from cloudflare_challenge import *


CLOUDFLARE_INTERSTITIAL_URL = 'https://2captcha.com/demo/cloudflare-turnstile-challenge'
CLOUDFLARE_TURNSTILE_URL = 'https://2captcha.com/demo/cloudflare-turnstile'


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
    browser = playwright_instance.chromium.launch(
        headless=False,
        args=[f"--window-size={width},{height}"]
    )
    yield browser
    browser.close()

@pytest.fixture(scope="function")
def page(browser, screen_resolution):
    "fresh page per test/function (most common and safe)"
    width, height = screen_resolution
    page = browser.new_page(viewport={"width": width, "height": height})
    yield page
    page.close()


def test_cloudflare_interstitial_detection(page):
    page.goto(CLOUDFLARE_INTERSTITIAL_URL)
    _, type = find_cf_challenge(page)
    assert type == "interstitial", "Cloudflare interstitial challenge was not detected when expected."
    

def test_cloudflare_turnstile_detection(page):
    page.goto(CLOUDFLARE_TURNSTILE_URL)
    _, type = find_cf_challenge(page)
    assert type == "turnstile", "Cloudflare turnstile challenge was not detected when expected."


def test_cloudflare_interstitial_solver(page):
    page.goto(CLOUDFLARE_INTERSTITIAL_URL)
    captcha, type = find_cf_challenge(page)
    solved = solve_cf_challenge(captcha, type)
    assert solved, "Failed to solve Cloudflare interstitial challenge."


def test_cloudflare_turnstile_solver(page):
    page.goto(CLOUDFLARE_TURNSTILE_URL)
    captcha, type = find_cf_challenge(page)
    solved = solve_cf_challenge(captcha, type)
    assert solved, "Failed to solve Cloudflare turnstile challenge."