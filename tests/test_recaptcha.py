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
    recaptcha = await recaptcha_within_container(container) if container else None
    assert bool(recaptcha) is checkbox_visible
    await tab.close()
    

@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/recaptcha/api2/demo",
        # (RECAPTCHA_V2_INVISIBLE_URL, False),
        # (RECAPTCHA_V3_URL, False),
    ]
)
async def test_solve_recaptcha_if_present(tab: Tab, url: str):
    await tab.go_to(url)
    form = await tab.find(tag_name='form')
    res = await solve_recaptcha_if_present(form, tab)
    assert res.ok == 'solved'
    solved_result = await recaptcha_solved(tab)
    assert solved_result
    
    await tab.close()