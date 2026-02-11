import pytest
from smart_apply.captcha_solvers.recaptcha import *
from pydoll.elements.web_element import WebElement
from pydoll.browser.tab import Tab


NO_RECAPTCHA_URL = 'https://example.com'
RECAPTCHA_V2_URL = 'https://2captcha.com/demo/recaptcha-v2'
RECAPTCHA_V2_INVISIBLE_URL = 'https://2captcha.com/demo/recaptcha-v2-invisible'
RECAPTCHA_V3_URL = 'https://2captcha.com/demo/recaptcha-v3'

@pytest.mark.parametrize(
    "url, expected",
    [
        (NO_RECAPTCHA_URL, False),
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, True),
        (RECAPTCHA_V3_URL, True),
    ]
)
async def test_page_has_recaptcha(tab, url, expected):
    await tab.go_to(url)
    detected = await page_has_recaptcha(tab)
    assert detected is expected
    await tab.close()


@pytest.mark.parametrize(
    "url, checkbox_visible",
    [
        (RECAPTCHA_V2_URL, True),
        (RECAPTCHA_V2_INVISIBLE_URL, False),
        (RECAPTCHA_V3_URL, False),
    ]
)
async def test_find_recaptcha_with_checkbox(tab, url, checkbox_visible):
    await tab.go_to(url)
    container = await tab.query('.g-recaptcha', raise_exc=False)
    recaptcha = await find_recaptcha_with_checkbox(container) if container else None
    assert bool(recaptcha) is checkbox_visible
    await tab.close()
    

@pytest.mark.parametrize(
    "url, expected",
    [
        (RECAPTCHA_V2_URL, True),
        # (RECAPTCHA_V2_INVISIBLE_URL, False),
        # (RECAPTCHA_V3_URL, False),
    ]
)
async def test_solve_recaptcha(tab: Tab, url: str, expected: bool):
    await tab.go_to(url)
    
    container = await tab.query('.g-recaptcha', raise_exc=False)
    recaptcha = await find_recaptcha_with_checkbox(container)
    
    if expected:
        assert recaptcha is not None
        solved = await solve_recaptcha(recaptcha)
        assert solved
    else:
        assert recaptcha is None
    
    await tab.close()