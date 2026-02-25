import time
from collections.abc import Callable
import asyncio
import inspect

from pydoll.browser.tab import Tab
from pydoll.exceptions import WaitElementTimeout
from smart_apply.logger import log_debug, log_info, log_warning


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
            log_debug("Network is idle.")
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


async def accept_cookie_consent(tab: Tab) -> bool:
    """Find and click a cookie consent accept button. Returns True if clicked."""

    FIND_ACCEPT_BUTTON_JS = """
    function findAcceptCookieButton(container) {
      const acceptKeywords = ['accept', 'allow', 'agree'];
      const bannerKeywords = ['cookie', 'privacy'];
      const candidates = Array.from(container.querySelectorAll(
        'button, a, [role="button"], input[type="button"], input[type="submit"]'
      ));

      for (const el of candidates) {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;

        const btnText = (el.innerText || '').toLowerCase().trim().split(/\s+/);
        if (!btnText.some(w => acceptKeywords.includes(w))) continue;

        let parent = el.parentElement;
        while (parent && parent !== container.parentElement) {
          const parentText = (parent.innerText || '').toLowerCase();
          if (bannerKeywords.some(kw => parentText.includes(kw))) return el;
          parent = parent.parentElement;
        }
      }

      return null;
    }
    """

    CLICK_ACCEPT_DOM_JS = FIND_ACCEPT_BUTTON_JS + """
        const btn = findAcceptCookieButton(this);
        if (btn) { btn.click(); return true; }
        return false;
    """

    CLICK_ACCEPT_SHADOW_JS = FIND_ACCEPT_BUTTON_JS + """
        const root = this.shadowRoot;
        if (!root) return false;
        const btn = findAcceptCookieButton(root);
        if (btn) { btn.click(); return true; }
        return false;
    """

    # 1. Traverse the normal DOM to find cookie banner and click accept button
    body = await tab.query("body")
    result = await body.execute_script(CLICK_ACCEPT_DOM_JS, return_by_value=True)
    clicked = script_value(result)
    if clicked:
        return True

    # 2. If not found, check for shadow roots (e.g. Usercentrics)
    shadow_roots = await tab.find_shadow_roots()
    for shadow_root in shadow_roots:
        host = shadow_root.host_element
        if not host:
            continue
        result = await host.execute_script(CLICK_ACCEPT_SHADOW_JS, return_by_value=True)
        clicked = script_value(result)
        if clicked:
            return True

    # 3. If still not found, check for iframes (e.g. TrustArc)
    iframes = await tab.query('iframe', find_all=True)
    for iframe in iframes:
        if not await iframe.is_visible():
            continue
        iframe_body = await iframe.query('body')
        result = await iframe_body.execute_script(CLICK_ACCEPT_DOM_JS, return_by_value=True)
        clicked = script_value(result)
        if clicked:
            return True

    return False