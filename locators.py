"""Every XPath/selector the ConnectStudio suite uses, in one place.

Grouped by the screen it belongs to. When the app's markup changes, this is the
only file that should need editing — no locator strings live in the test or flow
code.

Naming: `*_BTN` / `*_INPUT` / `*_XPATH` for single elements. Locators starting
with `.//` are *relative* — they must be searched from within a parent element
(e.g. a `.webcast-summary` row), not from the driver.
"""

# --------------------------------------------------------------------------
# Login / portal selection
# --------------------------------------------------------------------------
EMAIL_INPUT_ID = "email"
PASSWORD_INPUT_ID = "password"
LOGIN_BTN_CLASS = "login-button"
WELCOME_HEADER_CLASS = "header-title"

PORTAL_SEARCH_INPUT = "//input[@placeholder='Search portal']"
PORTAL_EDIT_BTN = "//button[normalize-space()='Edit']"
PORTAL_TITLE = "(//p[@class='branding-information-text mt-1'])[1]"

# --------------------------------------------------------------------------
# Sessions page + the 'new webcast' wizard
# --------------------------------------------------------------------------
SESSIONS_NAV_BTN = "//div[contains(text(),'Sessions')]"
NEW_WEBCAST_GROUP_BTN = "//div[@class='session-button-group-right']"
NEW_WEBCAST_MODAL_BTN = "(//div[@class='stream-modal-container h-full'])[1]"

WIZARD_TITLE_INPUT = "//input[@id='streamName']"
WIZARD_NEXT_BTN = "//button[normalize-space()='Next']"
WIZARD_CREATE_BTN = "//button[@class='save-button d-flex flex-row justify-items-center']"

# Wizard step 2 — date / time / duration. The picked values are fixed test data:
# the 25th, 03:00, 01h duration.
WIZARD_DATE_INPUT = "//input[@placeholder='Select date']"
WIZARD_DATE_CELL = "//div[normalize-space()='25']"
WIZARD_TIME_INPUT = "//input[@placeholder='Select time']"
WIZARD_TIME_CELL = (
    "//ul[@data-type='hour']//div[@class='ant-picker-time-panel-cell-inner']"
    "[normalize-space()='03']"
)
WIZARD_DURATION_INPUT = "//input[@placeholder='Select duration']"
WIZARD_DURATION_CELL = "(//div[@class='ant-picker-time-panel-cell-inner'][normalize-space()='01'])[3]"

# Wizard step 3 — the acquisition-signal radio is visually hidden, so it has to
# be un-hidden via JS before it can be clicked.
WIZARD_SIGNAL_INPUT = "//input[@name='acquisitionSignal']"

# --------------------------------------------------------------------------
# A webcast row ('.webcast-summary') on the Sessions list — all RELATIVE
# --------------------------------------------------------------------------
SUMMARY_CLASS = "webcast-summary"
SUMMARY_NAME = (
    ".//div[contains(@class,'webcast-summary-event-name')]"
    "//div[contains(@class,'webcast-summary-background')]"
)
# antd toggle switch: clicking it on an ALREADY-activated webcast deactivates it,
# so always check aria-checked before clicking.
SUMMARY_ACTIVATE_SWITCH = ".//div[contains(@class,'webcast-summary-activate')]//button[@role='switch']"
SUMMARY_MANAGE_BTN = ".//div[contains(@class,'webcast-manage-column')]//button"
SUMMARY_DELETE_BTN = ".//div[contains(@class,'webcast-summary-delete')]//button"

# Delete confirmation modal ('Delete Webcast — Are you sure...?')
MODAL_CONFIRM_BTN = "//div[contains(@class,'ant-modal-footer')]//button[normalize-space()='Confirm']"
MODAL_MASK_CSS = ".ant-modal-mask"

# --------------------------------------------------------------------------
# Manage page — top-level section buttons
# --------------------------------------------------------------------------
WEBCAST_DETAILS_BTN = "(//button[normalize-space()='Webcast details'])[1]"
CONTENT_BTN = "(//button[normalize-space()='Content'])[1]"
WEBCAST_LAYOUT_BTN = "(//button[normalize-space()='Webcast Layout'])[1]"
BACK_BTN = "//button[normalize-space()='Back']"

# The Manage page has a single Save button shared by every panel.
SAVE_BTN = "(//button[normalize-space()='Save'])[1]"
LAYOUT_SAVE_BTN = "//button[normalize-space()='Save']"

# --------------------------------------------------------------------------
# Webcast details panel — the type combobox
# --------------------------------------------------------------------------
# antd Select: typing into it and saving does NOT commit (antd discards
# unconfirmed search text). The option must be clicked from the open dropdown.
WEBCAST_TYPE_SELECTOR = "//input[@id='webcastType']/ancestor::div[contains(@class,'ant-select-selector')][1]"
WEBCAST_TYPE_SELECTED = "//span[contains(@class,'ant-select-selection-item')]"


def webcast_type_option(label):
    """The dropdown option whose title matches `label` exactly."""
    return f"//div[contains(@class,'ant-select-item-option')][@title='{label}']"


# --------------------------------------------------------------------------
# Content panel
# --------------------------------------------------------------------------
# File inputs are identified by their `accept` attribute rather than by index,
# which is stable across layout changes.
SLIDE_INPUT = "//input[@type='file' and contains(@accept,'pdf')]"
# The audio dropzone also accepts 'video/mp4', so the video input must be
# distinguished by the ABSENCE of an audio/* accept — not by 'video' alone.
VIDEO_INPUT = "//input[@type='file' and contains(@accept,'video') and not(contains(@accept,'audio'))]"
HEADSHOT_INPUT = "//input[@type='file' and contains(@accept,'image')]"
AUDIO_INPUT = "//input[@type='file' and contains(@accept,'audio')]"

ANY_FILE_INPUT = "//input[@type='file']"

# Shown INSTEAD of a raw dropzone once a section already holds a file.
UPLOAD_MORE_BTN = "//button[normalize-space()='Upload More']"
SELECT_ALL_BTN = "//button[normalize-space()='Select All']"

# The 'x' on an already-uploaded file. A new webcast ships with a default video
# that must be cancelled before its dropzone reappears.
UPLOADED_FILE_CANCEL_BTN = "//div[@class='uploaded-files mt-3']//div[2]//*[name()='svg']"


def uploaded_file_clear(section_label):
    """The 'x' on the uploaded file in the section titled `section_label`.

    Scoped to one section: several sections show an uploaded-file list at once,
    so the unscoped locator above would clear whichever came first in the DOM.
    """
    return (
        f"//div[normalize-space()='{section_label}']"
        "/following-sibling::div[contains(@class,'resource-drop-zone')]"
        "//*[contains(@class,'upload-file-clear-icon')]"
    )


# Sections whose dropzone is replaced by an uploaded-file list once they hold a
# file. Headshots persist at speaker level across webcasts, so a freshly created
# webcast can already carry one from an earlier run.
SECTION_LABELS = {"headshot": "Upload headshot"}


def status_dropdown(state):
    """The Preview/Live status dropdown, currently showing `state` ('Preview'/'Live')."""
    return f"//span[@title='{state}']"


def status_option(state):
    """The Preview/Live option inside the open status dropdown."""
    return f"//div[contains(text(),'{state}')]"


# --------------------------------------------------------------------------
# Webcast Layout panel
# --------------------------------------------------------------------------
LAYOUT_TITLE_INPUT = "//input[@placeholder='Title']"
LAYOUT_DESC_INPUT = "//input[@placeholder='Description']"


def layout_switch(index):
    """Nth toggle switch on the layout page (1-based).

    These are positional because the switches carry no stable id or label; see
    LAYOUT_SWITCHES in webcast_flow.py for what each index means.
    """
    return f"(//button[@role='switch'])[{index}]"


# --------------------------------------------------------------------------
# Global
# --------------------------------------------------------------------------
# SweetAlert popup body. Auto-dismisses in ~3s, and error messages use the same
# container as success ones — so always check the text.
SWAL_CONTAINER_ID = "swal2-html-container"
