
from random import randint
import time
from typing import Literal
from playwright.async_api import Page, TimeoutError, Locator
from collections.abc import Callable
import asyncio
import inspect


async def wait_for_network_idle(page: Page, timeout=30000, idle_time=1000):
    "Playwright page.wait_for_load_state('networkidle') simply doesn't work as expected"
    start_time = time.time()
    last_activity_time = time.time()
    
    def on_request_finished(request):
        nonlocal last_activity_time
        last_activity_time = time.time()
        #print(f"Request finished: {request.url}")

    page.on("requestfinished", on_request_finished)

    while True:
        await page.wait_for_timeout(1000)
        now = time.time()
        if now - start_time > timeout / 1000:
            print("Timeout reached while waiting for network to be idle.")
            break
        if now - last_activity_time >= idle_time / 1000:
            print("Network is idle.")
            break

    page.remove_listener("requestfinished", on_request_finished)


async def wait_until(condition: Callable[[], bool], timeout=30_000, interval=100):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        result = condition()
        if inspect.isawaitable(result):
            result = await result
        
        if result:
            return
        await asyncio.sleep(interval / 1000)
    raise TimeoutError("wait_until() timeout")