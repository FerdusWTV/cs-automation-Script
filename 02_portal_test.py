"""Portal CRUD end-to-end suite for ConnectStudio 2.0 (ShareStudio admin).

Safety contract - this suite NEVER touches pre-existing data:
  * `test_02` snapshots every portal already on the client (BASELINE).
  * Every portal this run creates is registered in CREATED and its name carries
    the unique `PORTAL_PREFIX` (run-stamped), so it cannot collide with real data.
  * `_delete_portal_card` refuses to click a delete icon for any name that is not
    in CREATED - a missed selector can therefore never delete someone's portal.
  * `test_07` asserts the baseline list is unchanged at the end.

Order matters: tests are numbered and share one browser session (module-scoped
`driver`), so run the file as a whole rather than cherry-picking with `-k`.

Run:
    ..\\venv\\Scripts\\pytest -v portal_test.py --env=dev --html=report.html --self-contained-html
    ..\\venv\\Scripts\\pytest -v portal_test.py --base-url=http://localhost:3000
"""

import os
import time
import uuid

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

# ----------------------- RUN STATE ------------------------

# Unique per run so two parallel runs (or a crashed previous run) can't collide.
RUN_ID = uuid.uuid4().hex[:6]
PORTAL_PREFIX = f"Automated Portal {RUN_ID}"
PORTAL_NAME = f"{PORTAL_PREFIX} - 001"
CLONE_NAME = f"{PORTAL_PREFIX} - 001 Clone"

# Portal names this run created - the ONLY names delete is ever allowed to target.
CREATED = set()
# Portal names that existed before this run - must be intact when we finish.
BASELINE = []
# Portal-list URL captured in test_02 so later tests can return to the same list.
PORTAL_LIST_URL = {"url": None}
# The organization and client the baseline was taken under. The create form must
# target these same two, or it builds the portal somewhere else entirely — which
# on an ADMIN account means picking the first organization on the list, whose
# client dropdown may well be empty.
CONTEXT = {"org": None, "client": None}


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
    """JS click - antd overlays and toasts routinely intercept native clicks."""
    driver.execute_script("arguments[0].click();", element)


def _pick_antd_option(driver, placeholder, wanted=None):
    """Open the antd Select carrying `placeholder` and choose an option.

    `wanted` selects by exact label; None takes the first available option.
    Returns the chosen label.
    """
    wait = _wait(driver)
    container = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//div[contains(@class,'ant-select')][.//span[normalize-space()='{placeholder}']]",
    )))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
    time.sleep(1)

    # antd opens its dropdown on a real mousedown against `.ant-select-selector` —
    # a JS .click() on the wrapper does nothing here.
    selector = container.find_element(By.CSS_SELECTOR, ".ant-select-selector")
    selector.click()
    time.sleep(1)

    dropdown = ("//div[contains(@class,'ant-select-dropdown') and "
                "not(contains(@class,'ant-select-dropdown-hidden'))]")
    if wanted:
        option = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{dropdown}//div[contains(@class,'ant-select-item-option')]"
                       f"[normalize-space()='{wanted}']")
        ))
    else:
        options = wait.until(lambda d: d.find_elements(
            By.XPATH, f"{dropdown}//div[contains(@class,'ant-select-item-option')]"
        ) or False)
        option = options[0]

    label = option.text.strip()
    _click(driver, option)
    time.sleep(1)
    return label


def _portal_names(driver):
    """Names of every portal card currently rendered on the portal list."""
    return [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, ".portal-name-text")]


def _portal_card(driver, name, timeout=30):
    """The portal card whose title is exactly `name`."""
    return _wait(driver, timeout).until(EC.presence_of_element_located((
        By.XPATH,
        f"//div[contains(@class,'portal-list-card')]"
        f"[.//div[contains(@class,'portal-name-text')][normalize-space()='{name}']]",
    )))


def _open_portal_list(driver, base_url):
    """Navigate to the portal list captured in test_02 and wait for it to render."""
    url = PORTAL_LIST_URL["url"]
    assert url, "Portal list URL not captured - test_02 must run first."
    driver.get(url)
    _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[@class='con-title'][normalize-space()='Portals']")
    ))
    time.sleep(3)


def _search_portal_list(driver, term):
    """Type `term` into the portal-list search box (1s debounce, then a refetch)."""
    box = _wait(driver).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input.connect-studio-search-input-small")
    ))
    # Clear via keystrokes: .clear() bypasses React's onChange, so the list would
    # stay filtered on the previous term.
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys(Keys.BACKSPACE)
    time.sleep(2)
    if term:
        box.send_keys(term)
    time.sleep(4)


def _delete_portal_card(driver, name):
    """Delete one portal by name.

    HARD GUARD: refuses any name this run did not create. This is the single
    choke point for destructive actions in the suite - keep it that way.
    """
    if name not in CREATED:
        pytest.fail(
            f"REFUSING to delete '{name}' - not created by this run. "
            f"Deletable names: {sorted(CREATED)}"
        )

    card = _portal_card(driver, name)
    trash = card.find_element(By.CSS_SELECTOR, ".delete-portal")
    _click(driver, trash)

    confirm = _wait(driver).until(EC.element_to_be_clickable((
        By.XPATH,
        "//div[contains(@class,'ant-modal')][.//div[normalize-space()='Confirmation']]"
        "//button[normalize-space()='Confirm']",
    )))
    _click(driver, confirm)

    # The modal closes only after the DELETE resolves and the list refetches.
    _wait(driver, 60).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(3)
    print(f"  Deleted '{name}'")


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
        pytest.fail(f"Login failed - dashboard never rendered. {_dump(driver, 'login')}")

    assert "Welcome" in title, f"Login failed - unexpected header: {title!r}"
    print(f"PASS: Logged in: {title.splitlines()[0]}")


def test_02_open_portal_list_and_snapshot_baseline(driver, base_url):
    """Organization -> client -> portal list, and record what already exists.

    Everything captured here is off-limits for the rest of the run.
    """
    wait = _wait(driver)

    # The sidebar links only resolve once the logged-in user lands in redux, so
    # let the dashboard settle and re-click until the route actually changes.
    time.sleep(6)
    for attempt in range(3):
        org_nav = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[normalize-space()='Organization']")
        ))
        _click(driver, org_nav)
        try:
            _wait(driver, 15).until(EC.url_contains("/organization"))
            break
        except TimeoutException:
            time.sleep(4)
    # Where 'Organization' lands depends on the account's role. An org-scoped
    # account goes straight to its own client list; an ADMIN / SUPER_ADMIN gets
    # the organization list first and has to pick one. dev and prod differ here
    # because there is no EMAIL_ORG_PROD, so a prod run falls back to the admin
    # account and needs this extra hop.
    org_cards = driver.find_elements(By.CSS_SELECTOR, ".org-card")
    if org_cards and not driver.find_elements(By.CSS_SELECTOR, ".client-list-table-container"):
        wanted = os.getenv("PORTAL_ORG")
        card = None
        if wanted:
            matches = driver.find_elements(
                By.XPATH,
                f"//div[contains(@class,'org-card')][.//h6[normalize-space()='{wanted}']]"
                "//div[contains(@class,'org-card-arrow')]",
            )
            if not matches:
                pytest.fail(
                    f"PORTAL_ORG='{wanted}' is not on the organization list. "
                    f"{_dump(driver, 'org_list')}"
                )
            card = matches[0]
        else:
            card = driver.find_element(By.CSS_SELECTOR, ".org-card .org-card-arrow")
        _click(driver, card)
        _wait(driver, 20).until(EC.url_contains("/organization/client"))
        time.sleep(2)

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".client-list-table-container")))
    except TimeoutException:
        pytest.fail(
            f"Client list never rendered (at {driver.current_url}). {_dump(driver, 'client_list')}"
        )
    time.sleep(3)

    shown_org = driver.find_elements(By.CSS_SELECTOR, ".client-org-name")
    CONTEXT["org"] = shown_org[0].text.strip() if shown_org else None

    # Pick the client named in PORTAL_CLIENT, else the first row.
    target_client = os.getenv("PORTAL_CLIENT")
    if target_client:
        row = wait.until(EC.presence_of_element_located((
            By.XPATH,
            f"//tr[.//td[normalize-space()='{target_client}']]//td[contains(@class,'portal-view-button')]",
        )))
    else:
        buttons = wait.until(lambda d: d.find_elements(
            By.CSS_SELECTOR, "td.portal-view-button"
        ) or False)
        row = buttons[0]

    # Row layout is: name | id | 'View Portals'. The preceding-sibling axis runs
    # backwards from `row`, so [1] is the id cell and [2] is the name.
    name_cell = row.find_elements(By.XPATH, "./preceding-sibling::td[2]")
    CONTEXT["client"] = target_client or (name_cell[0].text.strip() if name_cell else None)
    print(f"   Working under organization '{CONTEXT['org']}', client '{CONTEXT['client']}'")
    _click(driver, row)

    wait.until(EC.presence_of_element_located(
        (By.XPATH, "//div[@class='con-title'][normalize-space()='Portals']")
    ))
    time.sleep(3)

    PORTAL_LIST_URL["url"] = driver.current_url
    BASELINE.extend(_portal_names(driver))
    print(f"PASS: Portal list: {driver.current_url}")
    print(f"   Baseline - {len(BASELINE)} existing portal(s) on this page, all protected:")
    for name in BASELINE:
        print(f"     - {name}")


def test_03_create_portal(driver, base_url, config):
    """CREATE - sidebar 'Create Portal' -> branding -> homepage, named uniquely."""
    wait = _wait(driver)

    logo_path = os.getenv("PORTAL_LOGO_PATH") or config.get("headshot_path")
    if not logo_path or not os.path.exists(logo_path):
        pytest.fail(
            "Portal logo image not found - set PORTAL_LOGO_PATH (or HEADSHOT_PATH) "
            f"in .env to an image under 200 KB. Got: {logo_path!r}"
        )
    if os.path.getsize(logo_path) > 200 * 1024:
        pytest.fail(f"Logo '{logo_path}' exceeds the app's 200 KB limit - pick a smaller image.")

    create_btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//div[normalize-space()='Create Portal']")
    ))
    _click(driver, create_btn)
    wait.until(EC.url_contains("/new/branding"))
    time.sleep(3)

    # --- Step 1: branding -------------------------------------------------
    # The organization select only renders for ADMIN/SUPER_ADMIN; org admins get client only.
    if driver.find_elements(
        By.XPATH, "//div[contains(@class,'ant-select')][.//span[normalize-space()='Select organization']]"
    ):
        org = _pick_antd_option(
            driver, "Select organization", os.getenv("PORTAL_ORG") or CONTEXT["org"]
        )
        print(f"   Organization: {org}")
        time.sleep(3)

    client = _pick_antd_option(
        driver, "Select client", os.getenv("PORTAL_CLIENT") or CONTEXT["client"]
    )
    print(f"   Client: {client}")

    # Header menu logo is mandatory; react-dropzone's file input is hidden but writable.
    file_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".dropzone input[type='file']")
    ))
    driver.execute_script(
        "arguments[0].style.display='block';arguments[0].style.opacity=1;", file_input
    )
    file_input.send_keys(os.path.abspath(logo_path))

    # The crop modal only yields an image after a real crop interaction -
    # `onComplete` never fires from the auto-centered initial crop alone.
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".crop-image-modal")))
    handle = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".ReactCrop__drag-handle.ord-se")
    ))
    ActionChains(driver).click_and_hold(handle).move_by_offset(-12, -9).release().perform()
    time.sleep(2)

    set_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//div[contains(@class,'crop-image-modal')]//button[normalize-space()='Set']")
    ))
    _click(driver, set_btn)
    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".crop-image-modal")))
    except TimeoutException:
        pytest.fail(f"Crop modal never closed - 'Set' had no cropped image. {_dump(driver, 'crop')}")

    save_branding = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-testid='branding-next-button']")
    ))
    _click(driver, save_branding)

    # A successful create routes to /<portalId>/home.
    try:
        _wait(driver, 120).until(EC.url_matches(r".*/[0-9a-f]{6,}/home"))
    except TimeoutException:
        pytest.fail(
            f"Branding save did not create a portal (still at {driver.current_url}). "
            f"{_dump(driver, 'branding_save')}"
        )
    portal_id = driver.current_url.rstrip("/").split("/")[-2]
    print(f"   Portal created - id: {portal_id}")

    # --- Step 2: homepage - this is what names the portal in the list ------
    name_input = wait.until(EC.presence_of_element_located((By.ID, "eventName")))
    name_input.clear()
    name_input.send_keys(PORTAL_NAME)
    time.sleep(1)

    save_home = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@type='submit'][contains(normalize-space(),'Save')]")
    ))
    _click(driver, save_home)
    time.sleep(6)

    CREATED.add(PORTAL_NAME)
    print(f"PASS: Created portal '{PORTAL_NAME}' (id {portal_id})")


def test_04_read_created_portal(driver, base_url):
    """READ - the new portal is listed, and nothing pre-existing was disturbed."""
    _open_portal_list(driver, base_url)
    _search_portal_list(driver, PORTAL_NAME)

    names = _portal_names(driver)
    assert PORTAL_NAME in names, (
        f"'{PORTAL_NAME}' not found on the portal list after creation. Found: {names}"
    )
    assert names.count(PORTAL_NAME) == 1, f"Expected exactly one '{PORTAL_NAME}', got {names}"
    print(f"PASS: Portal visible on the list: {PORTAL_NAME}")

    # Unfiltered view must still contain every baseline portal.
    _search_portal_list(driver, "")
    current = _portal_names(driver)
    missing = [n for n in BASELINE if n not in current]
    assert not missing, f"Pre-existing portals disappeared after create: {missing}"


def test_05_clone_created_portal(driver, base_url):
    """CLONE - duplicate only our own portal, under its own unique name."""
    _open_portal_list(driver, base_url)
    _search_portal_list(driver, PORTAL_NAME)

    card = _portal_card(driver, PORTAL_NAME)
    clone_icon = card.find_element(By.CSS_SELECTOR, ".clone-portal")
    _click(driver, clone_icon)

    name_field = _wait(driver).until(EC.presence_of_element_located((By.ID, "portalName")))
    name_field.clear()
    name_field.send_keys(CLONE_NAME)

    confirm = _wait(driver).until(EC.element_to_be_clickable((
        By.XPATH,
        "//div[contains(@class,'ant-modal')][.//div[normalize-space()='Clone Portal']]"
        "//button[normalize-space()='Clone Portal']",
    )))
    _click(driver, confirm)
    _wait(driver, 90).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    CREATED.add(CLONE_NAME)  # registered immediately so cleanup can reach it
    time.sleep(4)

    _search_portal_list(driver, PORTAL_PREFIX)
    names = _portal_names(driver)
    assert CLONE_NAME in names, f"Clone '{CLONE_NAME}' not found after cloning. Found: {names}"
    print(f"PASS: Cloned portal: {CLONE_NAME}")


def test_06_delete_created_portals_only(driver, base_url):
    """DELETE - remove exactly the portals this run created, nothing else."""
    _open_portal_list(driver, base_url)
    _search_portal_list(driver, PORTAL_PREFIX)

    # Clone first (reverse-sorted puts 'Clone' ahead of the original).
    for name in sorted(CREATED, reverse=True):
        _delete_portal_card(driver, name)

    _search_portal_list(driver, PORTAL_PREFIX)
    leftovers = [n for n in _portal_names(driver) if n.startswith(PORTAL_PREFIX)]
    assert not leftovers, f"Portals created by this run were not deleted: {leftovers}"
    print(f"PASS: Deleted {len(CREATED)} portal(s) created by this run")


def test_07_baseline_untouched(driver, base_url):
    """Final safety assertion: every pre-existing portal is still there."""
    _open_portal_list(driver, base_url)
    _search_portal_list(driver, "")
    current = _portal_names(driver)

    missing = [n for n in BASELINE if n not in current]
    assert not missing, f"FAIL: Pre-existing portals are gone: {missing}"

    extra = [n for n in current if n.startswith(PORTAL_PREFIX)]
    assert not extra, f"FAIL: Automated portals left behind: {extra}"
    print(f"PASS: Baseline intact - {len(BASELINE)} pre-existing portal(s) untouched")
