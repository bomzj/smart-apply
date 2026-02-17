from pathlib import Path
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
import pytest_asyncio


@pytest_asyncio.fixture(loop_scope="session")
async def browser():
    """Start Chrome once per session"""
    options = ChromiumOptions()
    #data_dir = Path(__file__).resolve().parent.parent / ".browser_session_data"
    #options.add_argument(f'--user-data-dir={data_dir}')
    options.add_argument('--start-maximized')
    async with Chrome(options=options) as browser:
        await browser.start()
        yield browser


@pytest_asyncio.fixture(loop_scope="session")
async def tab(browser):
    "fresh tab per test/function (most common and safe)"
    tab = await browser.new_tab()
    yield tab
    await tab.close()