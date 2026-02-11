import pytest
from smart_apply.browser_utils import wait_until
from smart_apply.captcha_solvers.cloudflare_challenge import *


CLOUDFLARE_INTERSTITIAL_URL = 'https://2captcha.com/demo/cloudflare-turnstile-challenge'
CLOUDFLARE_TURNSTILE_URL = 'https://2captcha.com/demo/cloudflare-turnstile'


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (CLOUDFLARE_INTERSTITIAL_URL, True),
        (CLOUDFLARE_TURNSTILE_URL, True),
        ("https://example.com", False),
    ],
)
async def test_cf_challenge_detection(tab, url, expected):
    await tab.go_to(url)
    assert await cf_challenge(tab) is expected


@pytest.mark.parametrize("url", [
    CLOUDFLARE_INTERSTITIAL_URL,
    CLOUDFLARE_TURNSTILE_URL,
])
async def test_solve_cf_challenge(tab: Tab, url: str):
    await tab.enable_auto_solve_cloudflare_captcha()
    await tab.go_to(url)
    await wait_until(lambda: no_cf_challenge(tab))