"""Low-level Selenium primitives shared by every flow.

The rules encoded here were learned the hard way against the live app:

* **Click with JS, not natively.** Toasts frequently float over controls and
  intercept native clicks. `js_click` dispatches the click directly on the
  element, bypassing whatever is on top of it.
* **Except antd Select dropdowns**, which only *open* on a real mousedown —
  a JS click does nothing. Use `native_click` for those. Being real, those
  clicks CAN be intercepted, so `native_click` first waits out the app's
  fullscreen loading overlay.
* **SweetAlert popups auto-dismiss in ~3 seconds.** Call `wait_for_swal`
  immediately after the click that triggers it; never sleep first.
* **Errors reuse the success popup container**, so a popup appearing is not
  proof of success — pass `expect="success"` to assert on its text.
"""

import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import locators as L

# Default seconds to wait for an element before giving up.
DEFAULT_TIMEOUT = 30


# --------------------------------------------------------------------------
# Finding elements
# --------------------------------------------------------------------------

def find(driver_or_wait, xpath, timeout=None):
    """Wait for an element to be present and return it.

    Accepts either a driver or an existing WebDriverWait, so callers can pass
    whichever they already have.
    """
    wait = _as_wait(driver_or_wait, timeout)
    return wait.until(EC.presence_of_element_located((By.XPATH, xpath)))


def find_clickable(driver_or_wait, xpath, timeout=None):
    """Wait until an element is present AND clickable, then return it."""
    wait = _as_wait(driver_or_wait, timeout)
    return wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))


def find_all(driver, xpath):
    """Return all matching elements right now — empty list if none. Never waits."""
    return driver.find_elements(By.XPATH, xpath)


def exists(driver, xpath):
    """True if at least one element matches right now. Never waits."""
    return bool(find_all(driver, xpath))


def _as_wait(driver_or_wait, timeout=None):
    if isinstance(driver_or_wait, WebDriverWait):
        return driver_or_wait
    return WebDriverWait(driver_or_wait, timeout or DEFAULT_TIMEOUT)


# --------------------------------------------------------------------------
# Interacting
# --------------------------------------------------------------------------

def js_click(driver, element):
    """Click via JS — immune to toasts and overlays intercepting the click.

    SVG icons (used for several of the app's icon-only buttons) don't inherit
    HTMLElement.click(), so those get a dispatched MouseEvent instead.
    """
    driver.execute_script(
        "var el = arguments[0];"
        "if (typeof el.click === 'function') { el.click(); }"
        "else { el.dispatchEvent(new MouseEvent('click',"
        " {bubbles: true, cancelable: true, view: window})); }",
        element,
    )


def click(driver, wait, xpath, scroll=False, settle=0, center=True, pause=1):
    """Find an element by xpath and JS-click it. The everyday click helper.

    `scroll` scrolls it into view first (`center=False` aligns to the top
    instead), pausing `pause` seconds to let the scroll finish. `settle` sleeps
    after the click, for panels that re-render.
    """
    element = find(wait, xpath)
    if scroll:
        scroll_into_view(driver, element, center=center)
        if pause:
            time.sleep(pause)
    js_click(driver, element)
    if settle:
        time.sleep(settle)
    return element


def wait_for_spinner(driver, timeout=60):
    """Wait until the app's fullscreen loading overlay is gone.

    It covers the whole viewport during saves and page refreshes, so a real
    mouse click landing while it is up hits the overlay instead of the target
    (ElementClickInterceptedException).
    """
    WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, L.FULLSCREEN_SPINNER_CSS))
    )


def native_click(driver, wait, xpath, scroll=True):
    """Click with a real mouse event.

    Required for antd Select dropdowns, which open on mousedown and ignore a
    JS-dispatched click. Being a real click, it is also the one kind that an
    overlay can intercept — hence the spinner wait that `js_click` doesn't need.
    """
    wait_for_spinner(driver)
    element = find(wait, xpath)
    if scroll:
        scroll_into_view(driver, element)
        time.sleep(0.5)
    element.click()
    return element


def type_text(driver, wait, xpath, text, clear=False, scroll=False):
    """Type into an input. `send_keys` focuses the field on its own — no click,
    which matters when a toast is briefly covering it."""
    element = find(wait, xpath)
    if scroll:
        scroll_into_view(driver, element)
    if clear:
        element.clear()
    element.send_keys(text)
    return element


def scroll_into_view(driver, element, center=True):
    """Scroll an element into view. At 1080p many controls sit below the fold."""
    if center:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    else:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)


def reveal(driver, element):
    """Force a visually-hidden input to render so it can be clicked."""
    driver.execute_script("arguments[0].style.display = 'block';", element)


# --------------------------------------------------------------------------
# SweetAlert confirmation popups
# --------------------------------------------------------------------------

def wait_for_swal(driver, label, timeout=DEFAULT_TIMEOUT, expect=None):
    """Wait for the confirmation popup after an action and return its text.

    Must be called immediately after the triggering click — these popups
    auto-dismiss, so any sleep beforehand can miss them entirely.

    `expect`: substring the text must contain (case-insensitive), e.g.
    'success'. Error messages share this container, so without `expect` a
    failure popup reads as a pass. Saves a screenshot + page source on timeout.
    """
    import pytest  # local import: ui.py stays usable outside a pytest run

    try:
        # Poll until the popup exists AND has rendered text — presence alone can
        # catch the container the instant it attaches, still empty.
        text = WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                f"var e = document.getElementById('{L.SWAL_CONTAINER_ID}');"
                "return e && e.textContent.trim() ? e.textContent.trim() : null;"
            )
        )
        print(f"  Popup after {label}: {text}")
        if expect and expect.lower() not in text.lower():
            driver.save_screenshot(f"failure_{label}.png")
            pytest.fail(f"Unexpected popup after {label}: '{text}' (expected to contain '{expect}')")
        return text
    except TimeoutException:
        driver.save_screenshot(f"failure_{label}.png")
        with open(f"failure_{label}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        pytest.fail(
            f"No confirmation popup after {label} within {timeout}s — "
            f"diagnostics saved to failure_{label}.png / failure_{label}.html"
        )
