"""The embedded-sessions workflows, as readable step-by-step functions.

Embedded mode is a **client-level** flag, not a portal setting. The chain is:

    create_client(embedded=True)   # Organizations -> Clients -> Add a new client
    open_client_portals()          # appends ?embbedEnable=true&embbedPortalId=<id>
    -> the admin renders the SESSION LIST in place of the portal list
    open_embed_modal()             # 'Copy embed code' icon on a session row
    snippet()                      # read the generated <iframe> back

Everything the Embed Session modal does is pure client-side string building, so
the read-only snippet textarea is the single source of truth for the assertions
-- `snippet()` is called after every config change.

Locators live in `locators.py`, click/wait plumbing in `ui.py`.
"""

import json
import re
import time
from urllib.parse import parse_qs, quote, urlparse

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import locators as L
import ui


# ==========================================================================
# Organizations / clients
# ==========================================================================

def open_with_retry(driver, url, attempts=3, pause=5):
    """driver.get() with retries.

    The dev host intermittently drops a connection (net::ERR_CONNECTION_TIMED_OUT).
    Left unhandled that kills the login and every later test cascades into a
    skip, so a whole run is lost to a blip that a single retry rides out.
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            driver.get(url)
            return
        except WebDriverException as error:
            last_error = error
            print(f"  Navigation to {url} failed (attempt {attempt}/{attempts}): "
                  f"{str(error).splitlines()[0][:120]}")
            time.sleep(pause)
    raise last_error


def login_admin(driver, config, timeout=60):
    """Log into the admin account and return the welcome-header text.

    Deliberately the plain URL/EMAIL/PASSWORD rather than the _ORG ones the
    other suites use: only SUPER_ADMIN / ADMIN passes AdminGuard, and creating
    the embedded client is the first thing this suite does.
    """
    open_with_retry(driver, config["url"])
    driver.find_element(By.ID, L.EMAIL_INPUT_ID).send_keys(config["email"])
    driver.find_element(By.ID, L.PASSWORD_INPUT_ID).send_keys(config["password"])
    driver.find_element(By.CLASS_NAME, L.LOGIN_BTN_CLASS).click()

    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, L.WELCOME_HEADER_CLASS))
    ).text


def is_admin(driver, config):
    """True when the logged-in account can reach the Organizations page.

    /organization sits behind AdminGuard (SUPER_ADMIN / ADMIN) and silently
    redirects everyone else to /dashboard, so the only honest test is to go
    there and see where we land. Client creation needs this; entering embedded
    mode does not.
    """
    open_with_retry(driver, f"{config['url'].rstrip('/')}/organization")
    ui.wait_for_spinner(driver)
    return "/organization" in driver.current_url


def portal_id_from_url(driver):
    """The portal id out of an admin URL like /<portalId>/branding."""
    path = urlparse(driver.current_url).path.strip("/").split("/")
    return path[0] if path and path[0] else None


def enter_embedded_mode(driver, wait, config, portal_id):
    """Open the session list in embedded mode for `portal_id`.

    Embedded mode only needs embbedPortalId: the app resolves the client and
    organization from the portal's branding record (BrandingCheckUpdateMode).
    That matters because /organization/portal is behind the PORTAL admin guard
    while the client list that normally links here is behind the ADMIN one — so
    this is the route a portal-level account can actually take.
    """
    url = (
        f"{config['url'].rstrip('/')}/organization/portal"
        f"?embbedEnable=true&embbedPortalId={portal_id}"
    )
    # A modal left open by a failed test keeps its mask over the page; the
    # navigation below drops it, but only if nothing is mid-transition.
    time.sleep(0.5)
    drain_logs(driver)
    open_with_retry(driver, url)
    ui.wait_for_spinner(driver)
    time.sleep(2)  # the session list loads after the branding fetch resolves
    return query_params(driver)


def open_organization(driver, wait, config, org_name):
    """Go to the Organizations list and open `org_name`'s clients.

    Waits for the card click to actually land on the client list carrying
    organizationId. Without that wait the caller reads query_params() while the
    browser is still on /organization and gets organizationId=None, which then
    poisons every URL built from it further down.
    """
    open_with_retry(driver, f"{config['url'].rstrip('/')}/organization")
    ui.wait_for_spinner(driver)
    ui.type_text(driver, wait, L.ORG_SEARCH_INPUT, org_name)
    time.sleep(2)  # the org search is debounced
    ui.click(driver, wait, L.org_card_open(org_name))
    WebDriverWait(driver, 30).until(
        lambda d: "organizationId=" in d.current_url
    )
    ui.wait_for_spinner(driver)


def close_add_client_modal(driver, wait):
    """Dismiss the Add Client modal if it is open. No-op when it is not."""
    if ui.exists(driver, L.CLIENT_NAME_INPUT):
        ui.click(driver, wait, L.CLIENT_MODAL_CLOSE)
        time.sleep(1)


def find_client(driver, wait, client_name):
    """Search the client table for `client_name`. True if a row came back.

    Closes the Add Client modal first: it is a masked antd modal, so with it
    open the search box underneath cannot be typed into and the lookup would
    time out rather than report 'not found'.
    """
    close_add_client_modal(driver, wait)
    ui.type_text(driver, wait, L.CLIENT_SEARCH_INPUT, client_name, clear=True)
    time.sleep(2)  # the client search is debounced
    return ui.exists(driver, L.client_row_view_portals(client_name))


def open_add_client_modal(driver, wait):
    ui.click(driver, wait, L.ADD_CLIENT_BTN)
    ui.find(wait, L.CLIENT_NAME_INPUT)


def embed_switch_offered(driver):
    """True if the Add Client modal shows the 'Embedded Portal' switch."""
    return ui.exists(driver, L.EMBED_SWITCH_CHECKBOX)


def embed_switch_state(driver, wait):
    """The switch's current boolean state, read off the checkbox itself."""
    return ui.find(wait, L.EMBED_SWITCH_CHECKBOX).get_property("checked")


def set_embed_switch(driver, wait, on):
    """Flip 'Embedded Portal' to `on`. No-op when it already matches.

    The checkbox is visually replaced by a .slider span, so the input itself is
    not clickable -- the slider is what takes the click.
    """
    if embed_switch_state(driver, wait) == on:
        return
    ui.click(driver, wait, L.EMBED_SWITCH_SLIDER)
    time.sleep(0.5)


def create_client(driver, wait, name, embedded, language="English"):
    """Fill and submit the Add Client modal. Returns the confirmation text."""
    open_add_client_modal(driver, wait)
    ui.type_text(driver, wait, L.CLIENT_NAME_INPUT, name)

    ui.native_click(driver, wait, L.CLIENT_LANGUAGE_SELECTOR)
    ui.click(driver, wait, L.select_option(language))

    set_embed_switch(driver, wait, embedded)
    ui.click(driver, wait, L.CLIENT_SAVE_BTN)
    return ui.wait_for_swal(driver, f"create_client_{name}", expect="successfully added")


def open_client_portals(driver, wait, client_name):
    """Click 'View Portals' on a client row and return the resulting URL query.

    For an embedded client this is the step that switches the app into embedded
    mode -- the assertion target for the query-parameter cases.
    """
    ui.click(driver, wait, L.client_row_view_portals(client_name))
    wait.until(lambda d: "/organization/portal" in d.current_url)
    ui.wait_for_spinner(driver)
    return query_params(driver)


def query_params(driver):
    """The current URL's query string as a flat {name: value} dict."""
    return {k: v[0] for k, v in parse_qs(urlparse(driver.current_url).query).items()}


# ==========================================================================
# The embedded session list
# ==========================================================================

def ensure_embedded_list(driver, wait, config, portal_id):
    """Make sure the embedded session list is on screen, re-entering if not.

    Tests that navigate into Manage (or that fail part-way through it) would
    otherwise leave every later test with nothing to click, turning one failure
    into a cascade of skips.
    """
    if ui.exists(driver, L.SESSION_LIST_TITLE) and session_rows(driver, wait):
        return
    enter_embedded_mode(driver, wait, config, portal_id)


def session_rows(driver, wait):
    """Every session card on the list. Empty list when the client has none."""
    try:
        return wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, L.SUMMARY_CLASS))
        )
    except Exception:
        return []


def row_embed_button(row):
    """The row's 'Copy embed code' icon, or None when it isn't rendered."""
    found = row.find_elements(By.XPATH, L.SUMMARY_EMBED_BTN)
    return found[0] if found else None


def drain_logs(driver):
    """Empty the DevTools performance buffer.

    `performance: ALL` records every request the app makes, and the buffer is
    never trimmed on its own -- over a long suite it grows until the browser
    falls over ('invalid session id: session deleted...'). Reading the log is
    what clears it, so this is called whenever a fresh page is loaded: only the
    entries for the step under test need to survive.
    """
    try:
        driver.get_log("performance")
    except Exception:
        pass  # performance logging is not enabled on this driver


def api_response_body(driver, url_fragment, must_contain=None):
    """Parsed JSON body of a response whose URL contains `url_fragment`.

    Used to read what the app already fetched rather than calling the API
    directly: the API host differs per environment (and is baked into the
    bundle at build time), so re-deriving it here would mean hardcoding a dev
    URL that breaks on prod.

    `must_contain` names a key the body must carry. Several endpoints can match
    one fragment -- `/branding/<portalId>` matches both the portal's branding
    object and a list endpoint ending in the same id -- so the body is selected
    by shape, not by being the first or last URL to match. Returns None when
    nothing qualifies.
    """
    try:
        entries = driver.get_log("performance")
    except Exception:
        return None

    request_ids = []
    for entry in entries:
        try:
            message = json.loads(entry["message"])["message"]
        except Exception:
            continue
        if message.get("method") != "Network.responseReceived":
            continue
        if url_fragment in message["params"]["response"].get("url", ""):
            request_ids.append(message["params"]["requestId"])

    for request_id in request_ids:
        try:
            raw = driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": request_id}
            ).get("body", "")
            body = json.loads(raw)
        except Exception:
            continue
        if must_contain is None:
            return body
        if isinstance(body, dict) and body.get(must_contain) is not None:
            return body
    return None


def resolve_portal_org(driver, wait, config, portal_id):
    """The organization and client that own `portal_id`.

    Entering embedded mode makes the app fetch that portal's branding record,
    which carries organizationId and clientId — so the ids come from the app's
    own request rather than from a second, environment-specific API call.
    """
    enter_embedded_mode(driver, wait, config, portal_id)
    time.sleep(3)
    branding = api_response_body(driver, f"/branding/{portal_id}", must_contain="organizationId")
    if not branding:
        return {}
    return {
        "organizationId": branding.get("organizationId"),
        "clientId": branding.get("clientId"),
    }


def open_client_list(driver, wait, config, organization_id, organization_name=None):
    """Open an organization's client list by id, and return its name.

    Addressed by id rather than by searching the Organizations page, because the
    organization owning the configured portal is identified by id and its
    display name is only discoverable once the list has loaded.

    The name matters beyond display: the client rows build their 'View Portals'
    link from these query parameters, so opening the list without
    organizationName would drop it from the embedded URL further down. When the
    name is not supplied it is read off the loaded page and the list is opened
    again carrying it.
    """
    def load(name):
        open_with_retry(
            driver,
            f"{config['url'].rstrip('/')}/organization/client"
            f"?organizationId={organization_id}&organizationName={quote(name or '')}",
        )
        ui.wait_for_spinner(driver)
        ui.find(wait, "//div[contains(@class,'client-list-table-container')]")
        time.sleep(2)

    load(organization_name)
    if organization_name:
        return organization_name

    shown = ui.find_all(driver, "//div[contains(@class,'client-org-name')]")
    discovered = shown[0].text.strip() if shown else ""
    if discovered:
        load(discovered)
    return discovered


def failed_api_calls(driver, url_fragment):
    """(status, url, body) for each 4xx/5xx response whose URL contains `url_fragment`.

    The app swallows the create error (SessionsModal does `.catch((err) => err)`),
    so the UI shows nothing at all when the backend refuses. Reading the response
    straight off the DevTools log is the only way a failure message can say WHY
    rather than just 'no row appeared'. Needs the performance log enabled on the
    driver; returns [] when it is not.
    """
    try:
        entries = driver.get_log("performance")
    except Exception:
        return []

    failures = []
    for entry in entries:
        try:
            message = json.loads(entry["message"])["message"]
        except Exception:
            continue
        if message.get("method") != "Network.responseReceived":
            continue
        response = message["params"]["response"]
        if url_fragment not in response.get("url", "") or response.get("status", 200) < 400:
            continue
        body = ""
        try:
            body = driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": message["params"]["requestId"]}
            ).get("body", "")
        except Exception:
            pass
        failures.append((response["status"], response["url"], body[:500]))
    return failures


def create_session(driver, wait, title):
    """Create a session through the embedded-mode wizard.

    No type argument on purpose: an embedded session is always Video only. The
    wizard posts webcastType 'video' itself and the Manage dropdown offers
    nothing else, so there is nothing for a caller to choose.

    Embedded mode renders a single 'Create New Webcast' tile instead of the
    usual pair, and lays it out with different utility classes — so the tile is
    matched on its label here rather than on the class string the normal suite
    uses. Every wizard step after that screen is shared.
    """
    import webcast_flow as flow  # local import: avoids a circular import at module load

    ui.click(driver, wait, L.SCHEDULE_WEBCAST_BTN)
    ui.click(driver, wait, L.CREATE_NEW_WEBCAST_OPTION)
    ui.find(wait, L.WIZARD_TITLE_INPUT)
    drain_logs(driver)  # so failed_api_calls() sees only this creation's requests
    flow.run_new_webcast_wizard(driver, wait, title)


def open_manage(driver, wait, row):
    """Open a session's Manage page from its row."""
    ui.js_click(driver, row.find_element(By.XPATH, L.SUMMARY_MANAGE_BTN))
    ui.wait_for_spinner(driver)
    ui.find(wait, L.MANAGE_TAB)
    time.sleep(2)


def manage_tabs(driver):
    """The labels of the tabs on the Manage page, in order."""
    return [tab.text.strip() for tab in ui.find_all(driver, L.MANAGE_TAB)]


def webcast_type_options(driver, wait):
    """The labels offered by the Webcast details type dropdown.

    In embedded mode this is expected to be exactly ['Video only'] -- the type
    is fixed, so this exists to VERIFY that, never to pick a different one.
    There is deliberately no setter for the embedded type.

    Opened with a keypress rather than a click: antd Selects open on ARROW_DOWN
    as well as on mousedown, and the keypress cannot be intercepted by whatever
    happens to be floating over the panel. Leaves the dropdown closed again.
    """
    ui.click(driver, wait, L.WEBCAST_DETAILS_BTN)
    time.sleep(1)

    field = ui.find(wait, L.WEBCAST_TYPE_INPUT)
    ui.scroll_into_view(driver, field)
    time.sleep(0.5)
    field.send_keys(Keys.ARROW_DOWN)
    time.sleep(1)

    options = [
        option.get_attribute("title")
        for option in ui.find_all(driver, "//div[contains(@class,'ant-select-item-option')]")
    ]
    field.send_keys(Keys.ESCAPE)
    time.sleep(0.5)
    return [o for o in options if o]


def selected_webcast_type(driver, wait):
    """The type the session is currently set to."""
    return ui.find(wait, L.WEBCAST_TYPE_SELECTED).get_attribute("title")


def open_embed_modal(driver, wait, row):
    """Click a row's embed icon and wait for the Embed Session modal."""
    button = row_embed_button(row)
    assert button is not None, "No embed icon on this session row."
    ui.js_click(driver, button)
    ui.find(wait, L.EMBED_MODAL_TITLE)
    ui.find(wait, L.EMBED_SNIPPET_TEXTAREA)


def close_embed_modal(driver, wait):
    ui.click(driver, wait, L.EMBED_CLOSE_BTN)
    time.sleep(0.5)


# ==========================================================================
# The Embed Session modal
# ==========================================================================

def snippet(driver, wait):
    """The generated embed code.

    Read as the textarea's `value` property: antd's autosize textarea keeps the
    snippet in the DOM property only, so `.text` comes back empty.
    """
    return ui.find(wait, L.EMBED_SNIPPET_TEXTAREA).get_property("value")


def set_format(driver, wait, label):
    """Switch the output format. `label` is 'HTML' or 'React / JSX'."""
    ui.click(driver, wait, L.embed_format_option(label))
    time.sleep(0.5)


def advanced_open(driver):
    """True when the Advanced config panel is expanded."""
    return ui.exists(driver, L.EMBED_RESPONSIVE_CHECKBOX)


def set_advanced(driver, wait, on):
    """Show or hide the Advanced config panel. No-op when it already matches."""
    if advanced_open(driver) == on:
        return
    ui.click(driver, wait, L.EMBED_ADVANCED_SWITCH)
    time.sleep(0.5)


def set_responsive(driver, wait, on):
    checkbox = ui.find(wait, L.EMBED_RESPONSIVE_CHECKBOX)
    if checkbox.get_property("checked") != on:
        ui.js_click(driver, checkbox)
        time.sleep(0.5)


def _set_number(driver, wait, xpath, value):
    """Replace the contents of an antd InputNumber.

    `element.clear()` does not stick on these — antd re-renders the controlled
    value straight back, so a plain clear-then-type appends and you get '100640'
    where you wanted '640'. Selecting all first is what actually replaces it.
    antd then commits the number on blur, so the field is blurred explicitly
    before the snippet is read back.
    """
    field = ui.find(wait, xpath)
    ui.scroll_into_view(driver, field)
    field.send_keys(Keys.CONTROL, "a")
    field.send_keys(str(value))
    driver.execute_script("arguments[0].blur();", field)
    time.sleep(0.5)
    return field


def set_size(driver, wait, label, value):
    """Set the Width or Height value."""
    _set_number(driver, wait, L.embed_size_input(label), value)


def set_size_unit(driver, wait, label, unit):
    """Switch a Width/Height unit between 'px' and '%'."""
    ui.native_click(driver, wait, L.embed_size_unit_selector(label))
    ui.click(driver, wait, L.select_option(unit))
    time.sleep(0.5)


def set_permission(driver, wait, label, on):
    """Tick or untick one Permissions checkbox by its visible label."""
    checkbox = ui.find(wait, L.embed_permission_checkbox(label))
    if checkbox.get_property("checked") != on:
        ui.js_click(driver, checkbox)
        time.sleep(0.3)


def set_border_radius(driver, wait, value):
    _set_number(driver, wait, L.EMBED_BORDER_RADIUS_INPUT, value)


def set_advanced_select(driver, wait, label, option_title):
    """Pick an option in the 'Loading', 'Referrer policy' or 'Aspect ratio' select."""
    locator = (
        L.EMBED_ASPECT_SELECTOR if label == "Aspect ratio"
        else L.embed_advanced_selector(label)
    )
    ui.native_click(driver, wait, locator)
    ui.click(driver, wait, L.select_option(option_title))
    time.sleep(0.5)


def set_accessible_title(driver, wait, text):
    ui.type_text(driver, wait, L.EMBED_TITLE_INPUT, text, clear=True)
    time.sleep(0.5)


def attribute(snippet_text, name):
    """Pull `name="value"` out of a snippet. None when the attribute is absent.

    Deliberately string-based rather than an HTML parse: the JSX variant is not
    valid HTML, and the tests assert on the literal text the user copies.
    """
    match = re.search(rf'\b{re.escape(name)}\s*=\s*"([^"]*)"', snippet_text)
    return match.group(1) if match else None


def reset_modal(driver, wait):
    """Close and reopen the modal to get a clean DEFAULT_CONFIG.

    The component resets its config on close, so this is the cheapest way for a
    test to start from the documented defaults regardless of what ran before.
    """
    row = session_rows(driver, wait)[0]
    close_embed_modal(driver, wait)
    open_embed_modal(driver, wait, row)
