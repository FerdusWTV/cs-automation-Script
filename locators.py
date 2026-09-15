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
# Anchored on the tile's label, not its class string: PR #942 reordered these
# classes to 'h-full stream-modal-container', and the old exact-match
# `@class='stream-modal-container h-full'` silently stopped matching.
# `-root` is the outer wrapper and carries no onClick; the handler sits on the
# inner div, so that wrapper has to be excluded or the click does nothing.
NEW_WEBCAST_MODAL_BTN = (
    "//div[contains(@class,'stream-modal-container')"
    " and not(contains(@class,'stream-modal-container-root'))]"
    "[.//p[normalize-space()='Create New Webcast']]"
)

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
# The combobox input itself. antd opens the dropdown on ARROW_DOWN here, which
# is the one way in that a floating toast cannot intercept.
WEBCAST_TYPE_INPUT = "//input[@id='webcastType']"
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
SELECT_ALL_BTN = "//button[normalize-space()='Select All']"

# The dropzone that 'Upload More' brings back also renders a 'Browse' button.
# It is deliberately NOT used: clicking it opens the OS file dialog, which
# Selenium cannot drive. Files go to the <input type=file> beside it instead.
BROWSE_BTN = "//button[normalize-space()='Browse']"

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

# Once SAVED, those sections render a gallery under a different heading, with an
# 'Upload More' button in place of the dropzone. Keyed the same as SECTION_LABELS.
GALLERY_LABELS = {"headshot": "Uploaded headshots"}


def upload_more(gallery_label):
    """The 'Upload More' button in the gallery titled `gallery_label`.

    Scoped to its own section: the slides gallery renders an identical button,
    so the unscoped locator would hit whichever came first in the DOM.
    """
    return (
        f"//div[normalize-space()='{gallery_label}']"
        "/following-sibling::div[contains(@class,'uploaded-slides')]"
        "//button[normalize-space()='Upload More']"
    )


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
# The app's fullscreen loading overlay. antd keeps this element in the DOM at all
# times and toggles its visibility, so check visibility — never mere presence.
FULLSCREEN_SPINNER_CSS = ".ant-spin-fullscreen"

# SweetAlert popup body. Auto-dismisses in ~3s, and error messages use the same
# container as success ones — so always check the text.
SWAL_CONTAINER_ID = "swal2-html-container"


# ==========================================================================
# Embedded sessions
# ==========================================================================
# Embedded mode is a CLIENT-level flag. A client saved with 'Embedded Portal'
# on is opened with ?embbedEnable=true&embbedPortalId=<id>, and from there the
# admin renders the session list directly instead of the portal list.
# --------------------------------------------------------------------------

# --- Organizations / clients navigation -----------------------------------
ORG_SEARCH_INPUT = "//input[contains(@class,'connect-studio-search-input-small')]"


def org_card_open(org_name):
    """The 'open' arrow on the organization card named `org_name`."""
    return (
        f"//div[contains(@class,'org-card')][.//h6[normalize-space()='{org_name}']]"
        "//div[contains(@class,'org-card-arrow')]"
    )


CLIENT_SEARCH_INPUT = "//div[contains(@class,'client-table-section')]//input[@class='search-input']"
ADD_CLIENT_BTN = "//div[contains(@class,'add-client-modal')]//button[contains(@class,'save-button')]"

# --- Add Client modal ------------------------------------------------------
CLIENT_NAME_INPUT = "//div[contains(@class,'ant-modal')]//input[@name='name']"
# AntSoloSelect renders without an id, so the Language select is reached
# through its label rather than through the field itself.
CLIENT_LANGUAGE_SELECTOR = (
    "//div[contains(@class,'ant-modal')]//label[normalize-space()='Language']"
    "/following::div[contains(@class,'ant-select-selector')][1]"
)
# The switch is a plain <input type=checkbox> inside ConnectStudioSwitchButton,
# visually replaced by a .slider span — so the input itself is not clickable.
# Click the slider; read the checkbox's `checked` property for the state.
EMBED_SWITCH_CHECKBOX = (
    "//div[contains(@class,'switch-button-container')]"
    "[.//div[normalize-space()='Embedded Portal']]//input[@type='checkbox']"
)
EMBED_SWITCH_SLIDER = (
    "//div[contains(@class,'switch-button-container')]"
    "[.//div[normalize-space()='Embedded Portal']]//span[contains(@class,'slider')]"
)
CLIENT_SAVE_BTN = "//div[contains(@class,'ant-modal')]//button[@type='submit']"
# The title row carries a back arrow and a close X, both bare react-icons svgs
# with no distinguishing attribute — the close one is simply the last.
CLIENT_MODAL_CLOSE = (
    "(//div[contains(@class,'ant-modal')]//*[name()='svg'][contains(@class,'cursor-pointer')])[last()]"
)


def client_row_view_portals(client_name):
    """The 'View Portals' cell of the client row named `client_name`."""
    return (
        f"//tr[td[normalize-space()='{client_name}']]"
        "//td[contains(@class,'portal-view-button')]"
    )


# --- Session list in embedded mode ----------------------------------------
SESSION_LIST_TITLE = "//div[contains(@class,'webcast-summary-title')]"
# The portal LIST root. Absent in embedded mode because Portal/index.js returns
# <SessionComponent /> before rendering it. Note this is the right thing to
# assert on and PORTAL_SEARCH_INPUT is not: that search box lives in the global
# header, so it is on screen in embedded mode too.
PORTAL_SCREEN_ROOT = "//div[contains(@class,'portal-screen-root')]"
IMPORT_WEBCAST_BTN = "//button[contains(normalize-space(),'Import Webcast')]"
SIDEBAR_CREATE_PORTAL = "//*[normalize-space()='Create Portal']"
SCHEDULE_WEBCAST_BTN = "//div[@class='session-button-group-right']"
STREAM_MODAL_OPTION = "//div[contains(@class,'stream-modal-container-root')]"
CREATE_NEW_WEBCAST_OPTION = "//p[normalize-space()='Create New Webcast']"
LENOS_INTEGRATION_FIELD = "//input[@id='integrationId']"

# The embed icon sits beside Delete in the row's action column. Both are
# identical antd icon buttons, so the only thing telling them apart is the
# embed one's rounded wrapper — the row also gains 'has-embed-action' when the
# pair is rendered.
SUMMARY_EMBED_BTN = (
    ".//div[contains(@class,'webcast-summary-delete')]"
    "//div[contains(@class,'rounded-md')]//button"
)
SUMMARY_HAS_EMBED_ACTION = ".//div[contains(@class,'has-embed-action')]"

# Manage page tabs. In embedded mode the last four are not rendered at all.
MANAGE_TAB = "//button[@role='tab']"


def manage_tab(label):
    return f"//button[@role='tab'][normalize-space()='{label}']"

# --- Embed Session modal ---------------------------------------------------
# Anchored on the body wrapper, not on the heading: the deployed modal is
# titled 'Embed Code' while the source in the repo still says 'Embed Session',
# so the heading is the one part of this modal that has already moved once.
EMBED_MODAL = "//div[contains(@class,'ant-modal')][.//div[contains(@class,'embed-config')]]"
EMBED_MODAL_TITLE = f"{EMBED_MODAL}//div[contains(@class,'ant-modal-title')]//div[contains(@class,'con-title')]"
EMBED_SESSION_NAME = f"{EMBED_MODAL}//strong"
# Read-only <textarea> holding the generated snippet. Its text is the single
# source of truth for every snippet assertion — read `value`, not `.text`,
# because antd's autosize textarea does not reflect the value as node text.
EMBED_SNIPPET_TEXTAREA = f"{EMBED_MODAL}//textarea"

EMBED_ADVANCED_SWITCH = (
    f"{EMBED_MODAL}//label[normalize-space()='Advanced config']"
    "/ancestor::div[1]//button[@role='switch']"
)
EMBED_RESPONSIVE_CHECKBOX = (
    f"{EMBED_MODAL}//label[contains(@class,'ant-checkbox-wrapper')]"
    "[contains(normalize-space(),'Responsive')]//input"
)
EMBED_ASPECT_SELECTOR = (
    f"{EMBED_MODAL}//label[normalize-space()='Aspect ratio']"
    "/following-sibling::div[contains(@class,'ant-select')][1]"
)
EMBED_BORDER_RADIUS_INPUT = (
    f"{EMBED_MODAL}//label[normalize-space()='Border radius (px)']"
    "/following::input[contains(@class,'ant-input-number-input')][1]"
)
EMBED_TITLE_INPUT = f"{EMBED_MODAL}//label[normalize-space()='Accessible title']/following::input[1]"
EMBED_COPY_BTN = f"{EMBED_MODAL}//button[normalize-space()='Copy embed code']"
EMBED_CLOSE_BTN = f"{EMBED_MODAL}//button[normalize-space()='Close']"
EMBED_MODAL_MASK_CSS = ".ant-modal-mask"


def embed_format_option(label):
    """'HTML' / 'React / JSX' in the output-format radio group."""
    return f"{EMBED_MODAL}//label[contains(@class,'ant-radio-button-wrapper')][normalize-space()='{label}']"


def embed_size_input(label):
    """The number input under 'Width' or 'Height'."""
    return (
        f"{EMBED_MODAL}//label[normalize-space()='{label}']"
        "/following::input[contains(@class,'ant-input-number-input')][1]"
    )


def embed_size_unit_selector(label):
    """The px/% unit select beside the 'Width' or 'Height' input."""
    return (
        f"{EMBED_MODAL}//label[normalize-space()='{label}']"
        "/following::div[contains(@class,'ant-select-selector')][1]"
    )


def embed_permission_checkbox(label):
    """A Permissions checkbox by its visible label, e.g. 'Fullscreen'."""
    return (
        f"{EMBED_MODAL}//label[contains(@class,'ant-checkbox-wrapper')]"
        f"[.//text()[contains(.,'{label}')]]//input"
    )


def embed_advanced_selector(label):
    """The antd Select under 'Loading' or 'Referrer policy'."""
    return (
        f"{EMBED_MODAL}//label[normalize-space()='{label}']"
        "/following-sibling::div[contains(@class,'ant-select')][1]"
    )


def select_option(title):
    """An option in the CURRENTLY OPEN antd dropdown, matched on its exact title.

    Scoped to the visible dropdown on purpose: antd keeps every dropdown it has
    ever opened mounted, flagging the closed ones with `ant-select-dropdown-hidden`.
    An unscoped match therefore picks the option out of whichever dropdown was
    opened first — so setting the Height unit would silently re-set the Width one.
    """
    return (
        "//div[contains(@class,'ant-select-dropdown')"
        " and not(contains(@class,'ant-select-dropdown-hidden'))]"
        f"//div[contains(@class,'ant-select-item-option')][@title='{title}']"
    )
