import time
from collections.abc import Callable
import asyncio
import inspect

from pydoll.browser.tab import Tab
from pydoll.exceptions import WaitElementTimeout
from smart_apply.logger import log_info, log_warning


def script_value(response: dict):
    """Extract the return value from a PyDoll execute_script response."""
    return response.get('result', {}).get('result', {}).get('value')


async def wait_for_network_idle(tab: Tab, timeout=30, idle_time=1):
    """Wait until no network activity occurs for `idle_time` seconds."""
    start_time = time.time()
    last_activity_time = time.time()

    network_was_enabled = tab.network_events_enabled
    if not network_was_enabled:
        await tab.enable_network_events()

    def on_request_finished(event):
        nonlocal last_activity_time
        last_activity_time = time.time()

    cb_id = await tab.on("Network.loadingFinished", on_request_finished)

    while True:
        await asyncio.sleep(1)
        now = time.time()
        if now - start_time > timeout:
            log_warning("Timeout reached while waiting for network to be idle.")
            break
        if now - last_activity_time >= idle_time:
            log_info("Network is idle.")
            break

    await tab.remove_callback(cb_id)
    if not network_was_enabled:
        await tab.disable_network_events()


async def wait_until(condition: Callable[[], bool], timeout=30, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = condition()
        if inspect.isawaitable(result):
            result = await result

        if result:
            return
        await asyncio.sleep(interval)
    raise WaitElementTimeout("wait_until() timeout")


async def site_available(tab: Tab) -> bool:
    current_url = await tab.current_url #await tab.execute_script("return window.location.href")
    if current_url.startswith("chrome-error://"):
        return False

    content = await tab.page_source
    error_signals = [
        "ERR_NAME_NOT_RESOLVED",
        "ERR_CONNECTION_REFUSED",
        "ERR_CONNECTION_TIMED_OUT",
        "ERR_INTERNET_DISCONNECTED",
        "This site can't be reached",
        "DNS_PROBE_FINISHED_NXDOMAIN",
    ]
    
    return not any(signal in content for signal in error_signals)