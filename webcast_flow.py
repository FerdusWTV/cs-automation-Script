"""The ConnectStudio admin workflows, as readable step-by-step functions.

Each function here is one thing a human would do in the UI. The tests in
`session_test.py` just call them in order; the locators live in `locators.py`
and the click/wait plumbing in `ui.py`.

The end-to-end shape of a webcast:

    create_webcast()          # Sessions -> new webcast wizard
    activate_and_open_manage()# flip the Activate switch, open Manage
    set_webcast_type()        # Webcast details -> type combobox
    upload_content()          # Content -> per-type files, each with its own Save
    configure_layout()        # Webcast Layout -> title/description/toggles
"""

import time

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import locators as L
import ui


# ==========================================================================
# Login / portal
# ==========================================================================

def login(driver, config, timeout=60):
    """Log into the admin org and return the welcome-header text."""
    driver.get(config["url_org"])
    driver.find_element(By.ID, L.EMAIL_INPUT_ID).send_keys(config["email_org"])
    driver.find_element(By.ID, L.PASSWORD_INPUT_ID).send_keys(config["password_org"])
    driver.find_element(By.CLASS_NAME, L.LOGIN_BTN_CLASS).click()

    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, L.WELCOME_HEADER_CLASS))
    ).text


def open_portal(driver, wait, portal_name):
    """Search for a portal and open it for editing. Returns the portal title."""
    # No .click() on the search box — a post-login toast can briefly cover it and
    # intercept the click; send_keys focuses the input by itself.
    ui.type_text(driver, wait, L.PORTAL_SEARCH_INPUT, portal_name)
    ui.click(driver, wait, L.PORTAL_EDIT_BTN)
    return ui.find(wait, L.PORTAL_TITLE).text


def open_sessions_page(driver, wait):
    """Navigate to the Sessions list."""
    time.sleep(2)
    ui.click(driver, wait, L.SESSIONS_NAV_BTN)


# ==========================================================================
# Creating a webcast
# ==========================================================================

def create_webcast(driver, wait, title):
    """Run the new-webcast wizard end to end: title, schedule, signal, create."""
    open_sessions_page(driver, wait)
    ui.click(driver, wait, L.NEW_WEBCAST_GROUP_BTN)
    ui.click(driver, wait, L.NEW_WEBCAST_MODAL_BTN)
    run_new_webcast_wizard(driver, wait, title)


def run_new_webcast_wizard(driver, wait, title):
    """Steps 1-4 of the new-webcast wizard, once its first screen is open.

    Split out from `create_webcast` so the embedded suite can reuse it: embedded
    mode opens the wizard from its own single-option tile, but every step after
    that is identical.
    """
    # Step 1 — title
    ui.type_text(driver, wait, L.WIZARD_TITLE_INPUT, title)
    time.sleep(3)
    ui.click(driver, wait, L.WIZARD_NEXT_BTN)

    # Step 2 — date / time / duration (fixed test values: 25th, 03:00, 1 hour)
    ui.native_click(driver, wait, L.WIZARD_DATE_INPUT, scroll=False)
    ui.click(driver, wait, L.WIZARD_DATE_CELL)

    ui.native_click(driver, wait, L.WIZARD_TIME_INPUT, scroll=False)
    ui.click(driver, wait, L.WIZARD_TIME_CELL)

    ui.native_click(driver, wait, L.WIZARD_DURATION_INPUT, scroll=False)
    ui.click(driver, wait, L.WIZARD_DURATION_CELL)

    ui.click(driver, wait, L.WIZARD_NEXT_BTN)

    # Step 3 — acquisition signal (the radio is hidden until we un-hide it)
    signal = ui.find(wait, L.WIZARD_SIGNAL_INPUT)
    ui.reveal(driver, signal)
    ui.js_click(driver, signal)
    ui.click(driver, wait, L.WIZARD_NEXT_BTN)

    ui.click(driver, wait, L.WIZARD_CREATE_BTN)

    time.sleep(3)
    wait.until(EC.presence_of_element_located((By.ID, L.SWAL_CONTAINER_ID)))
    print(f"  ✅ Webcast '{title}' created.")


# ==========================================================================
# Activating + opening the Manage page
# ==========================================================================

def _summaries(driver, wait):
    return wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, L.SUMMARY_CLASS)))


def _summary_name(summary):
    return summary.find_element(By.XPATH, L.SUMMARY_NAME).text.strip()


def activate_and_open_manage(driver, wait, title):
    """Activate the named webcast, then open its Manage page.

    'Activate' is an antd toggle switch, so clicking it on an already-activated
    webcast would DEACTIVATE it. We therefore only click a switch whose
    aria-checked is 'false', which also skips stale duplicates from old runs.
    """
    try:
        summaries = _summaries(driver, wait)
        print(f"  Found {len(summaries)} webcast summaries.")
    except Exception as e:
        pytest.fail(f"Could not find webcast summaries. Error: {e}")

    target_index = _find_unactivated(summaries, title)
    if target_index is None:
        pytest.fail(f"No unactivated webcast '{title}' found in summaries.")
    print(f"  ✅ Found webcast '{title}' (summary #{target_index}).")

    switch = summaries[target_index].find_element(By.XPATH, L.SUMMARY_ACTIVATE_SWITCH)
    ui.js_click(driver, switch)
    print("  Clicked 'Activate' switch.")

    ui.wait_for_swal(driver, "activate", expect="success")
    time.sleep(2)

    # The list re-renders after activation — re-fetch and confirm the row at our
    # index is still the webcast we activated before opening Manage.
    summaries = _summaries(driver, wait)
    if target_index >= len(summaries):
        pytest.fail(f"Summary list shrank after activating '{title}'.")

    updated = summaries[target_index]
    updated_name = _summary_name(updated)
    if updated_name.casefold() != title.casefold():
        pytest.fail(f"Summary order changed after activation — expected '{title}', got '{updated_name}'.")

    manage_btn = WebDriverWait(updated, 10).until(
        EC.element_to_be_clickable((By.XPATH, L.SUMMARY_MANAGE_BTN))
    )
    ui.js_click(driver, manage_btn)
    print(f"  ✅ Manage page opened for '{title}'.")


def _find_unactivated(summaries, title):
    """Index of the first row named `title` whose Activate switch is still off."""
    for idx, summary in enumerate(summaries):
        try:
            if _summary_name(summary).casefold() != title.casefold():
                continue
            switch = summary.find_element(By.XPATH, L.SUMMARY_ACTIVATE_SWITCH)
            if switch.get_attribute("aria-checked") == "true":
                print(f"  ⚠️ Skipping already-activated duplicate of '{title}'.")
                continue
            return idx
        except Exception:
            continue
    return None


# ==========================================================================
# Webcast type
# ==========================================================================

def set_webcast_type(driver, wait, type_label):
    """Open 'Webcast details' and set the webcast type, then Save.

    The type combobox is an antd Select: typing a value and saving does NOT
    commit it (antd discards unconfirmed search text) — and it fails silently,
    since the success popup still fires. The option must be picked from the open
    dropdown. This matters because the type decides which file inputs the
    Content panel exposes, so we verify the selection stuck before saving.
    """
    ui.click(driver, wait, L.WEBCAST_DETAILS_BTN)

    ui.native_click(driver, wait, L.WEBCAST_TYPE_SELECTOR)
    time.sleep(1)

    option = ui.find_clickable(wait, L.webcast_type_option(type_label))
    ui.js_click(driver, option)
    time.sleep(1)

    selected = driver.find_element(By.XPATH, L.WEBCAST_TYPE_SELECTED).get_attribute("title")
    if selected != type_label:
        pytest.fail(f"Webcast type not selected: wanted '{type_label}', selector shows '{selected}'.")

    ui.click(driver, wait, L.SAVE_BTN)
    ui.wait_for_swal(driver, "webcast_type_save", timeout=60, expect="success")
    print(f"  ✅ Webcast type set to '{type_label}'.")
    time.sleep(2)


# ==========================================================================
# Content uploads
# ==========================================================================

# Everything that differs per file type, in one table. To support a new file
# type, add a row here and a locator in locators.py.
#
#   input   — the dropzone's file input
#   path    — config key holding a single path
#   paths   — config key holding a LIST of paths (multi-file dropzones only)
#   settle  — seconds to let the dropzone read the file before Save
#   timeout — how long Save may take; audio/video are processed server-side
# Seconds to wait before trusting a dropzone that has just appeared — a save
# re-render shows an empty dropzone first and the persisted file list second.
SETTLE_RERENDER = 4

FILE_TYPES = {
    "slide":    {"input": L.SLIDE_INPUT,    "path": "slide_path",    "paths": None,              "settle": 5, "timeout": 60},
    "video":    {"input": L.VIDEO_INPUT,    "path": "video_path",    "paths": None,              "settle": 3, "timeout": 180},
    "headshot": {"input": L.HEADSHOT_INPUT, "path": "headshot_path", "paths": "headshot_paths",  "settle": 4, "timeout": 60},
    "audio":    {"input": L.AUDIO_INPUT,    "path": "audio_path",    "paths": None,              "settle": 3, "timeout": 180},
}

# Which files each webcast type needs, and in which Preview/Live state.
# Slides go to both Preview and Live; the primary media (video/audio) and the
# headshot are Preview-only. Webcasts open in Preview, so a spec that keeps all
# its Preview work together does the fewest status switches.
# Audio comes BEFORE headshot on every audio type: the headshot dropzone is only
# rendered once the section holds an audio file, so attaching it first times out
# looking for an input that isn't in the DOM yet.
CONTENT_SPECS = {
    "VxS": [("preview", "slide"), ("live", "slide"), ("preview", "video")],
    "AxS": [("preview", "slide"), ("preview", "audio"), ("preview", "headshot"), ("live", "slide")],
    "V":   [("preview", "video")],
    "A":   [("preview", "audio"), ("preview", "headshot")],
    "AxE": [("preview", "slide"), ("preview", "audio"), ("preview", "headshot"), ("live", "slide")],
}


def upload_content(driver, wait, config, type_key):
    """Upload every file this webcast type needs, per CONTENT_SPECS.

    Each file is committed by its own click of the single bottom Save button.
    Switching Preview/Live re-renders the panel, so the Content panel has to be
    re-opened after every switch.
    """
    current_state = "preview"  # webcasts open in Preview by default
    panel_open = False

    for state, file_key in CONTENT_SPECS[type_key]:
        if state != current_state:
            switch_status(driver, wait, current_state, state)
            current_state = state
            panel_open = False  # the status switch closed/re-rendered the panel
        if not panel_open:
            open_content_panel(driver, wait)
            panel_open = True
        upload_file(driver, wait, config, file_key)


def open_content_panel(driver, wait):
    """Open the Content panel (must be re-opened after each status switch)."""
    time.sleep(1)
    ui.click(driver, wait, L.CONTENT_BTN, settle=2)


def switch_status(driver, wait, from_state, to_state):
    """Switch the Preview/Live status dropdown.

    It's an antd Select, so it opens only on a native mousedown — but the option
    inside needs a JS click, since a toast can intercept the native one.
    """
    ui.native_click(driver, wait, L.status_dropdown(from_state.capitalize()))
    ui.click(driver, wait, L.status_option(to_state.capitalize()), settle=1)


def upload_file(driver, wait, config, file_key):
    """Attach a file (or files) to its dropzone and commit it with its own Save.

    `headshot_paths` may hold several images, and the headshot dropzone takes
    them one at a time: it is replaced by the uploaded-file list on the first
    attach, and only reappears via the 'Upload More' button that the SAVED
    gallery renders. So each extra image costs its own Upload More + Save round
    trip (see `_upload_one_more`). A `multiple` input, if the app ever renders
    one, still takes the whole set in a single newline-joined send_keys.
    """
    spec = FILE_TYPES[file_key]
    paths = _resolve_paths(config, spec, file_key)

    _clear_existing_media(driver, wait, file_key)

    file_input = _find_dropzone(driver, wait, file_key, spec, clear_retry=True)

    if len(paths) > 1 and file_input.get_attribute("multiple"):
        file_input.send_keys("\n".join(paths))
        print(f"  📎 Attached {len(paths)} {file_key} files.")
        extra_paths = []
    else:
        file_input.send_keys(paths[0])
        extra_paths = paths[1:]

    time.sleep(spec["settle"])  # let the dropzone read the file before saving
    _save(driver, wait, file_key, spec)
    print(f"  ✅ {file_key} saved" + (f" (1/{len(paths)})." if extra_paths else "."))

    for n, path in enumerate(extra_paths, start=2):
        _upload_one_more(driver, wait, file_key, spec, path, n, len(paths))


def _save(driver, wait, file_key, spec):
    """Click the panel's single Save button and assert the success popup."""
    ui.click(driver, wait, L.SAVE_BTN)
    ui.wait_for_swal(driver, f"{file_key}_save", timeout=spec["timeout"], expect="success")
    time.sleep(2)


def _upload_one_more(driver, wait, file_key, spec, path, n, total):
    """Add one more file to a single-file section via its 'Upload More' button.

    Once saved, the section renders a gallery ('Uploaded headshots') instead of a
    dropzone, and 'Upload More' is what brings the dropzone back. The dropzone
    also carries a 'Browse' button — deliberately not clicked, since that opens
    the OS file dialog, which Selenium cannot drive; the path goes straight to
    the <input type=file> rendered beside it.
    """
    gallery = L.GALLERY_LABELS.get(file_key)
    if gallery is None:
        pytest.fail(f"No gallery label known for '{file_key}' — cannot upload more than one.")

    ui.click(driver, wait, L.upload_more(gallery), scroll=True, settle=2)

    # clear_retry=False: the files already saved in this section must survive.
    _find_dropzone(driver, wait, file_key, spec).send_keys(path)
    time.sleep(spec["settle"])

    _save(driver, wait, file_key, spec)
    print(f"  ✅ {file_key} saved ({n}/{total}).")


def _resolve_paths(config, spec, file_key):
    """The list of local file paths to upload for this file type."""
    paths = config.get(spec["paths"]) or [] if spec["paths"] else []
    if not paths:
        single = config.get(spec["path"])
        paths = [single] if single else []
    if not paths:
        pytest.fail(f"No path configured for '{file_key}' — check .env / conftest config.")
    return paths


def _clear_existing_media(driver, wait, file_key, timeout=20):
    """Cancel a file already in this section so its dropzone reappears.

    A section that already holds a file renders the uploaded-file list instead
    of a raw <input type=file>, so the upload would otherwise time out looking
    for a dropzone that isn't there. A new webcast ships with a DEFAULT VIDEO,
    which is why this always applies to the video upload.

    Clicking the 'x' on the uploaded file removes it and brings the dropzone
    back. This applies to video and to the headshot: headshots belong to the
    speaker rather than the webcast, so a brand-new webcast can already show one
    left over from an earlier run.

    Returns True if something was cleared.
    """
    if file_key == "video":
        xpath = L.UPLOADED_FILE_CANCEL_BTN
    elif file_key in L.SECTION_LABELS:
        xpath = L.uploaded_file_clear(L.SECTION_LABELS[file_key])
    else:
        return False

    # Poll rather than checking once. Saving the previous file re-renders the
    # whole Content panel, and the lower sections ('Upload headshot' on the
    # audio types) mount a beat later and below the fold — a single no-wait
    # check misses the leftover file, and then the dropzone never appears at
    # all, because a section holding a file renders a file list instead.
    deadline = time.monotonic() + timeout
    while True:
        if ui.exists(driver, xpath):
            ui.click(driver, wait, xpath, scroll=True, settle=2)
            print(f"  🗑️ Cancelled the existing {file_key} before uploading.")
            return True
        if ui.exists(driver, FILE_TYPES[file_key]["input"]):
            return False  # dropzone is already there — nothing to clear
        if time.monotonic() >= deadline:
            return False
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)


def _find_dropzone(driver, wait, file_key, spec, clear_retry=False, timeout=90):
    """Find this file type's input, reporting what IS on the page if it's absent.

    Two things make this more than a `find`:

    * Lower sections of the Content panel — notably 'Upload headshot' on the
      audio types — are only mounted once they're scrolled near.
    * Saving a file re-renders the whole panel, and the render lands in two
      steps: an empty dropzone appears first, then gets replaced by the file
      list for any file the section already holds (a headshot persists at
      speaker level, so it survives webcast cleanup). Accepting the input on
      first sight therefore hands back a node that is about to be thrown away.

    So the input is only accepted if it is STILL there a moment later, and a
    leftover file found in the meantime is cleared and the search resumed.

    `clear_retry=False` skips all of that and does a plain find — that's the
    re-find between multi-file attaches, which must not clear what it attached.
    """
    if not clear_retry:
        return ui.find(driver, spec["input"], timeout=15)

    deadline = time.monotonic() + timeout
    scrolled = False

    while True:
        _clear_existing_media(driver, wait, file_key, timeout=0)

        if ui.exists(driver, spec["input"]):
            time.sleep(SETTLE_RERENDER)  # let any pending re-render land
            try:
                # Re-find rather than reusing the earlier hit: the re-render
                # would have made that reference stale.
                return ui.find(driver, spec["input"], timeout=5)
            except TimeoutException:
                # Replaced after all — go round again; the next pass clears the
                # file that replaced it.
                print(f"  ↻ '{file_key}' dropzone was replaced on re-render — retrying.")
                continue

        if not scrolled:
            print(f"  🔍 no '{file_key}' input yet — scrolling to mount the lower sections.")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            scrolled = True
            time.sleep(2)
            continue

        if time.monotonic() >= deadline:
            _dump_dropzone_failure(driver, file_key)
            raise TimeoutException(
                f"No '{file_key}' file input appeared within {timeout}s — "
                f"diagnostics saved to failure_{file_key}_dropzone.png/.html"
            )
        time.sleep(1)


def _dump_dropzone_failure(driver, file_key):
    """Print what IS on the page and save a screenshot + page source."""
    accepts = [e.get_attribute("accept") for e in ui.find_all(driver, L.ANY_FILE_INPUT)]
    buttons = [b.text.strip() for b in driver.find_elements(By.XPATH, "//button") if b.text.strip()]
    print(f"  ❌ no '{file_key}' input. file inputs on page: {accepts}")
    print(f"     buttons on page: {buttons}")
    driver.save_screenshot(f"failure_{file_key}_dropzone.png")
    with open(f"failure_{file_key}_dropzone.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)


# ==========================================================================
# Webcast layout
# ==========================================================================

# Positional toggle switches on the layout page — they carry no stable id.
LAYOUT_SWITCHES = {
    "axe_mode":    1,  # only enabled for the AxE webcast type
    "logo":        2,
    "qna":         4,
    "slider_list": 6,
}

PREVIEW_TITLE_TEXT = "Automated Preview Text Title!"
PREVIEW_DESC_TEXT = "This is Automation test preview text for testing."


def configure_layout(driver, wait, type_key=None):
    """Set the layout title, description and toggles, save, then go Back."""
    ui.click(driver, wait, L.WEBCAST_LAYOUT_BTN)

    if type_key == "AxE":
        ui.click(driver, wait, L.layout_switch(LAYOUT_SWITCHES["axe_mode"]), scroll=True, center=False)
        print(f"  Clicked AxE layout switch ({L.layout_switch(LAYOUT_SWITCHES['axe_mode'])}).")

    ui.type_text(driver, wait, L.LAYOUT_TITLE_INPUT, PREVIEW_TITLE_TEXT, clear=True, scroll=True)
    ui.type_text(driver, wait, L.LAYOUT_DESC_INPUT, PREVIEW_DESC_TEXT, clear=True, scroll=True)

    for name in ("logo", "qna", "slider_list"):
        ui.click(driver, wait, L.layout_switch(LAYOUT_SWITCHES[name]), scroll=True, center=False)

    ui.click(driver, wait, L.LAYOUT_SAVE_BTN, scroll=True, center=False, pause=0)
    ui.wait_for_swal(driver, "layout_save", timeout=60)
    print("  ✅ Layout saved.")

    time.sleep(1)
    ui.click(driver, wait, L.BACK_BTN)
    print("  ↩️  Clicked Back — returned to Sessions page.")
    time.sleep(2)


# ==========================================================================
# Cleanup
# ==========================================================================

def delete_all_webcasts(driver, wait, title_prefix="Automated Webcast"):
    """Delete every webcast whose name starts with `title_prefix`.

    Each delete opens a 'Delete Webcast — Are you sure...?' antd modal that must
    be confirmed via its footer 'Confirm' button (NOT the primary button).
    """
    time.sleep(1)
    deleted = 0

    while True:
        try:
            summaries = _summaries(driver, WebDriverWait(driver, 10))
        except TimeoutException:
            break  # no webcasts left at all

        target = _first_matching(summaries, title_prefix)
        if target is None:
            break

        summary, name = target
        before = len(summaries)

        trash = summary.find_element(By.XPATH, L.SUMMARY_DELETE_BTN)
        ui.scroll_into_view(driver, trash)
        trash.click()

        confirm = ui.find_clickable(wait, L.MODAL_CONFIRM_BTN)
        confirm.click()
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, L.MODAL_MASK_CSS)))
        time.sleep(2)

        deleted += 1
        print(f"  🗑️ Deleted '{name}' ({before} -> {before - 1}).")

    print(f"  Cleanup done — {deleted} webcast(s) deleted.")


def _first_matching(summaries, title_prefix):
    """The first (element, name) whose name starts with `title_prefix`."""
    for summary in summaries:
        try:
            name = _summary_name(summary)
        except Exception:
            continue
        if name.startswith(title_prefix):
            return summary, name
    return None
