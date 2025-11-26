from random import randint
import time
from playwright.sync_api import Page, TimeoutError
from collections.abc import Callable


def wait_for_network_idle(page: Page, timeout=30000, idle_time=1000):
    "Playwright page.wait_for_load_state('networkidle') simply doesn't work as expected"
    start_time = time.time()
    last_activity_time = time.time()
    
    def on_request_finished(request):
        nonlocal last_activity_time
        last_activity_time = time.time()
        #print(f"Request finished: {request.url}")

    page.on("requestfinished", on_request_finished)

    while True:
        page.wait_for_timeout(1000)
        now = time.time()
        if now - start_time > timeout / 1000:
            print("Timeout reached while waiting for network to be idle.")
            break
        if now - last_activity_time >= idle_time / 1000:
            print("Network is idle.")
            break

    page.remove_listener("requestfinished", on_request_finished)


def wait_until(condition: Callable[[], bool], timeout=30_000, interval=100):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval / 1000)
    raise TimeoutError("wait_until() timeout")


def detect_cloudflare_interstitial_challenge(page: Page) -> bool:
    title = page.title()
    if title == "Just a moment...":
        return True
    
    # Get page HTML content
    html = page.content()
    
    # Common markers for Cloudflare challenge pages
    markers = [
        "Enable JavaScript and cookies to continue",
        "_cf_chl_opt"
    ]
    
    for marker in markers:
        if marker.lower() in html.lower():
            return True
    
    return False


def solve_cloudflare_interstitial_challenge(page: Page, timeout: int = 60000) -> bool:
    start_time = time.time() * 1000
    
    # We need a loop since the challenge might require multiple clicks
    while (time.time() * 1000 - start_time) < timeout:
        # Get position of Cloudflare challenge iframe
        try:
            # 1. Move mouse to trigger challenge iframe to start loading
            viewport = page.viewport_size
            x = viewport["width"] // 2 + randint(-10, 10)
            y = viewport["height"] // 2 + randint(-10, 10)
            page.mouse.move(x , y)
            
            # 2. Wait until challenge iframe is inserted into DOM
            def iframe_inserted():
                return any(
                    "challenges.cloudflare.com/cdn-cgi" in f.url
                    for f in page.frames
                )            
            
            wait_until(iframe_inserted)
            
            # 3. Wait until challenge is fully loaded and ready for interaction
            wait_for_network_idle(page, timeout=10000, idle_time=3000)
            
            # 4. Closed shadow nodes are not accessible via playwright(without hack), 
            # so get parent container of challenge iframe
            captcha_block = page.locator('.main-content div[id]').first
            box = captcha_block.bounding_box()
        except:
            print("Could not find Cloudflare challenge iframe.")
            return False

        # Where to click, checkbox is 24x24 px and offset 16px from left side of iframe
        click_x = box['x'] + 16 + 24 / 2 # center of checkbox
        click_y = box['y'] + box['height'] / 2
   
        try:
            with page.expect_event("load", timeout=30000):
                print("Clicking on Cloudflare challenge checkbox...")
                page.mouse.click(click_x, click_y)
        except:
            print("No navigation after clicking challenge, continuing...")

        detected = detect_cloudflare_interstitial_challenge(page)

        if not detected:
            #print("Cloudflare challenge is solved.")
            return True
            
        print("Cloudflare challenge still present, retrying...")

    return False