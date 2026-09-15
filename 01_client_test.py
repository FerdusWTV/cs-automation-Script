"""Client creation end-to-end suite for ConnectStudio 2.0 (ShareStudio admin).

Covers the 'Add a new client' flow on Organization -> Client
(`components/Organization/Modals/AddClientModal.js`): the modal's validation,
a successful create, and the new client showing up in the client table.

Safety contract - this suite NEVER touches pre-existing data:
  * `test_02` snapshots every client already on the organization (BASELINE).
  * Every client this run creates carries the run-stamped `CLIENT_PREFIX`, so it
    cannot collide with (or be mistaken for) real data.
  * `test_06` asserts the baseline rows are all still present at the end.
  * The admin UI exposes NO delete for clients, so the created client is left
    behind on purpose. Its name is unique per run - clean up server-side if the
    environment needs it.

Order matters: tests are numbered and share one browser session (module-scoped
`driver`), so run the file as a whole rather than cherry-picking with `-k`.

Run:
    ..\\venv\\Scripts\\pytest -v client_test.py --env=dev --html=report.html --self-contained-html
    ..\\venv\\Scripts\\pytest -v client_test.py --base-url=http://localhost:3000

Optional .env / environment overrides:
    CLIENT_ORG        organization to open (super-admin only; default: first card)
    CLIENT_LANGUAGE   language option label   (default: English)
"""

import os
import time
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

# ----------------------- RUN STATE ------------------------

# Unique per run so two parallel runs (or a crashed previous run) can't collide.
RUN_ID = uuid.uuid4().hex[:6]
CLIENT_PREFIX = f"Automated Client {RUN_ID}"
CLIENT_NAME = f"{CLIENT_PREFIX} - 001"

# Client names this run created.
CREATED = set()
# Client names that existed before this run - must still be there when we finish.
BASELINE = []
# Client-list URL captured in test_02 so later tests can return to the same list.
CLIENT_LIST_URL = {"url": None}

LANGUAGE = os.getenv("CLIENT_LANGUAGE", "English")

# The modal's own wrapper class - every locator below is scoped to it so the
# page behind the mask can never satisfy a query.
MODAL = "//div[contains(@class,'add-client-modal')][contains(@class,'ant-modal-wrap')]"


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
    driver.execute_script("arguments[0].click();", element)


def _pick_antd_option(driver, placeholder, wanted=None, contains=False):
    """Open the antd Select carrying `placeholder` inside the modal and choose an option.

    `wanted` selects by exact label, or by substring when `contains` is set;
    None takes the first available option. Returns the chosen label.
    """
    wait = _wait(driver)
    container = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"{MODAL}//div[contains(@class,'ant-select')]"
        f"[.//span[normalize-space()='{placeholder}']]",
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
    time.sleep(1)

    # antd opens its dropdown on a real mousedown against `.ant-select-selector` -
    # a JS .click() on the wrapper does nothing here.
    container.find_element(By.CSS_SELECTOR, ".ant-select-selector").click()
    time.sleep(1)

    dropdown = ("//div[contains(@class,'ant-select-dropdown') and "
                "not(contains(@class,'ant-select-dropdown-hidden'))]")
    item = f"{dropdown}//div[contains(@class,'ant-select-item-option')]"
    if wanted and contains:
        option = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{item}[contains(normalize-space(),'{wanted}')]")
        ))
    elif wanted:
        option = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{item}[normalize-space()='{wanted}']")
        ))
    else:
        options = wait.until(lambda d: d.find_elements(By.XPATH, item) or False)
        option = options[0]

    label = option.text.strip()
    _click(driver, option)
    time.sleep(1)
    return label


def _client_rows(driver):
    """(name, id) for every client row currently rendered on the client table."""
    rows = []
    for tr in driver.find_elements(By.CSS_SELECTOR, ".client-list-table-container tbody tr"):
        cells = tr.find_elements(By.TAG_NAME, "td")
        if len(cells) == 3 and cells[0].text.strip():
            rows.append((cells[0].text.strip(), cells[1].text.strip()))
    return rows


def _client_names(driver):
    return [name for name, _ in _client_rows(driver)]


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
    """Type `term` into the client-list search box (1s debounce, then a refetch).

    The page only refetches for an empty string or 2+ characters
    (`onSearchHandler`), so short terms are deliberately not supported here.
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
    """Click 'Add a new client' and wait for the modal to be interactive.

    Idempotent: if the modal is already open it is returned as-is. A test that
    fails before its own close step would otherwise leave the mask up, and the
    'Add a new client' button underneath it is unclickable — turning one failure
    into a cascade across every test that follows.
    """
    wait = _wait(driver)
    already_open = driver.find_elements(
        By.XPATH, f"{MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']"
    )
    if already_open:
        return

    add_btn = wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//div[@class='add-client-modal']//button[contains(@class,'save-button')]",
    )))
    _click(driver, add_btn)
    wait.until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']")
    ))
    time.sleep(1)


def _submit_modal(driver):
    save = _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, f"{MODAL}//button[contains(@class,'custom-save-btn')]")
    ))
    _click(driver, save)


def _swal_text(driver, timeout=15):
    """Text of the swal toast, waited for immediately after the triggering click.

    The toast auto-dismisses in ~3s, and success and failure share the same
    container - so the caller must assert on the text, not on its presence.
    """
    toast = _wait(driver, timeout).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".swal2-container")
    ))
    return toast.text.strip()


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
        pytest.fail(f"Login failed - dashboard never rendered. {_dump(driver, 'client_login')}")

    assert "Welcome" in title, f"Login failed - unexpected header: {title!r}"
    print(f"PASS: Logged in: {title.splitlines()[0]}")


def test_02_open_client_list_and_snapshot_baseline(driver, base_url):
    """Organization -> client list, and record which clients already exist.

    Everything captured here is off-limits for the rest of the run.
    """
    wait = _wait(driver)

    # The sidebar links only resolve once the logged-in user lands in redux, so
    # let the dashboard settle and re-click until the route actually changes.
    time.sleep(6)
    for _ in range(3):
        org_nav = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[normalize-space()='Organization']")
        ))
        _click(driver, org_nav)
        try:
            _wait(driver, 15).until(EC.url_contains("/organization"))
            break
        except TimeoutException:
            time.sleep(4)
    time.sleep(3)

    # ADMIN/SUPER_ADMIN land on the organization cards and have to pick one first;
    # an org admin is dropped straight onto their own client table.
    if driver.find_elements(By.CSS_SELECTOR, ".org-card"):
        target_org = os.getenv("CLIENT_ORG")
        if target_org:
            arrow = wait.until(EC.presence_of_element_located((
                By.XPATH,
                f"//div[contains(@class,'org-card')][.//h6[normalize-space()='{target_org}']]"
                f"//div[contains(@class,'org-card-arrow')]",
            )))
        else:
            arrows = wait.until(lambda d: d.find_elements(
                By.CSS_SELECTOR, ".org-card .org-card-arrow"
            ) or False)
            arrow = arrows[0]
        _click(driver, arrow)
        wait.until(EC.url_contains("/organization/client"))

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".client-list-table-container")))
    except TimeoutException:
        pytest.fail(
            f"Client list never rendered (at {driver.current_url}). "
            f"{_dump(driver, 'client_list')}"
        )
    time.sleep(3)

    CLIENT_LIST_URL["url"] = driver.current_url
    BASELINE.extend(_client_names(driver))
    org_name = driver.find_element(By.CSS_SELECTOR, ".client-org-name").text.strip()
    print(f"PASS: Client list for '{org_name}': {driver.current_url}")
    print(f"   Baseline - {len(BASELINE)} existing client(s) on this page, all protected:")
    for name in BASELINE:
        print(f"     - {name}")


def test_03_modal_validates_required_fields(driver):
    """VALIDATION - an empty submit reports both required fields and creates nothing.

    Name is a yup-validated Formik field; language is checked by hand in
    `onClientSave` and short-circuits before the POST.
    """
    _open_add_client_modal(driver)
    _submit_modal(driver)

    wait = _wait(driver)
    try:
        wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{MODAL}//div[normalize-space()='Name is required']")
        ))
        wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{MODAL}//div[normalize-space()='Language is required']")
        ))
    except TimeoutException:
        pytest.fail(
            f"Empty submit did not report both required fields. "
            f"{_dump(driver, 'client_validation')}"
        )

    # Nothing was sent, so the modal must still be open.
    assert driver.find_elements(
        By.XPATH, f"{MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']"
    ), "Modal closed on an invalid submit - a client may have been created."
    print("PASS: Empty submit blocked: 'Name is required' + 'Language is required'")

    # The header holds two icon-only controls (back, close) - either one toggles
    # the modal shut. They're react-icons SVGs, hence the `name()` predicate.
    icons = driver.find_elements(
        By.XPATH, f"{MODAL}//div[contains(@class,'ant-modal-header')]//*[name()='svg']"
    )
    assert icons, "Modal header rendered without its back/close icons."
    _click(driver, icons[-1])
    _wait(driver).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(2)


def test_04_create_client(driver):
    """CREATE - name + language, saved from the modal.

    There is no template field: `TemplateOption` was removed from the Add Client
    modal (it survives commented out at AddClientModal.js:145-148), so a client
    is now just a name and a language.
    """
    _open_add_client_modal(driver)
    wait = _wait(driver)

    name_input = wait.until(EC.presence_of_element_located(
        (By.XPATH, f"{MODAL}//input[@name='name']")
    ))
    name_input.send_keys(CLIENT_NAME)

    language = _pick_antd_option(driver, "Select Language", LANGUAGE)
    print(f"   Name: {CLIENT_NAME}")
    print(f"   Language: {language}")

    _submit_modal(driver)

    # Grab the toast right away - it lives ~3s and error reuses the container.
    try:
        text = _swal_text(driver)
    except TimeoutException:
        pytest.fail(f"No toast after saving the client. {_dump(driver, 'client_create')}")

    assert "successfully added" in text.lower(), (
        f"Client create failed - toast said {text!r}. {_dump(driver, 'client_create')}"
    )
    CREATED.add(CLIENT_NAME)

    # The modal closes and the list refetches only after the POST resolves.
    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    except TimeoutException:
        pytest.fail(f"Modal stayed open after a success toast. {_dump(driver, 'client_create')}")
    time.sleep(3)
    print(f"PASS: Created client '{CLIENT_NAME}'")


def test_05_created_client_is_listed(driver):
    """READ - the new client is searchable and carries a server-assigned id."""
    _open_client_list(driver)
    _search_client_list(driver, CLIENT_NAME)

    rows = dict(_client_rows(driver))
    if CLIENT_NAME not in rows:
        pytest.fail(
            f"Created client '{CLIENT_NAME}' not found by search - listed: {sorted(rows)}. "
            f"{_dump(driver, 'client_search')}"
        )
    assert rows[CLIENT_NAME], f"Client '{CLIENT_NAME}' listed without an id."
    print(f"PASS: Listed '{CLIENT_NAME}' (id {rows[CLIENT_NAME]})")


def test_06_baseline_intact(driver):
    """SAFETY - every client that existed before this run is still there."""
    _open_client_list(driver)
    _search_client_list(driver, "")

    names = set(_client_names(driver))
    # Only the first page is rendered; a baseline name pushed off it by the new
    # client is confirmed by searching for it directly.
    missing = []
    for name in BASELINE:
        if name in names:
            continue
        _search_client_list(driver, name)
        if name not in _client_names(driver):
            missing.append(name)
        _search_client_list(driver, "")

    assert not missing, f"Pre-existing client(s) missing after the run: {missing}"
    print(f"PASS: All {len(BASELINE)} baseline client(s) intact")
    print(f"   Left behind (no delete in the admin UI): {sorted(CREATED)}")
