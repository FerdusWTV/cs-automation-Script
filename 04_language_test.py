"""Multi-language end-to-end suite for ConnectStudio 2.0 (ShareStudio admin).

Covers the three levels at which a language can be chosen:

  1. CLIENT  - one default language per client (`AddClientModal.js`), which
     cascades down to every portal on that client.
  2. PORTAL  - any number of ADDITIONAL languages on Branding
     (`Branding/LanguageDropdown`), always excluding the client's default one.
     Those languages then drive the per-language content selectors (Home, menu
     labels, agenda, resources) and the per-language URLs on Publish.
  3. SESSION - further additional languages per session
     (`CustomEventLanguageECDN.js`), filtered only by the session's own default
     language, so a session may use languages the portal does not list.

TestRail: project 2 (Connect Studio) / suite 7 (Admin Panel), section 47
'Language'. Each test carries `@pytest.mark.testrail(...)` for the case(s) it
covers; run with `--testrail-out=` and upload with `testrail_upload.py`.

Safety contract - this suite NEVER touches pre-existing data:
  * `test_02` snapshots the existing clients (CLIENT_BASELINE).
  * Every client and portal this run creates carries the run-stamped prefix.
  * `_delete_portal_card` refuses any portal name this run did not create.
  * The admin UI has no client delete, so the created client is left behind on
    purpose (same as 01_client_test.py) - its name is unique per run.
  * The session-level test is READ-ONLY and saves nothing.
  * `test_16` asserts the client baseline is unchanged at the end.

Order matters: tests are numbered and share one browser session (module-scoped
`driver`), so run the file as a whole rather than cherry-picking with `-k`.

Run:
    ..\\venv\\Scripts\\pytest -v 04_language_test.py --env=dev --html=report.html --self-contained-html
    ..\\venv\\Scripts\\pytest -v 04_language_test.py --base-url=http://localhost:3000
    ..\\venv\\Scripts\\pytest -v 04_language_test.py --testrail-out=language_results.json

Optional .env / environment overrides:
    LANG_ORG            organization to open, found via the org search bar (admin
                        accounts only - an org user stays in its own org; default: first card)
    LANG_DEFAULT        client default language  (default: Italian)
    LANG_ADDITIONAL     comma-separated additional languages (default: English,German)
    LANG_SESSION_URL    full URL of an EXISTING session page. Without it the
                        session-level test is skipped rather than creating a
                        webcast just to read two checkboxes.
    PORTAL_LOGO_PATH    header logo under 200 KB (falls back to HEADSHOT_PATH)
"""

import os
import time
import uuid

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import org_flow
import ui

# ----------------------- LANGUAGE DATA --------------------

# `custom/enums/DefaultLanguages.js` - the CLIENT default-language dropdown.
CLIENT_LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "German": "de",
    "Italian": "it",
    "French": "fr",
    "Swedish": "sv",
    "Danish": "da",
    "Finish": "fi",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Simplified Chinese": "zh",
    "Traditional Chinese": "zh_TW",
}

# `components/Branding/LanguageDropdown/languages.js` - the PORTAL additional
# dropdown. Deliberately compared against the list above: the two disagree
# (Danish vs Turkish), which is TestRail C917.
PORTAL_LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "German": "de",
    "Italian": "it",
    "French": "fr",
    "Swedish": "sv",
    "Turkish": "tr",
    "Finish": "fi",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Simplified Chinese": "zh",
    "Traditional Chinese": "zh_TW",
}

# ----------------------- RUN STATE ------------------------

RUN_ID = uuid.uuid4().hex[:6]
CLIENT_NAME = f"Automated Lang Client {RUN_ID}"
PORTAL_PREFIX = f"Automated Lang Portal {RUN_ID}"
PORTAL_NAME = f"{PORTAL_PREFIX} - 001"

DEFAULT_LANGUAGE = os.getenv("LANG_DEFAULT", "Italian")
ADDITIONAL_LANGUAGES = [
    name.strip()
    for name in os.getenv("LANG_ADDITIONAL", "English,German").split(",")
    if name.strip()
]

# Portal names this run created - the ONLY names delete is ever allowed to target.
CREATED_PORTALS = set()
# Client names that existed before this run - must be intact when we finish.
CLIENT_BASELINE = []
# Client-list URL captured in test_02 so later tests can return to it.
CLIENT_LIST_URL = {"url": None}
# The organization the baseline was taken under.
CONTEXT = {"org": None}
# The portal this run builds, filled in by test_10.
PORTAL = {"id": None, "url": None}

MODAL = "//div[contains(@class,'add-client-modal')][contains(@class,'ant-modal-wrap')]"
OPEN_DROPDOWN = ("//div[contains(@class,'ant-select-dropdown') and "
                 "not(contains(@class,'ant-select-dropdown-hidden'))]")


def _code(name):
    """Language code for a display name, from whichever of the two lists has it."""
    return PORTAL_LANGUAGES.get(name) or CLIENT_LANGUAGES[name]


DEFAULT_CODE = _code(DEFAULT_LANGUAGE)
ADDITIONAL_CODES = [_code(name) for name in ADDITIONAL_LANGUAGES]


# ----------------------- FIXTURES ------------------------

@pytest.fixture(scope="module")
def driver():
    """One Chrome session shared by the whole ordered suite."""
    options = Options()
    if os.getenv("HEADLESS", "").lower() in ("1", "true", "yes"):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-allow-origins=*")

    driver_path = os.getenv("DRIVER")
    if driver_path and os.path.exists(driver_path):
        drv = webdriver.Chrome(service=Service(driver_path), options=options)
    else:
        drv = webdriver.Chrome(options=options)
    drv.implicitly_wait(5)
    yield drv
    drv.quit()


@pytest.fixture(scope="module")
def base_url(request, config):
    """`--base-url` wins, else the env's admin URL from conftest's config."""
    return (request.config.getoption("--base-url") or config["url_org"]).rstrip("/")


# ----------------------- HELPERS -------------------------

def _wait(driver, timeout=30):
    return WebDriverWait(driver, timeout)


def _dump(driver, label):
    """Screenshot + page source next to the report, for post-mortem on failure."""
    driver.save_screenshot(f"failure_{label}.png")
    with open(f"failure_{label}.html", "w", encoding="utf-8") as fh:
        fh.write(driver.page_source)
    return f"diagnostics saved to failure_{label}.png / failure_{label}.html"


def _click(driver, element):
    """JS click - antd overlays and swal toasts routinely intercept native clicks."""
    ui.js_click(driver, element)


# --- antd Select ----------------------------------------------------------
# antd opens a dropdown on a real mousedown against `.ant-select-selector`; a
# JS .click() on the wrapper does nothing. Every helper below therefore uses a
# native click to OPEN and a JS click to CHOOSE (the option can be covered by a
# toast, the selector never is).

def _select_container(driver, xpath, timeout=30):
    container = _wait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
    time.sleep(1)
    return container


def _open_select(driver, xpath):
    """Open the antd Select at `xpath` and return its container element."""
    container = _select_container(driver, xpath)
    container.find_element(By.CSS_SELECTOR, ".ant-select-selector").click()
    _wait(driver).until(EC.presence_of_element_located((By.XPATH, OPEN_DROPDOWN)))
    time.sleep(1)
    return container


def _dropdown_options(driver):
    """Labels currently listed in the open dropdown, in render order."""
    return [
        element.text.strip()
        for element in driver.find_elements(
            By.XPATH, f"{OPEN_DROPDOWN}//div[contains(@class,'ant-select-item-option-content')]"
        )
        if element.text.strip()
    ]


def _dropdown_empty_text(driver):
    """Text of the open dropdown's empty state, or '' when options are listed."""
    empty = driver.find_elements(By.XPATH, f"{OPEN_DROPDOWN}//div[contains(@class,'ant-select-item-empty')]")
    return empty[0].text.strip() if empty else ""


def _choose_option(driver, label):
    """Click an option by exact label in the open dropdown.

    antd virtualizes long option lists - only the rows in view exist in the DOM -
    so a label further down (e.g. a client created this run) is scrolled into
    existence before waiting on it.
    """
    xpath = (f"{OPEN_DROPDOWN}//div[contains(@class,'ant-select-item-option')]"
             f"[normalize-space()='{label}']")
    for _ in range(50):
        if driver.find_elements(By.XPATH, xpath):
            break
        holders = driver.find_elements(
            By.XPATH, f"{OPEN_DROPDOWN}//div[contains(@class,'rc-virtual-list-holder')]"
        )
        if not holders:
            break
        at_end = driver.execute_script(
            "const h = arguments[0], before = h.scrollTop;"
            "h.scrollTop += h.clientHeight * 0.8;"
            "return h.scrollTop === before;",
            holders[0],
        )
        time.sleep(0.3)
        if at_end:
            break
    option = _wait(driver).until(EC.presence_of_element_located((By.XPATH, xpath)))
    _click(driver, option)
    time.sleep(1)


def _close_dropdown(driver):
    """Dismiss an open dropdown without choosing anything."""
    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.5)


def _selected_tags(driver, xpath):
    """Tag labels currently shown inside a multi-select."""
    container = _select_container(driver, xpath)
    return [
        element.text.strip()
        for element in container.find_elements(
            By.CSS_SELECTOR, ".ant-select-selection-item-content"
        )
        if element.text.strip()
    ]


def _search_in_select(driver, xpath, term):
    """Type into an OPEN select's search box to filter its options."""
    container = _select_container(driver, xpath)
    container.find_element(By.CSS_SELECTOR, "input.ant-select-selection-search-input").send_keys(term)
    time.sleep(1.5)


def _pick_antd_option(driver, placeholder, wanted=None, scope=""):
    """Open the Select carrying `placeholder` and choose `wanted` (or the first).

    `scope` prefixes the container xpath, so the same helper works inside the
    client modal and on the full-page branding form.
    """
    xpath = (f"{scope}//div[contains(@class,'ant-select')]"
             f"[.//span[normalize-space()='{placeholder}']]")
    _open_select(driver, xpath)
    if wanted:
        _choose_option(driver, wanted)
        return wanted
    options = _dropdown_options(driver)
    assert options, f"'{placeholder}' dropdown had no options"
    _choose_option(driver, options[0])
    return options[0]


# --- branding page rows ---------------------------------------------------

def _branding_row(label, legacy_label=None):
    """XPath of the Branding field whose label is `label`.

    The redesigned page wraps each field in `.bf-field` with a `.bf-label`;
    the legacy `.branding-logo-portal` row (with its own wording) is kept as a
    fallback so the suite still runs against an un-redeployed environment.
    """
    return (f"(//div[contains(@class,'bf-field')][label[normalize-space()='{label}']]"
            f" | //div[contains(@class,'branding-logo-portal')]"
            f"[div[normalize-space()='{legacy_label or label}']])")


DEFAULT_LANGUAGE_INPUT = f"{_branding_row('Default Language')}//input"
ADDITIONAL_LANGUAGE_SELECT = (f"{_branding_row('Additional Languages', 'Select Additional Language')}"
                              "//div[contains(@class,'ant-select')]")

# Redesigned Home page: the selector sits in the header (`.bf-header-select`).
# Legacy pages: a bare <label> followed by the Select, with no wrapper class.
HOME_LANGUAGE_SELECT = ("(//div[contains(@class,'bf-header-select')]//div[contains(@class,'ant-select')]"
                        " | //label[normalize-space()='Select Language']"
                        "/following::div[contains(@class,'ant-select')])[1]")


# --- lists ----------------------------------------------------------------

def _client_names(driver):
    """Names of every client row currently rendered on the client table."""
    names = []
    for row in driver.find_elements(By.CSS_SELECTOR, ".client-list-table-container tbody tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) == 3 and cells[0].text.strip():
            names.append(cells[0].text.strip())
    return names


def _open_client_list(driver):
    """Navigate to the client list captured in test_02 and wait for it to render."""
    url = CLIENT_LIST_URL["url"]
    assert url, "Client list URL not captured - test_02 must run first."
    driver.get(url)
    _wait(driver).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".client-list-table-container")
    ))
    time.sleep(3)


def _search_client_list(driver, term):
    """Type `term` into the client-list search box (debounce, then a refetch).

    The page only refetches for an empty string or 2+ characters, so short terms
    are deliberately not supported here.
    """
    box = _wait(driver).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".client-list-table-container input.search-input")
    ))
    # Clear via keystrokes: .clear() bypasses React's onChange, so the list would
    # stay filtered on the previous term.
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys(Keys.BACKSPACE)
    time.sleep(2)
    if term:
        box.send_keys(term)
    time.sleep(4)


def _open_add_client_modal(driver):
    """Click 'Add a new client' and wait for the modal. Idempotent.

    A test that fails before its own close step would otherwise leave the mask
    up, and the button underneath it is unclickable - turning one failure into a
    cascade across every test that follows.
    """
    already_open = driver.find_elements(
        By.XPATH, f"{MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']"
    )
    if already_open:
        return
    add_btn = _wait(driver).until(EC.presence_of_element_located((
        By.XPATH, "//div[@class='add-client-modal']//button[contains(@class,'save-button')]",
    )))
    _click(driver, add_btn)
    _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']")
    ))
    time.sleep(1)


def _close_add_client_modal(driver):
    """Close the client modal if it is still open, so the next test starts clean.

    The header holds two icon-only controls (back, close) - either one toggles
    the modal shut. They're react-icons SVGs, hence the `name()` predicate.
    """
    icons = driver.find_elements(
        By.XPATH, f"{MODAL}//div[contains(@class,'ant-modal-header')]//*[name()='svg']"
    )
    if not icons:
        return
    _click(driver, icons[-1])
    _wait(driver).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(2)


def _client_name_input(driver):
    """The client modal's name field - a Formik <Field name="name">, with no id."""
    return _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//input[@name='name']")
    ))


def _portal_names(driver):
    return [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, ".portal-name-text")]


def _delete_portal_card(driver, name):
    """Delete one portal by name.

    HARD GUARD: refuses any name this run did not create. This is the single
    choke point for destructive actions in the suite - keep it that way.
    """
    if name not in CREATED_PORTALS:
        pytest.fail(
            f"REFUSING to delete '{name}' - not created by this run. "
            f"Deletable names: {sorted(CREATED_PORTALS)}"
        )
    card = _wait(driver).until(EC.presence_of_element_located((
        By.XPATH,
        f"//div[contains(@class,'portal-list-card')]"
        f"[.//div[contains(@class,'portal-name-text')][normalize-space()='{name}']]",
    )))
    _click(driver, card.find_element(By.CSS_SELECTOR, ".delete-portal"))

    confirm = _wait(driver).until(EC.element_to_be_clickable((
        By.XPATH,
        "//div[contains(@class,'ant-modal')][.//div[normalize-space()='Confirmation']]"
        "//button[normalize-space()='Confirm']",
    )))
    _click(driver, confirm)
    _wait(driver, 60).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(3)
    print(f"  Deleted portal '{name}'")


def _open_portal_page(driver, page):
    """Open /<portalId>/<page> for the portal this run created."""
    assert PORTAL["url"], "Portal not created - test_10 must run first."
    driver.get(f"{PORTAL['url']}/{page}")
    time.sleep(5)


# ----------------------- TEST CASES -----------------------

def test_01_login(driver, base_url, config):
    """Log in and land on the dashboard."""
    driver.get(base_url)
    _wait(driver).until(EC.presence_of_element_located((By.ID, "email"))).send_keys(config["email_org"])
    driver.find_element(By.ID, "password").send_keys(config["password_org"])
    driver.find_element(By.CLASS_NAME, "login-button").click()

    try:
        title = _wait(driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, "header-title"))
        ).text
    except TimeoutException:
        pytest.fail(f"Login failed - dashboard never rendered. {_dump(driver, 'lang_login')}")

    assert "Welcome" in title, f"Login failed - unexpected header: {title!r}"
    print(f"PASS: Logged in: {title.splitlines()[0]}")


def test_02_open_client_list_and_snapshot_baseline(driver):
    """Organization -> client list, and record the clients that already exist."""
    wait = _wait(driver)

    # The sidebar links only resolve once the logged-in user lands in redux, so
    # let the dashboard settle and re-click until the route actually changes.
    time.sleep(6)
    for _ in range(3):
        nav = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[normalize-space()='Organization']")
        ))
        _click(driver, nav)
        try:
            _wait(driver, 15).until(EC.url_contains("/organization"))
            break
        except TimeoutException:
            time.sleep(4)

    # Where 'Organization' lands depends on the account's role: an org-scoped
    # account goes straight to its client list, an ADMIN searches the org list.
    try:
        CONTEXT["org"] = org_flow.open_organization(driver, os.getenv("LANG_ORG"))
    except (AssertionError, TimeoutException) as exc:
        pytest.fail(f"Could not open the client list (at {driver.current_url}): {exc} "
                    f"{_dump(driver, 'lang_client_list')}")
    CLIENT_LIST_URL["url"] = driver.current_url
    CLIENT_BASELINE.extend(_client_names(driver))
    print(f"PASS: Client list for organization '{CONTEXT['org']}': {driver.current_url}")
    print(f"   Baseline - {len(CLIENT_BASELINE)} existing client(s), all protected")


@pytest.mark.testrail(886)
def test_03_client_language_dropdown_lists_every_language(driver):
    """C886 - the client Language dropdown offers the full DefaultLanguages set."""
    _open_add_client_modal(driver)
    _open_select(driver, f"{MODAL}//div[contains(@class,'ant-select')]"
                         f"[.//span[normalize-space()='Select Language']]")
    options = _dropdown_options(driver)
    _close_dropdown(driver)

    missing = [name for name in CLIENT_LANGUAGES if name not in options]
    unexpected = [name for name in options if name not in CLIENT_LANGUAGES]
    assert not missing, f"Languages missing from the client dropdown: {missing} (saw {options})"
    assert not unexpected, f"Unexpected languages in the client dropdown: {unexpected}"
    print(f"PASS: Client language dropdown offers all {len(CLIENT_LANGUAGES)} languages")


@pytest.mark.testrail(887)
def test_04_client_language_is_required(driver):
    """C887 - saving without a language is blocked with an inline error."""
    _open_add_client_modal(driver)
    name_field = _client_name_input(driver)
    name_field.clear()
    name_field.send_keys(f"{CLIENT_NAME} validation")

    save = _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, f"{MODAL}//button[contains(@class,'custom-save-btn')]")
    ))
    _click(driver, save)

    error = _wait(driver, 15).until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//div[normalize-space()='Language is required']")
    ))
    assert error.is_displayed(), "'Language is required' was not shown"
    assert CLIENT_NAME not in _client_names(driver), "A client was created despite the error"
    print("PASS: Empty language blocked with 'Language is required'")


@pytest.mark.testrail(888, 889)
def test_05_create_client_with_non_english_default(driver):
    """C888/C889 - create a client whose default language is not English."""
    _open_add_client_modal(driver)

    # C889 - the note that scopes the language to the portal, not the admin UI.
    note = _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//p[contains(@class,'note')]")
    )).text.lower()
    assert "portal" in note and "admin" in note, f"Scope note missing or reworded: {note!r}"

    name_field = _client_name_input(driver)
    name_field.clear()
    name_field.send_keys(CLIENT_NAME)
    chosen = _pick_antd_option(driver, "Select Language", DEFAULT_LANGUAGE, scope=MODAL)
    assert chosen == DEFAULT_LANGUAGE

    save = _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, f"{MODAL}//button[contains(@class,'custom-save-btn')]")
    ))
    _click(driver, save)

    # The toast auto-dismisses in ~3s and errors share its container, so assert
    # on the text rather than on the popup merely existing.
    toast = _wait(driver, 20).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".swal2-container")
    )).text.strip()
    assert "success" in toast.lower(), f"Client create did not succeed: {toast!r}"

    _close_add_client_modal(driver)
    _open_client_list(driver)
    _search_client_list(driver, CLIENT_NAME)
    assert CLIENT_NAME in _client_names(driver), (
        f"'{CLIENT_NAME}' is not on the client list after creation"
    )
    print(f"PASS: Created client '{CLIENT_NAME}' with default language {DEFAULT_LANGUAGE}")


@pytest.mark.testrail(890, 891)
def test_06_portal_default_language_cascades_and_is_read_only(driver):
    """C890/C891 - Branding shows the client's language, read-only."""
    create_btn = _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[normalize-space()='Create Portal']")
    ))
    _click(driver, create_btn)
    _wait(driver).until(EC.url_contains("/new/branding"))
    time.sleep(3)

    # The organization has to be chosen again here; its select only renders for
    # ADMIN / SUPER_ADMIN.
    try:
        if org_flow.has_branding_org_select(driver):
            org_flow.pick_branding_option(driver, "Organization", os.getenv("LANG_ORG") or CONTEXT["org"])
            time.sleep(3)
        org_flow.pick_branding_option(driver, "Client", CLIENT_NAME)
    except (AssertionError, TimeoutException) as exc:
        pytest.fail(f"Org/client selection failed: {exc} {_dump(driver, 'lang_branding_select')}")
    time.sleep(3)

    field = _wait(driver).until(EC.presence_of_element_located((By.XPATH, DEFAULT_LANGUAGE_INPUT)))
    assert field.get_attribute("disabled") is not None, "Default Language field is editable"
    value = field.get_attribute("value").strip()
    assert value == DEFAULT_LANGUAGE, (
        f"Default Language shows {value!r}, expected the client's {DEFAULT_LANGUAGE!r}"
    )
    print(f"PASS: Default Language cascaded from the client as read-only '{value}'")


@pytest.mark.testrail(892)
def test_07_additional_dropdown_excludes_the_default_language(driver):
    """C892 - every supported language is offered except the default one."""
    _open_select(driver, ADDITIONAL_LANGUAGE_SELECT)
    options = _dropdown_options(driver)
    _close_dropdown(driver)

    expected = [name for name in PORTAL_LANGUAGES if name != DEFAULT_LANGUAGE]
    assert DEFAULT_LANGUAGE not in options, (
        f"The default language '{DEFAULT_LANGUAGE}' is selectable as an additional language"
    )
    missing = [name for name in expected if name not in options]
    assert not missing, f"Languages missing from the additional dropdown: {missing} (saw {options})"
    print(f"PASS: Additional dropdown offers {len(options)} languages, "
          f"excluding '{DEFAULT_LANGUAGE}'")


@pytest.mark.testrail(893)
def test_08_select_multiple_additional_languages(driver):
    """C893 - the additional-language control is multi-select and shows tags."""
    _open_select(driver, ADDITIONAL_LANGUAGE_SELECT)
    for name in ADDITIONAL_LANGUAGES:
        _choose_option(driver, name)
    _close_dropdown(driver)

    tags = _selected_tags(driver, ADDITIONAL_LANGUAGE_SELECT)
    missing = [name for name in ADDITIONAL_LANGUAGES if name not in tags]
    assert not missing, f"Selected languages not rendered as tags: {missing} (saw {tags})"
    print(f"PASS: Selected {len(ADDITIONAL_LANGUAGES)} additional languages: {tags}")


@pytest.mark.testrail(896)
def test_09_unknown_language_shows_empty_state(driver):
    """C896 - searching an unsupported language shows 'No Language Found'."""
    _open_select(driver, ADDITIONAL_LANGUAGE_SELECT)
    _search_in_select(driver, ADDITIONAL_LANGUAGE_SELECT, "Klingon")
    empty = _dropdown_empty_text(driver)
    options = _dropdown_options(driver)

    # Clear the search so the typed text can't leak into the save below.
    for _ in range(len("Klingon")):
        ActionChains(driver).send_keys(Keys.BACKSPACE).perform()
    _close_dropdown(driver)

    assert not options, f"An unsupported language still matched options: {options}"
    assert "no language found" in empty.lower(), f"Unexpected empty state: {empty!r}"
    print("PASS: Unsupported language shows 'No Language Found'")


def test_10_save_portal_with_its_languages(driver, config):
    """Finish the portal so the language settings have somewhere to persist.

    Not a TestRail case of its own - it is the fixture the rest of the suite
    needs, and it registers the portal for deletion in test_15.
    """
    wait = _wait(driver)
    logo_path = os.getenv("PORTAL_LOGO_PATH") or config.get("headshot_path")
    if not logo_path or not os.path.exists(logo_path):
        pytest.fail(
            "Portal logo image not found - set PORTAL_LOGO_PATH (or HEADSHOT_PATH) in .env "
            f"to an image under 200 KB. Got: {logo_path!r}"
        )
    if os.path.getsize(logo_path) > 200 * 1024:
        pytest.fail(f"Logo '{logo_path}' exceeds the app's 200 KB limit - pick a smaller image.")

    # Header menu logo is mandatory; Material-template orgs also need the
    # registration/login logo.
    try:
        org_flow.upload_branding_logos(driver, logo_path)
    except (AssertionError, TimeoutException) as exc:
        pytest.fail(f"Logo upload failed: {exc} {_dump(driver, 'lang_crop')}")

    _click(driver, wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-testid='branding-next-button']")
    )))
    try:
        _wait(driver, 120).until(EC.url_matches(r".*/[0-9a-f]{6,}/home"))
    except TimeoutException:
        pytest.fail(f"Branding save did not create a portal (still at {driver.current_url}). "
                    f"{_dump(driver, 'lang_branding_save')}")

    PORTAL["id"] = driver.current_url.rstrip("/").split("/")[-2]
    PORTAL["url"] = driver.current_url.rsplit("/", 1)[0]

    # The home page is what names the portal on the list, so it has to be saved
    # for the default language before anything else (and C920 depends on it).
    name_input = wait.until(EC.presence_of_element_located((By.ID, "eventName")))
    name_input.clear()
    name_input.send_keys(PORTAL_NAME)
    time.sleep(1)
    _click(driver, wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@type='submit'][contains(normalize-space(),'Save')]")
    )))
    time.sleep(8)

    CREATED_PORTALS.add(PORTAL_NAME)
    print(f"PASS: Portal '{PORTAL_NAME}' created (id {PORTAL['id']})")


@pytest.mark.testrail(895)
def test_11_additional_languages_persist_after_reload(driver):
    """C895 - the selected additional languages survive a save and a reload."""
    _open_portal_page(driver, "branding")
    _wait(driver).until(EC.presence_of_element_located((By.XPATH, ADDITIONAL_LANGUAGE_SELECT)))
    time.sleep(3)

    tags = _selected_tags(driver, ADDITIONAL_LANGUAGE_SELECT)
    missing = [name for name in ADDITIONAL_LANGUAGES if name not in tags]
    assert not missing, f"Additional languages lost after reload: {missing} (saw {tags})"

    value = driver.find_element(By.XPATH, DEFAULT_LANGUAGE_INPUT).get_attribute("value").strip()
    assert value == DEFAULT_LANGUAGE, f"Default Language changed after reload: {value!r}"
    print(f"PASS: {tags} still selected after reload, default still '{value}'")


@pytest.mark.testrail(897)
def test_12_home_language_selector_offers_default_then_additional(driver):
    """C897 - per-language selectors offer [default, ...additional] in order.

    Note these selectors are fed the raw code list, so the options read 'it' /
    'de' rather than 'Italian' / 'German' - that inconsistency is C919 and is
    asserted here as the CURRENT behaviour, not as the desired one.
    """
    _open_portal_page(driver, "home")
    _open_select(driver, HOME_LANGUAGE_SELECT)
    options = _dropdown_options(driver)
    _close_dropdown(driver)

    expected = [DEFAULT_CODE] + ADDITIONAL_CODES
    assert options == expected, (
        f"Home language selector offered {options}, expected {expected} "
        "(default language first, then each additional language)"
    )
    print(f"PASS: Home language selector offers {options}")


@pytest.mark.testrail(898, 920)
def test_13_home_content_is_stored_per_language(driver):
    """C898/C920 - each language keeps its own home-page content."""
    translated = f"{PORTAL_NAME} [{ADDITIONAL_CODES[0]}]"
    wait = _wait(driver)

    # C920 - the selector is only usable once the default language is saved,
    # which test_10 did; before that it is disabled with a warning.
    selector = _select_container(driver, HOME_LANGUAGE_SELECT)
    assert "ant-select-disabled" not in selector.get_attribute("class"), (
        "Home language selector is still disabled after the default language was saved"
    )

    # Switch to the first additional language and give it its own event title.
    _open_select(driver, HOME_LANGUAGE_SELECT)
    _choose_option(driver, ADDITIONAL_CODES[0])
    _handle_language_switch_modal(driver)
    time.sleep(4)

    name_input = wait.until(EC.presence_of_element_located((By.ID, "eventName")))
    name_input.clear()
    name_input.send_keys(translated)
    time.sleep(1)
    _click(driver, wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@type='submit'][contains(normalize-space(),'Save')]")
    )))
    time.sleep(8)

    # Reload rather than just switching back: this proves the value came from
    # the server, not from React state that never refetched.
    _open_portal_page(driver, "home")
    default_value = wait.until(EC.presence_of_element_located(
        (By.ID, "eventName")
    )).get_attribute("value").strip()
    assert default_value == PORTAL_NAME, (
        f"Default-language title was overwritten by the translation: {default_value!r}"
    )

    _open_select(driver, HOME_LANGUAGE_SELECT)
    _choose_option(driver, ADDITIONAL_CODES[0])
    _handle_language_switch_modal(driver)
    time.sleep(4)
    translated_value = wait.until(EC.presence_of_element_located(
        (By.ID, "eventName")
    )).get_attribute("value").strip()
    assert translated_value == translated, (
        f"Translated title not stored for '{ADDITIONAL_CODES[0]}': {translated_value!r}"
    )
    print(f"PASS: '{DEFAULT_CODE}' keeps {PORTAL_NAME!r}, "
          f"'{ADDITIONAL_CODES[0]}' keeps {translated!r}")


def _handle_language_switch_modal(driver):
    """Dismiss the 'save before switching?' modal when the form is dirty.

    Home only raises it when the current form differs from what was loaded. We
    answer 'Save Changes', which writes the unchanged values back against the
    ORIGINAL language - a no-op that keeps the two languages independent.
    """
    modal = driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'ant-modal')]"
        "[.//div[contains(normalize-space(),'save your changes before switching')]]",
    )
    if not modal:
        return
    _click(driver, _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, "//div[contains(@class,'ant-modal')]//button[normalize-space()='Save Changes']")
    )))
    _wait(driver, 60).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(3)


@pytest.mark.testrail(912)
def test_14_publish_lists_one_url_per_language(driver):
    """C912 - Publish shows a portal URL for the default and every additional language."""
    _open_portal_page(driver, "publish")
    rows = _wait(driver).until(lambda d: d.find_elements(
        By.CSS_SELECTOR, ".publish-portal-url-row"
    ) or False)

    urls = [row.find_element(By.CSS_SELECTOR, ".publish-portal-url-link").text.strip()
            for row in rows]
    codes = [row.find_element(By.CSS_SELECTOR, ".publish-portal-url-lang").text.strip()
             for row in rows]

    expected_codes = [code.upper() for code in [DEFAULT_CODE] + ADDITIONAL_CODES]
    assert codes == expected_codes, f"Publish listed {codes}, expected {expected_codes}"
    for code, url in zip([DEFAULT_CODE] + ADDITIONAL_CODES, urls):
        assert url.endswith(f"/{code}/{PORTAL['id']}"), (
            f"URL for '{code}' is {url!r}, expected it to end with /{code}/{PORTAL['id']}"
        )
    print(f"PASS: Publish lists {len(urls)} per-language URLs: {codes}")


@pytest.mark.testrail(906, 907)
def test_15_session_language_screen(driver):
    """C906/C907 - the session Language & ECDN tab, read-only.

    Skipped unless LANG_SESSION_URL points at an existing session: building a
    webcast just to read two checkboxes is not worth the data it leaves behind,
    and this suite never writes to a session it did not create.
    """
    session_url = os.getenv("LANG_SESSION_URL")
    if not session_url:
        pytest.skip("LANG_SESSION_URL not set - no existing session to inspect")

    driver.get(session_url)
    tab = _wait(driver, 60).until(EC.presence_of_element_located(
        (By.XPATH, "//button[@role='tab'][contains(normalize-space(),'Language')]")
    ))
    _click(driver, tab)
    time.sleep(4)

    row = _wait(driver).until(EC.presence_of_element_located((
        By.XPATH,
        "//div[contains(@class,'webcast-details-form-row')][div[normalize-space()='Default Language']]",
    )))
    checkbox = row.find_element(By.ID, "defaultLanguage")
    assert checkbox.get_attribute("disabled") is not None, "Default Language checkbox is editable"
    assert checkbox.is_selected(), "Default Language checkbox is not checked"
    default_name = row.find_elements(By.TAG_NAME, "span")[-1].text.strip()
    assert default_name, "Default Language row has no language name"

    additional_row = _wait(driver).until(EC.presence_of_element_located((
        By.XPATH,
        "//div[contains(@class,'webcast-details-form-row')]"
        "[div[normalize-space()='Additional Languages']]",
    )))
    labels = [span.text.strip() for span in additional_row.find_elements(By.TAG_NAME, "span")
              if span.text.strip()]
    assert labels, "No additional languages were offered"
    assert default_name not in labels, (
        f"The session default '{default_name}' is also offered as an additional language"
    )
    print(f"PASS: Session default '{default_name}' is locked; "
          f"{len(labels)} other language(s) offered")


def test_16_cleanup_and_baseline_intact(driver):
    """Delete only the portal this run created, and prove nothing else moved.

    The created CLIENT is left behind on purpose - the admin UI exposes no
    client delete. Its name carries RUN_ID, so it is safe to clean up
    server-side if the environment needs it.
    """
    _open_client_list(driver)
    _search_client_list(driver, CLIENT_NAME)
    view = _wait(driver).until(EC.presence_of_element_located((
        By.XPATH, f"//tr[.//td[normalize-space()='{CLIENT_NAME}']]//td[contains(@class,'portal-view-button')]",
    )))
    _click(driver, view)
    _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[@class='con-title'][normalize-space()='Portals']")
    ))
    time.sleep(3)

    for name in sorted(CREATED_PORTALS):
        _delete_portal_card(driver, name)
    leftovers = [n for n in _portal_names(driver) if n.startswith(PORTAL_PREFIX)]
    assert not leftovers, f"Portals created by this run were not deleted: {leftovers}"

    _open_client_list(driver)
    _search_client_list(driver, "")
    current = _client_names(driver)
    missing = [name for name in CLIENT_BASELINE if name not in current]
    assert not missing, f"Pre-existing clients are gone: {missing}"
    print(f"PASS: Cleanup done - {len(CLIENT_BASELINE)} pre-existing client(s) untouched")
    print(f"   NOTE: client '{CLIENT_NAME}' remains (no delete in the admin UI)")
