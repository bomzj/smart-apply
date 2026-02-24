import pytest
import asyncio
from pydoll.browser.tab import Tab
from smart_apply.browser_utils import accept_cookie_consent, script_value

# --- Live Target Data ---

# We use sites known to strictly enforce GDPR/CCPA banners via major CMPs
LIVE_TARGETS = [
    ("https://www.cloudflare.com/", True),
    ("https://www.cookiebot.com/", True),
    ("https://www.usercentrics.com/", True), # uses open shadow root
    ("https://www.sqli.com/", True),
    ('https://www.netflix.com/', True),
    ('https://www.nytimes.com/', True),
    ('https://www.speedtest.net/', True),
    ('https://www.w3.org/', False),  # W3C doesn't have a cookie banner
    ('https://example.com/', False),  # Example domain with no banner,
    ('https://www.twilio.com/', True) # Twilio uses iframe banner
]


@pytest.mark.parametrize("url, expected", LIVE_TARGETS)
async def test_live_cookie_banners(tab: Tab, url: str, expected: bool):
    """
    Tests the heuristic algorithm against live production websites.
    """
    
    # 1. Navigate to the live URL
    await tab.go_to(url)
    
    # 2. Crucial: Wait for third-party CMP scripts to load and render the banner.
    # Real banners are rarely in the initial HTML payload; they are injected by JS.
    await asyncio.sleep(4) 
    
    # 3. Execute our heuristic algorithm
    banner_clicked = await accept_cookie_consent(tab)
    
    # 4. Assert that the algorithm successfully found and interacted with a button
    assert banner_clicked is expected
    
    # 5. Verify the banner is actually gone from the viewport
    # We give the site a moment to process the click and play its closing animation
    await asyncio.sleep(1)
    
    # Re-run the heuristic to ensure no high-scoring banner containers remain
    # (If it returns False, it means the banner was successfully dismissed)
    banner_still_present = await accept_cookie_consent(tab)
    
    assert banner_still_present is False