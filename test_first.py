from _pytest import warning_types
import os
import time
import pytest
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ----------------------- FIXTURES ------------------------

@pytest.fixture(scope="session")
def driver():
    """Setup and teardown of Chrome WebDriver."""
    load_dotenv()
    options = Options()
    # options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-allow-origins=*")

    driver_path = os.getenv("DRIVER")
    if driver_path and os.path.exists(driver_path):
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    driver.maximize_window()
    yield driver
    driver.quit()


# ----------------------- HELPER FUNCTIONS -----------------

def _wait_for_swal(driver, label, timeout=30, expect=None):
    """Wait for the SweetAlert popup right after an action and return its text.

    Must be called immediately after the triggering click — the popups
    auto-dismiss, so any sleep beforehand can miss them entirely.
    `expect`: substring the popup text must contain (case-insensitive), e.g.
    'success' — otherwise the test fails with the actual popup message.
    Dumps a screenshot + page source on timeout for debugging.
    """
    try:
        # Poll until the popup exists AND has rendered its text (presence alone
        # can catch the container the instant it attaches, still empty).
        text = WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                "var e = document.getElementById('swal2-html-container');"
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

def _navigate_and_create_webcast(driver, wait, title):
    """Navigate to Sessions page and create a new webcast with the given title."""
    time.sleep(2)
    session_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Sessions')]")))
    driver.execute_script("arguments[0].click();", session_btn)

    webcast_creation_btn = wait.until(
        EC.presence_of_element_located((By.XPATH, "//div[@class='session-button-group-right']"))
    )
    driver.execute_script("arguments[0].click();", webcast_creation_btn)

    new_webcast_btn = wait.until(
        EC.presence_of_element_located((By.XPATH, "(//div[@class='stream-modal-container h-full'])[1]"))
    )
    driver.execute_script("arguments[0].click();", new_webcast_btn)

    # Step 1 — Title
    webcast_title_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@id='streamName']")))
    webcast_title_input.send_keys(title)
    time.sleep(3)

    next_btn_1 = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Next']")))
    driver.execute_script("arguments[0].click();", next_btn_1)

    # Step 2 — Date / Time / Duration
    webcast_date = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Select date']")))
    webcast_date.click()
    select_date = wait.until(EC.presence_of_element_located((By.XPATH, "//div[normalize-space()='25']")))
    driver.execute_script("arguments[0].click();", select_date)

    webcast_time = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Select time']")))
    webcast_time.click()
    select_time = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//ul[@data-type='hour']//div[@class='ant-picker-time-panel-cell-inner'][normalize-space()='03']")
    ))
    driver.execute_script("arguments[0].click();", select_time)

    webcast_duration = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Select duration']")))
    webcast_duration.click()
    select_duration = wait.until(EC.presence_of_element_located(
        (By.XPATH, "(//div[@class='ant-picker-time-panel-cell-inner'][normalize-space()='01'])[3]")
    ))
    driver.execute_script("arguments[0].click();", select_duration)

    next_btn_2 = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Next']")))
    driver.execute_script("arguments[0].click();", next_btn_2)

    # Step 3 — Signal
    signal = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='acquisitionSignal']")))
    driver.execute_script("arguments[0].style.display = 'block';", signal)
    driver.execute_script("arguments[0].click();", signal)

    next_btn_3 = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Next']")))
    driver.execute_script("arguments[0].click();", next_btn_3)

    # Create
    create_btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//button[@class='save-button d-flex flex-row justify-items-center']")
    ))
    driver.execute_script("arguments[0].click();", create_btn)

    time.sleep(3)
    wait.until(EC.presence_of_element_located((By.ID, "swal2-html-container")))
    print(f"  ✅ Webcast '{title}' created.")


NAME_XPATH = ".//div[contains(@class,'webcast-summary-event-name')]//div[contains(@class,'webcast-summary-background')]"
SWITCH_XPATH = ".//div[contains(@class,'webcast-summary-activate')]//button[@role='switch']"


def _activate_and_manage_webcast(driver, wait, title):
    """Find the not-yet-activated webcast by title, activate it, then open its Manage page.

    The 'Activate' control is an antd toggle switch — clicking it on an
    already-activated webcast DEACTIVATES it, so we must only ever click a
    switch whose aria-checked is 'false' (skips stale duplicates from old runs).
    """
    def get_summaries():
        return wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "webcast-summary")))

    try:
        summaries = get_summaries()
        print(f"  Found {len(summaries)} webcast summaries.")
    except Exception as e:
        pytest.fail(f"Could not find webcast summaries. Error: {e}")

    target_index = None
    for idx, summary in enumerate(summaries):
        try:
            name = summary.find_element(By.XPATH, NAME_XPATH).text.strip()
            if name.casefold() != title.casefold():
                continue
            switch = summary.find_element(By.XPATH, SWITCH_XPATH)
            if switch.get_attribute("aria-checked") == "true":
                print(f"  ⚠️ Skipping already-activated duplicate of '{title}'.")
                continue
            target_index = idx
            break
        except Exception:
            continue

    if target_index is None:
        pytest.fail(f"No unactivated webcast '{title}' found in summaries.")

    print(f"  ✅ Found webcast '{title}' (summary #{target_index}).")
    switch = summaries[target_index].find_element(By.XPATH, SWITCH_XPATH)
    driver.execute_script("arguments[0].click();", switch)
    print("  Clicked 'Activate' switch.")

    _wait_for_swal(driver, "activate", expect="success")
    time.sleep(2)

    # Re-fetch (the list re-renders after activation) and open Manage at the same index.
    summaries = get_summaries()
    if target_index >= len(summaries):
        pytest.fail(f"Summary list shrank after activating '{title}'.")
    updated = summaries[target_index]
    updated_name = updated.find_element(By.XPATH, NAME_XPATH).text.strip()
    if updated_name.casefold() != title.casefold():
        pytest.fail(f"Summary order changed after activation — expected '{title}', got '{updated_name}'.")

    manage_btn = WebDriverWait(updated, 10).until(
        EC.element_to_be_clickable((By.XPATH, ".//div[contains(@class,'webcast-manage-column')]//button"))
    )
    driver.execute_script("arguments[0].click();", manage_btn)
    print(f"  ✅ Manage page opened for '{title}'.")


SLIDE_INPUT_XPATH = "//input[@type='file' and contains(@accept,'pdf')]"
VIDEO_INPUT_XPATH = "//input[@type='file' and contains(@accept,'video')]"
HEADSHOT_INPUT_XPATH = "//input[@type='file' and contains(@accept,'image')]"
AUDIO_INPUT_XPATH = "//input[@type='file' and contains(@accept,'audio')]"
SAVE_BTN_XPATH = "(//button[normalize-space()='Save'])[1]"


def _set_webcast_type(driver, wait, type_label):
    """On the Manage page, open 'Webcast details' and set the webcast type.

    `#webcastType` is an antd Select (combobox) — typing into it and saving does
    NOT commit a value (antd discards unconfirmed search text). The type must be
    picked from the dropdown: click the selector to open it, then click the
    option whose `title` matches the label exactly. Changing the type is what
    controls which file inputs the Content page exposes, so this must stick.
    """
    details_btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, "(//button[normalize-space()='Webcast details'])[1]")
    ))
    driver.execute_script("arguments[0].click();", details_btn)
    time.sleep(1)

    # Open the Select (native click — antd opens the listbox on mousedown).
    selector = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//input[@id='webcastType']/ancestor::div[contains(@class,'ant-select-selector')][1]")
    ))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", selector)
    time.sleep(0.5)
    selector.click()
    time.sleep(1)

    # Pick the option by its exact title (the env label must match a real option).
    option = wait.until(EC.element_to_be_clickable(
        (By.XPATH, f"//div[contains(@class,'ant-select-item-option')][@title='{type_label}']")
    ))
    driver.execute_script("arguments[0].click();", option)
    time.sleep(1)

    selected = driver.find_element(
        By.XPATH, "//span[contains(@class,'ant-select-selection-item')]"
    ).get_attribute("title")
    if selected != type_label:
        pytest.fail(f"Webcast type not selected: wanted '{type_label}', selector shows '{selected}'.")

    save_btn = wait.until(EC.presence_of_element_located((By.XPATH, SAVE_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", save_btn)
    _wait_for_swal(driver, "webcast_type_save", timeout=60, expect="success")
    print(f"  ✅ Webcast type set to '{type_label}'.")
    time.sleep(2)


# Each content file's input locator, the config key holding its path, how long to
# let the dropzone settle after attaching, and how long Save may take server-side.
_FILE_INPUT = {
    "slide":    SLIDE_INPUT_XPATH,
    "video":    VIDEO_INPUT_XPATH,
    "headshot": HEADSHOT_INPUT_XPATH,
    "audio":    AUDIO_INPUT_XPATH,
}
_FILE_PATH_KEY = {
    "slide": "slide_path", "video": "video_path",
    "headshot": "headshot_path", "audio": "audio_path",
}
_FILE_SETTLE = {"slide": 5, "video": 3, "headshot": 2, "audio": 3}
_FILE_SAVE_TIMEOUT = {"slide": 60, "video": 180, "headshot": 60, "audio": 180}

# Per webcast type: the ordered (state, file) uploads. Slides go to both Preview
# and Live; the primary media (video/audio) + headshot are Preview-only.
CONTENT_SPECS = {
    "VxS": [("preview", "slide"), ("live", "slide"), ("preview", "video")],
    "AxS": [("preview", "slide"), ("preview", "headshot"), ("preview", "audio"), ("live", "slide")],
    "V":   [("preview", "video")],
    "A":   [("preview", "headshot"), ("preview", "audio")],
    "AxE": [("preview", "slide"), ("preview", "headshot"), ("preview", "audio"), ("live", "slide")],
}


def _open_content_panel(driver, wait):
    """Open the Content panel (must be re-opened after each status switch)."""
    time.sleep(1)
    content_btn = wait.until(
        EC.presence_of_element_located((By.XPATH, "(//button[normalize-space()='Content'])[1]"))
    )
    driver.execute_script("arguments[0].click();", content_btn)
    time.sleep(2)


def _switch_status(driver, wait, from_state, to_state):
    """Switch the Preview/Live status dropdown.

    The dropdown is an antd Select — it opens on the native mousedown (a JS
    .click() won't open it), but the option in the menu needs a JS click since
    a toast can intercept the native one.
    """
    src, dst = from_state.capitalize(), to_state.capitalize()
    dropdown = wait.until(EC.presence_of_element_located((By.XPATH, f"//span[@title='{src}']")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dropdown)
    time.sleep(0.5)
    dropdown.click()
    option = wait.until(EC.presence_of_element_located((By.XPATH, f"//div[contains(text(),'{dst}')]")))
    driver.execute_script("arguments[0].click();", option)
    time.sleep(1)


def _upload_one(driver, wait, config, file_key):
    """Attach a single file to its dropzone and commit it with its own Save."""
    path = config.get(_FILE_PATH_KEY[file_key])
    if not path:
        pytest.fail(f"No path configured for '{file_key}' — check .env / conftest config.")

    file_input = wait.until(EC.presence_of_element_located((By.XPATH, _FILE_INPUT[file_key])))
    file_input.send_keys(path)
    time.sleep(_FILE_SETTLE[file_key])  # let the dropzone read the file before saving

    save_btn = wait.until(EC.presence_of_element_located((By.XPATH, SAVE_BTN_XPATH)))
    driver.execute_script("arguments[0].click();", save_btn)
    _wait_for_swal(driver, f"{file_key}_save", timeout=_FILE_SAVE_TIMEOUT[file_key], expect="success")
    print(f"  ✅ {file_key} saved.")
    time.sleep(2)


def _upload_content(driver, wait, config, type_key):
    """Upload the content set required by `type_key` per CONTENT_SPECS.

    The dropzone file inputs are targeted by their `accept` attribute, and each
    file is committed by its own Save (audio/video saves can take well over 30s
    in prod due to server-side processing — hence the long per-file timeouts).
    """
    spec = CONTENT_SPECS[type_key]
    current_state = "preview"  # webcasts open in Preview by default
    panel_open = False

    for state, file_key in spec:
        if state != current_state:
            _switch_status(driver, wait, current_state, state)
            current_state = state
            panel_open = False  # status switch closes/re-renders the panel
        if not panel_open:
            _open_content_panel(driver, wait)
            panel_open = True
        _upload_one(driver, wait, config, file_key)



def _configure_layout_and_go_back(driver, wait, type_key=None):
    """Configure webcast layout settings then click Back to return to Sessions."""
    layout_btn = wait.until(EC.presence_of_element_located(
        (By.XPATH, "(//button[normalize-space()='Webcast Layout'])[1]")
    ))
    driver.execute_script("arguments[0].click();", layout_btn)

    # AxE webcast type requires enabling the first toggle switch on the layout page.
    if type_key == "AxE":
        axe_switch = wait.until(EC.presence_of_element_located(
            (By.XPATH, "(//button[@role='switch'])[1]")
        ))
        driver.execute_script("arguments[0].scrollIntoView(true);", axe_switch)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", axe_switch)
        print("  Clicked AxE layout switch (//button[@role='switch'])[1].")

    # Title
    preview_title = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Title']")))
    driver.execute_script("arguments[0].scrollIntoView(true);", preview_title)
    preview_title.clear()
    preview_title.send_keys("Automated Preview Text Title!")

    # Description
    preview_desc = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Description']")))
    driver.execute_script("arguments[0].scrollIntoView(true);", preview_desc)
    preview_desc.clear()
    preview_desc.send_keys("This is Automation test preview text for testing.")

    # Toggle switches: logo, Q&A, slider list
    switches = {
        "logo":        "(//button[@role='switch'])[2]",
        "qna":         "(//button[@role='switch'])[4]",
        "slider_list": "(//button[@role='switch'])[6]",
    }
    for key, xpath in switches.items():
        switch_btn = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView(true);", switch_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", switch_btn)

    # Save layout
    save_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Save']")))
    driver.execute_script("arguments[0].scrollIntoView(true);", save_btn)
    driver.execute_script("arguments[0].click();", save_btn)
    _wait_for_swal(driver, "layout_save", timeout=60)
    print(f"  ✅ Layout saved.")

    time.sleep(1)
    back_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Back']")))
    driver.execute_script("arguments[0].click();", back_btn)
    print(f"  ↩️  Clicked Back — returned to Sessions page.")
    time.sleep(2)


def _delete_all_webcasts(driver, wait, 
title_prefix="Automated Webcast"):
    """Delete every webcast whose name starts with `title_prefix`.

    Each delete opens a 'Delete Webcast — Are you sure...?' antd modal that
    must be confirmed via its footer 'Confirm' button.
    """
    time.sleep(1)
    deleted = 0
    while True:
        try:
            summaries = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "webcast-summary"))
            )
        except TimeoutException:
            break  # no webcasts left at all

        target = None
        for summary in summaries:
            try:
                name = summary.find_element(By.XPATH, NAME_XPATH).text.strip()
            except Exception:
                continue
            if name.startswith(title_prefix):
                target = (summary, name)
                break
        if target is None:
            break

        summary, name = target
        before = len(summaries)
        trash = summary.find_element(By.XPATH, ".//div[contains(@class,'webcast-summary-delete')]//button")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", trash)
        trash.click()
        confirm = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class,'ant-modal-footer')]//button[normalize-space()='Confirm']")
        ))
        confirm.click()
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
        time.sleep(2)
        deleted += 1
        print(f"  🗑️ Deleted '{name}' ({before} -> {before - 1}).")

    print(f"  Cleanup done — {deleted} webcast(s) deleted.")


# ----------------------- TEST CASES -----------------------

def test_00_cleanup(config):
    """Start every run clean: delete 'Automated Webcast *' leftovers.

    Uses its own short-lived headless browser so the main session driver
    still starts logged-out for test_01_login.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    cleanup_driver = webdriver.Chrome(options=options)
    cleanup_driver.implicitly_wait(5)
    try:
        # Login
        cleanup_driver.get(config["url_org"])
        cleanup_driver.find_element(By.ID, 'email').send_keys(config["email_org"])
        cleanup_driver.find_element(By.ID, 'password').send_keys(config["password_org"])
        cleanup_driver.find_element(By.CLASS_NAME, 'login-button').click()
        WebDriverWait(cleanup_driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'header-title'))
        )

        # Open target portal
        wait = WebDriverWait(cleanup_driver, 30)
        search_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search portal']")))
        search_box.send_keys(config["target_portal"])
        edit_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Edit']")))
        cleanup_driver.execute_script("arguments[0].click();", edit_btn)
        wait.until(EC.presence_of_element_located((By.XPATH, "(//p[@class='branding-information-text mt-1'])[1]")))

        # Sessions page
        time.sleep(2)
        session_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Sessions')]")))
        cleanup_driver.execute_script("arguments[0].click();", session_btn)
        time.sleep(3)

        _delete_all_webcasts(cleanup_driver, wait)
    finally:
        cleanup_driver.quit()


def test_01_login(driver, config):
    driver.get(config["url_org"])
    driver.find_element(By.ID, 'email').send_keys(config["email_org"])
    driver.find_element(By.ID, 'password').send_keys(config["password_org"])
    driver.find_element(By.CLASS_NAME, 'login-button').click()

    wait = WebDriverWait(driver, 60)
    welcome_text = wait.until(
        EC.presence_of_element_located((By.CLASS_NAME, 'header-title'))
    ).text

    assert 'Welcome' in welcome_text, "Login failed — 'Welcome' not found."
    print(f"✅ Login successful: {welcome_text}")


def test_02_open_target_portal(driver, config):
    wait = WebDriverWait(driver, 30)
    search_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search portal']")))
    # No .click() — a post-login toast can briefly cover the box and intercept it;
    # send_keys focuses the input on its own.
    search_box.send_keys(config["target_portal"])

    edit_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Edit']")))
    driver.execute_script("arguments[0].click();", edit_btn)

    portal_title = wait.until(
        EC.presence_of_element_located((By.XPATH, "(//p[@class='branding-information-text mt-1'])[1]"))
    ).text

    assert "Portal" in portal_title, "Portal title validation failed."
    print(f"✅ Opened portal: {portal_title}")


def test_03_create_all_webcasts(driver, config):
    """Create, activate, set type, upload the type's content, and configure layout."""
    wait = WebDriverWait(driver, 30)

    # (title, webcast-type label to pick in 'Webcast details', content spec key)
    webcasts = [
        (config["webcast_titles"][0], config["webcast_type_1"], "VxS"),
        (config["webcast_titles"][1], config["webcast_type_2"], "AxS"),
        (config["webcast_titles"][2], config["webcast_type_3"], "V"),
        (config["webcast_titles"][3], config["webcast_type_4"], "A"),
        (config["webcast_titles"][4], config["webcast_type_5"], "AxE"),
    ]

    # --webcast-type=<KEY> restricts the run to a single webcast of that type.
    single = config.get("single_webcast_type")
    if single:
        webcasts = [w for w in webcasts if w[2] == single]
        if not webcasts:
            pytest.fail(f"No webcast defined for type '{single}' — choose one of: VxS, AxS, V, A, AxE.")
        print(f"\nSingle-webcast mode: creating only the '{single}' webcast.")

    for i, (title, type_label, type_key) in enumerate(webcasts, start=1):
        print(f"\n{'='*60}")
        print(f"  WEBCAST {i}/{len(webcasts)}: '{title}'  [{type_key}: {type_label}]")
        print(f"{'='*60}")

        _navigate_and_create_webcast(driver, wait, title)
        _activate_and_manage_webcast(driver, wait, title)
        _set_webcast_type(driver, wait, type_label)
        _upload_content(driver, wait, config, type_key)
        _configure_layout_and_go_back(driver, wait, type_key)

        print(f"  🎉 Webcast {i}/{len(webcasts)} '{title}' fully done!\n")

    print("✅ All webcasts created and configured successfully!")
