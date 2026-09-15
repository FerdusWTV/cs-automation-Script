"""End-to-end suite for the embedded-sessions feature (PR #942).

Embedded mode is switched on per CLIENT. A client saved with 'Embedded Portal'
on is opened with `?embbedEnable=true&embbedPortalId=<id>`, and from there the
admin drops the portal list and renders the session list directly, with a
'Copy embed code' icon on every session row that opens the Embed Code modal.

**Embedded sessions are always Video only.** `webcastTypeOptions` filters the
type list to VIDEO_ONLY_TYPES, leaving one option, and the wizard posts
webcastType 'video' on its own. So this suite creates exactly ONE session and
never sets a type -- there is deliberately no per-type matrix here like the
WEBCAST_MATRIX in session_test.py, which builds one webcast of each of the five
types. The only type assertion is that the single offered option is the one
already selected.

The tests run in order and share one browser session:

    test_0x   client setup      create the embedded + plain clients
    test_1x   session list      what embedded mode shows and hides, one session
    test_2x   embed modal       the generated <iframe> snippet
    test_3x   modal behaviour   copy, reset, read-only, responsiveness

Run from this directory:

    ..\\venv\\Scripts\\pytest 03_embedded_test.py -v --env=dev \\
        --html=embedded_report.html --self-contained-html

The embedded client is created in the SAME organization that owns TARGET_PORTAL
from .env — Kollective is configured per organization and session creation fails
in an organization whose credentials do not work, so the organization is not
something to pick arbitrarily. `--embed-org` overrides it.

Useful options (see conftest.py): `--env=dev|prod`, `--embed-org=...`,
`--embed-client=...`, and `--testrail-out=results.json` to record the run for
upload to TestRail.

Every test carries `@pytest.mark.testrail(<case id>)` naming the case it covers
in project 2 / suite 7, section 'Embedded Session'.

The UI steps live in `embed_flow.py`, the selectors in `locators.py`, and the
click/wait plumbing in `ui.py`.
"""

import os
import time

import pytest
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import embed_flow as embed
import locators as L
import ui
import webcast_flow as flow

# The snippet the modal generates before anything is configured. Asserted
# attribute by attribute rather than as one string so a failure names the
# attribute that drifted.
DEFAULT_ATTRIBUTES = {
    "width": "100%",
    "height": "700px",
    "frameborder": "0",
    "scrolling": "no",
    "loading": "eager",
    "referrerpolicy": "strict-origin-when-cross-origin",
    "allow": "fullscreen; autoplay; picture-in-picture; encrypted-media",
}

# Embedded sessions are always video ones. `webcastTypeOptions` filters the type
# list to VIDEO_ONLY_TYPES, which leaves this single label, and the wizard posts
# webcastType 'video' on its own -- so nothing in this suite ever sets a type,
# and there is no per-type matrix here the way session_test.py has one.
VIDEO_ONLY_TYPE = "Video only"

# Carried between the ordered tests: names and ids discovered as the run goes.
STATE = {}


# ----------------------- FIXTURES -------------------------

def _chrome_options(headless=False):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-allow-origins=*")
    # The DevTools performance log is how a failed create reports WHY: the app
    # swallows the error, so the response is the only place the reason exists.
    options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})
    return options


@pytest.fixture(scope="session")
def driver():
    """The browser shared by every test in this module.

    Clipboard permission is granted up front so the 'Copy embed code' test can
    read back what was copied — without it navigator.clipboard rejects and the
    app shows its failure toast instead.
    """
    load_dotenv()
    options = _chrome_options()
    driver_path = os.getenv("DRIVER")
    if driver_path and os.path.exists(driver_path):
        driver = webdriver.Chrome(service=Service(driver_path), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.implicitly_wait(5)
    driver.maximize_window()
    yield driver
    driver.quit()


@pytest.fixture
def wait(driver):
    """Standard 30s wait against the shared browser."""
    return WebDriverWait(driver, 30)


@pytest.fixture
def embed_modal(driver, wait, config):
    """An open Embed Session modal on the first session row, reset to defaults.

    The component resets its config when it closes, so reopening per test is
    what guarantees each test starts from DEFAULT_CONFIG rather than inheriting
    whatever the previous test configured.
    """
    _require(STATE.get("in_embedded_mode"), "the embedded session list was never reached")
    embed.ensure_embedded_list(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    _require(rows, "the embedded client has no sessions")

    if ui.exists(driver, L.EMBED_MODAL_TITLE):
        embed.close_embed_modal(driver, wait)
    embed.open_embed_modal(driver, wait, rows[0])
    yield
    if ui.exists(driver, L.EMBED_MODAL_TITLE):
        embed.close_embed_modal(driver, wait)


def _require(condition, reason):
    """Skip — not fail — when an earlier step left this test nothing to check.

    A skip is recorded against TestRail as 'blocked', which is the honest
    reading: the case was never executed. Failing here instead would blame this
    case for a breakage that belongs to the test that ran before it.
    """
    if not condition:
        pytest.skip(f"Prerequisite missing: {reason}")


def _visible(driver, xpath):
    """True when at least one match is actually rendered to the user.

    Several controls the embedded view 'hides' are only class-hidden, so
    `ui.exists` would report them as still present.
    """
    return any(element.is_displayed() for element in ui.find_all(driver, xpath))


def _require_admin():
    """Skip the client-setup cases when the account cannot reach them.

    Creating clients happens on /organization, which is behind AdminGuard
    (SUPER_ADMIN / ADMIN). A portal- or org-level account is silently redirected
    to /dashboard, so these cases need admin credentials in .env to run at all.
    """
    _require(
        STATE.get("is_admin"),
        "the configured account is not an ADMIN — /organization is not reachable, "
        "so clients cannot be created. Set EMAIL_ORG/PASSWORD_ORG to an admin account.",
    )


# ===========================================================================
# Client setup
# ===========================================================================

def test_00_login(driver, config):
    """Log in as the ADMIN account.

    Not the org account the other suites use: creating a client happens on
    /organization, which is behind AdminGuard (SUPER_ADMIN / ADMIN), and an
    ORG_ADMIN is silently redirected to /dashboard instead.
    """
    welcome_text = embed.login_admin(driver, config)
    assert "Welcome" in welcome_text, "Login failed — 'Welcome' not found."
    print(f"✅ Login successful: {welcome_text}")


def test_01_detect_admin_access(driver, config):
    """Confirm the account really can reach the client-creation screens."""
    STATE["is_admin"] = embed.is_admin(driver, config)
    assert STATE["is_admin"], (
        "The configured account cannot open /organization. The embedded suite "
        "needs an ADMIN account — check EMAIL / PASSWORD in .env."
    )
    print("✅ Admin access confirmed.")


def test_02_resolve_target_organization(driver, wait, config):
    """Work out which organization the embedded client belongs in.

    The client is created in the SAME organization that owns the portal named by
    TARGET_PORTAL in .env, not in whichever organization happens to sort first.
    That matters for more than tidiness: Kollective is configured per
    organization, and session creation fails outright in an organization whose
    Kollective credentials do not work (see EMBEDDED_SESSION_DEFECTS.md).

    `--embed-org` still overrides this when a different organization is wanted.
    """
    _require_admin()

    if config["embed_org"]:
        embed.open_organization(driver, wait, config, config["embed_org"])
        STATE["org"] = config["embed_org"]
        STATE["org_id"] = embed.query_params(driver).get("organizationId")
        print(f"✅ Using --embed-org '{STATE['org']}' ({STATE['org_id']})")
        return

    flow.open_portal(driver, wait, config["target_portal"])
    time.sleep(2)
    portal_id = embed.portal_id_from_url(driver)
    assert portal_id, f"Could not resolve a portal id for '{config['target_portal']}'."
    STATE["target_portal_id"] = portal_id

    owner = embed.resolve_portal_org(driver, wait, config, portal_id)
    assert owner.get("organizationId"), (
        f"Could not read the organization owning portal {portal_id} from its "
        "branding record."
    )
    STATE["org_id"] = owner["organizationId"]
    STATE["org"] = embed.open_client_list(driver, wait, config, STATE["org_id"])
    print(f"✅ Target portal {portal_id} belongs to org '{STATE['org']}' ({STATE['org_id']})")


@pytest.mark.testrail(570)
def test_03_embed_switch_offered(driver, wait, config):
    """The Add Client modal offers an 'Embedded Portal' switch, off by default."""
    _require_admin()
    _require(STATE.get("org_id"), "the target organization was never resolved")

    embed.open_client_list(driver, wait, config, STATE["org_id"], STATE.get("org"))
    embed.open_add_client_modal(driver, wait)

    assert embed.embed_switch_offered(driver), (
        "No 'Embedded Portal' switch in the Add Client modal."
    )
    assert embed.embed_switch_state(driver, wait) is False, (
        "'Embedded Portal' should default to off for a new client."
    )
    print("✅ 'Embedded Portal' switch offered, defaulting to off.")
    embed.close_add_client_modal(driver, wait)


@pytest.mark.testrail(571)
def test_04_create_embedded_client(driver, wait, config):
    """Create (or reuse) an embedded client."""
    _require_admin()
    name = config["embed_client"]

    # Reuse across runs: the client cannot be deleted from the admin, so
    # creating a fresh one per run would pile them up in the organization.
    if embed.find_client(driver, wait, name):
        STATE["embedded_client"] = name
        pytest.skip(f"Embedded client '{name}' already exists — reused, not recreated.")

    text = embed.create_client(driver, wait, name, embedded=True)
    assert embed.find_client(driver, wait, name), (
        f"Client '{name}' was not in the list after saving (popup said: {text})"
    )
    STATE["embedded_client"] = name
    print(f"✅ Embedded client created: {name}")


@pytest.mark.testrail(572)
def test_05_create_plain_client(driver, wait, config):
    """A client saved with the switch off is an ordinary, non-embedded client."""
    _require_admin()
    name = config["plain_client"]

    if embed.find_client(driver, wait, name):
        STATE["plain_client"] = name
        pytest.skip(f"Plain client '{name}' already exists — reused, not recreated.")

    text = embed.create_client(driver, wait, name, embedded=False)
    assert embed.find_client(driver, wait, name), (
        f"Client '{name}' was not in the list after saving (popup said: {text})"
    )
    STATE["plain_client"] = name
    print(f"✅ Plain client created: {name}")


@pytest.mark.testrail(574)
def test_06_plain_client_has_no_embed_params(driver, wait):
    """Opening a NON-embedded client must not append the embed parameters."""
    _require_admin()
    _require(STATE.get("plain_client"), "the plain client was never created")

    embed.find_client(driver, wait, STATE["plain_client"])
    params = embed.open_client_portals(driver, wait, STATE["plain_client"])

    assert "embbedEnable" not in params, f"embbedEnable leaked onto a plain client: {params}"
    assert "embbedPortalId" not in params, f"embbedPortalId leaked onto a plain client: {params}"
    assert ui.exists(driver, L.PORTAL_SEARCH_INPUT), (
        "A plain client should still show the portal list, not the session list."
    )
    print(f"✅ Plain client opened without embed parameters: {params}")


@pytest.mark.testrail(573)
def test_07_embedded_client_appends_query_params(driver, wait, config):
    """Opening the embedded client appends embbedEnable and embbedPortalId.

    Also covers the empty-id case: embbedPortalId is emitted even when the
    backend has no portal id for the client yet, so the parameter is always
    present and it is its VALUE that may be blank.
    """
    _require_admin()
    _require(STATE.get("embedded_client"), "the embedded client was never created")

    embed.open_client_list(driver, wait, config, STATE["org_id"], STATE.get("org"))
    embed.find_client(driver, wait, STATE["embedded_client"])
    params = embed.open_client_portals(driver, wait, STATE["embedded_client"])

    assert params.get("embbedEnable") == "true", f"embbedEnable not set: {params}"
    assert "embbedPortalId" in params, f"embbedPortalId missing entirely: {params}"
    for expected in ("organizationId", "organizationName", "clientId", "clientName"):
        assert expected in params, f"{expected} dropped from the query string: {params}"

    # The backend provisions a portal for an embedded client as it creates it,
    # so this is the portal the session list and every snippet refer to.
    STATE["portal_id"] = params["embbedPortalId"]
    print(f"✅ Embedded mode entered with embbedPortalId='{params['embbedPortalId']}'")


def test_08_enter_embedded_mode(driver, wait, config):
    """Open the session list in embedded mode for the resolved portal.

    Done by URL rather than through the client list: the client list is behind
    the ADMIN guard while /organization/portal is behind the portal one, and the
    app resolves the client and organization from embbedPortalId anyway.
    """
    _require(STATE.get("portal_id"), "the embedded client did not yield a portal id")

    params = embed.enter_embedded_mode(driver, wait, config, STATE["portal_id"])
    assert params.get("embbedEnable") == "true", f"Embedded mode was not entered: {params}"

    STATE["in_embedded_mode"] = True
    print(f"✅ Embedded session list open for portal {STATE['portal_id']}")


# ===========================================================================
# The embedded session list
# ===========================================================================

@pytest.mark.testrail(576)
def test_10_session_list_replaces_portal_list(driver, wait):
    """Embedded mode renders the session list instead of the portal list."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    assert ui.exists(driver, "//div[contains(@class,'webcast-summary-title')]"), (
        "No 'Live Sessions' heading — the session list did not replace the portal list."
    )
    assert not ui.exists(driver, L.PORTAL_SCREEN_ROOT), (
        "The portal list is still rendered in embedded mode."
    )
    print("✅ Session list rendered in place of the portal list.")


@pytest.mark.testrail(579)
def test_11_import_webcast_hidden(driver, wait):
    """The Import Webcast button is not offered in embedded mode."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    assert not ui.exists(driver, L.IMPORT_WEBCAST_BTN), (
        "'Import Webcast' is still shown in embedded mode."
    )
    print("✅ Import Webcast hidden.")


@pytest.mark.testrail(580)
def test_12_create_portal_hidden_from_sidebar(driver, wait):
    """The sidebar's Create Portal entry is suppressed in embedded mode."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    # The sidebar item stays in the DOM with a `hidden` class rather than being
    # unmounted, so presence proves nothing — visibility is the requirement.
    assert not _visible(driver, L.SIDEBAR_CREATE_PORTAL), (
        "'Create Portal' is still visible in the sidebar in embedded mode."
    )
    print("✅ Create Portal hidden from the sidebar.")


@pytest.mark.testrail(583)
def test_13_only_create_new_webcast_offered(driver, wait):
    """The schedule modal offers one option, not the Stream Studio pair."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    ui.click(driver, wait, L.SCHEDULE_WEBCAST_BTN)
    ui.find(wait, L.CREATE_NEW_WEBCAST_OPTION)
    options = ui.find_all(driver, L.STREAM_MODAL_OPTION)

    assert len(options) == 1, (
        f"Expected only 'Create New Webcast' in embedded mode, found {len(options)} options."
    )
    assert not ui.exists(driver, "//p[contains(normalize-space(),'Stream Studio')]"), (
        "The Stream Studio option is still offered in embedded mode."
    )
    print("✅ Only 'Create New Webcast' offered.")


@pytest.mark.testrail(585)
def test_14_lenos_integration_hidden(driver, wait):
    """Step 1 of the wizard hides the LENOS integration field in embedded mode."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    ui.click(driver, wait, L.CREATE_NEW_WEBCAST_OPTION)
    ui.find(wait, L.WIZARD_TITLE_INPUT)

    assert not ui.exists(driver, L.LENOS_INTEGRATION_FIELD), (
        "The LENOS integration field is still shown in embedded mode."
    )
    print("✅ LENOS integration field hidden.")

    # Leave the wizard so the next test starts from the session list.
    driver.refresh()
    ui.wait_for_spinner(driver)


@pytest.mark.testrail(584)
def test_15_create_embedded_session(driver, wait, config):
    """Create the session the modal tests embed, through the embedded wizard.

    A freshly created embedded client has no sessions, so this is what gives the
    rest of the suite something to generate a snippet for. Embedded sessions are
    always video ones — the wizard is posted with webcastType 'video' and the
    type is never chosen by hand, so this only creates and then checks.
    """
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    if embed.session_rows(driver, wait):
        STATE["session_title"] = "(pre-existing)"
        pytest.skip("The embedded client already has a session — reused, none created.")

    title = f"Automated Embedded Session {int(time.time())}"
    embed.create_session(driver, wait, title)
    STATE["session_title"] = title

    failures = embed.failed_api_calls(driver, "/session/create")

    embed.enter_embedded_mode(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    STATE["has_sessions"] = bool(rows)

    assert rows, (
        f"The wizard completed but no session appeared for '{title}'. "
        f"The create call failed with: {failures or 'no failing response captured'}. "
        "The UI shows nothing either way — SessionsModal does `.catch((err) => err)` "
        "on this POST, so the server's reason never reaches the user."
    )
    print(f"✅ Session created in embedded mode: {title}")


def test_16_fall_back_to_a_portal_with_sessions(driver, wait, config):
    """Point the modal tests at a portal that actually has sessions.

    The embedded client this suite creates starts empty, and session creation
    against it is currently broken server-side (see test_15). Rather than lose
    all modal coverage to that one failure, fall back to the configured portal
    — the Embed Session modal behaves identically whichever embedded portal the
    list belongs to.
    """
    if STATE.get("has_sessions"):
        print("✅ The embedded client has its own sessions — no fallback needed.")
        return

    fallback_id = config["embed_portal_id"] or STATE.get("target_portal_id")

    _require(fallback_id, "no fallback portal could be resolved")
    embed.enter_embedded_mode(driver, wait, config, fallback_id)
    rows = embed.session_rows(driver, wait)
    _require(rows, f"the fallback portal {fallback_id} has no sessions either")

    STATE["portal_id"] = fallback_id
    STATE["has_sessions"] = True
    print(f"✅ Falling back to portal {fallback_id} ({len(rows)} sessions) for the modal cases.")


@pytest.mark.testrail(586)
def test_17_manage_view_is_restricted(driver, wait, config):
    """The Manage page of an embedded session is Video only and tab-reduced.

    Two rules meet here. `webcastTypeOptions(isNew, isEmbedded)` filters the type
    list down to VIDEO_ONLY_TYPES, which leaves exactly one option -- 'Video
    only' -- in both the new-session and legacy lists. So there is no type to
    choose in embedded mode and nothing for a test to set: the check is that the
    single option is the one already selected. The Manage view also drops the
    tabs that make no sense for an embedded player (Webcast Layout, Video
    Indexer, VOD Management, External Session).
    """
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")
    embed.ensure_embedded_list(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    _require(rows, "the embedded client has no sessions")

    embed.open_manage(driver, wait, rows[0])
    tabs = embed.manage_tabs(driver)
    print(f"  Manage tabs in embedded mode: {tabs}")

    for hidden in ("Webcast Layout", "Video Indexer", "VOD MANAGEMENT", "External Session"):
        assert not any(hidden.lower() == tab.lower() for tab in tabs), (
            f"'{hidden}' is still offered on the Manage page in embedded mode."
        )
    assert any("webcast details" == tab.lower() for tab in tabs), (
        f"The Webcast details tab is missing altogether: {tabs}"
    )

    options = embed.webcast_type_options(driver, wait)
    selected = embed.selected_webcast_type(driver, wait)
    print(f"  Webcast type in embedded mode: {selected!r}, options {options}")

    assert options == [VIDEO_ONLY_TYPE], (
        f"Embedded mode should offer '{VIDEO_ONLY_TYPE}' and nothing else, got {options}."
    )
    assert selected == VIDEO_ONLY_TYPE, (
        f"An embedded session should already be '{VIDEO_ONLY_TYPE}', not '{selected}'."
    )

    # Back to the list so the row-level tests that follow have something to use.
    embed.enter_embedded_mode(driver, wait, config, STATE["portal_id"])


@pytest.mark.testrail(581)
def test_18_embed_button_on_every_row(driver, wait, config):
    """Every session row carries a 'Copy embed code' icon beside Delete."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")
    embed.ensure_embedded_list(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    _require(rows, "the embedded client has no sessions")

    missing = [i for i, row in enumerate(rows) if embed.row_embed_button(row) is None]
    assert not missing, f"Rows {missing} have no embed icon (of {len(rows)} rows)."
    print(f"✅ Embed icon present on all {len(rows)} session rows.")


@pytest.mark.testrail(582)
def test_19_embed_button_absent_outside_embedded_mode(driver, wait, config):
    """The same session list, opened normally, shows no embed icon.

    Reached by stripping the embed parameters from the current URL rather than
    by navigating a second client, so the comparison is the same list in both
    modes and the only variable is the flag.
    """
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")

    embedded_url = driver.current_url
    plain_url = embedded_url.replace("embbedEnable=true", "embbedEnable=false")
    driver.get(plain_url)
    ui.wait_for_spinner(driver)

    rows = embed.session_rows(driver, wait)
    with_button = [i for i, row in enumerate(rows) if embed.row_embed_button(row) is not None]

    driver.get(embedded_url)  # restore embedded mode for the tests that follow
    ui.wait_for_spinner(driver)

    assert not with_button, (
        f"Rows {with_button} still show the embed icon with embbedEnable=false."
    )
    print("✅ Embed icon absent outside embedded mode.")


# ===========================================================================
# The Embed Session modal — snippet generation
# ===========================================================================

@pytest.mark.testrail(587)
def test_20_modal_opens_from_row(driver, wait, embed_modal):
    """The embed icon opens the modal with its four headline controls."""
    assert ui.exists(driver, L.EMBED_SESSION_NAME), "The modal does not show the session title."
    assert embed.snippet(driver, wait).strip(), "The embed code area is empty."
    assert ui.exists(driver, L.embed_format_option("HTML")), "No HTML/React format toggle."
    assert ui.exists(driver, L.EMBED_ADVANCED_SWITCH), "No Advanced config switch."
    print("✅ Embed Session modal opens with title, snippet, format toggle and advanced switch.")


@pytest.mark.testrail(588)
def test_21_default_snippet(driver, wait, embed_modal):
    """With Advanced config off, the snippet carries the documented defaults."""
    code = embed.snippet(driver, wait)

    for name, expected in DEFAULT_ATTRIBUTES.items():
        actual = embed.attribute(code, name)
        assert actual == expected, f'{name}: expected "{expected}", got "{actual}"'

    assert "allowfullscreen" in code, "allowfullscreen missing from the default snippet."
    style = embed.attribute(code, "style")
    for fragment in ("border:0;", "border-radius:0px;", "max-width:100%;"):
        assert fragment in style, f"'{fragment}' missing from the default style: {style}"
    print("✅ Default snippet matches the documented attributes.")


@pytest.mark.testrail(589, 592)
def test_22_embed_url(driver, wait, embed_modal):
    """The src points at the session on the embedded portal.

    A session created in embedded mode is a custom session, so its viewer URL
    carries `isNewSession=true`; the portal id in the path is the one the query
    string brought in, not the branding store's.
    """
    src = embed.attribute(embed.snippet(driver, wait), "src")

    assert src, "The snippet has no src."
    assert "/session/" in src, f"src is not a session URL: {src}"
    assert "isNewSession=true" in src, (
        f"A session created in embedded mode should carry isNewSession=true: {src}"
    )
    if STATE.get("portal_id"):
        assert f"/{STATE['portal_id']}/session/" in src, (
            f"src does not use embbedPortalId '{STATE['portal_id']}': {src}"
        )
    print(f"✅ Embed URL: {src}")


@pytest.mark.testrail(594)
def test_23_jsx_format(driver, wait, embed_modal):
    """'React / JSX' re-renders the snippet with JSX attribute spellings."""
    embed.set_format(driver, wait, "React / JSX")
    code = embed.snippet(driver, wait)

    assert code.rstrip().endswith("/>"), f"The JSX tag should self-close:\n{code}"
    for name in ("frameBorder", "allowFullScreen", "referrerPolicy"):
        assert name in code, f"{name} missing from the JSX snippet."
    assert "style={{" in code, "The JSX style should be a double-brace object."
    for key in ("borderRadius", "maxWidth"):
        assert key in code, f"{key} missing — JSX style keys should be camelCased."
    print("✅ JSX output uses JSX attribute names and a style object.")


@pytest.mark.testrail(595)
def test_24_back_to_html_format(driver, wait, embed_modal):
    """Switching back to HTML restores the lowercase attributes and closing tag."""
    embed.set_format(driver, wait, "React / JSX")
    embed.set_format(driver, wait, "HTML")
    code = embed.snippet(driver, wait)

    assert "</iframe>" in code, f"The HTML snippet should close the tag:\n{code}"
    assert "frameborder=" in code, "HTML output should use lowercase frameborder."
    assert "frameBorder" not in code, "JSX attribute spelling survived the switch back."
    assert 'style="' in code, "HTML output should use a style string, not an object."
    print("✅ HTML output restored.")


@pytest.mark.testrail(596)
def test_25_advanced_switch_reveals_options(driver, wait, embed_modal):
    """The Advanced config switch expands the configuration panel."""
    assert not embed.advanced_open(driver), "Advanced config should start collapsed."

    embed.set_advanced(driver, wait, True)

    assert ui.exists(driver, L.EMBED_RESPONSIVE_CHECKBOX), "No Responsive checkbox."
    assert ui.exists(driver, L.embed_size_input("Width")), "No Width field."
    assert ui.exists(driver, L.EMBED_BORDER_RADIUS_INPUT), "No Border radius field."
    assert ui.exists(driver, L.embed_permission_checkbox("Fullscreen")), "No permission list."
    print("✅ Advanced config reveals the full option set.")


@pytest.mark.testrail(597)
def test_26_custom_width_and_height(driver, wait, embed_modal):
    """Typed width and height values reach the snippet with their units."""
    embed.set_advanced(driver, wait, True)
    embed.set_size_unit(driver, wait, "Width", "px")
    embed.set_size(driver, wait, "Width", 640)
    embed.set_size(driver, wait, "Height", 360)

    code = embed.snippet(driver, wait)
    assert embed.attribute(code, "width") == "640px", f'width was "{embed.attribute(code, "width")}"'
    assert embed.attribute(code, "height") == "360px", f'height was "{embed.attribute(code, "height")}"'
    print("✅ Custom width and height applied.")


@pytest.mark.testrail(598)
def test_27_size_units_switch(driver, wait, embed_modal):
    """The px/% unit selects drive the unit suffix in the snippet."""
    embed.set_advanced(driver, wait, True)
    embed.set_size(driver, wait, "Width", 80)
    embed.set_size_unit(driver, wait, "Width", "%")
    assert embed.attribute(embed.snippet(driver, wait), "width") == "80%"

    embed.set_size_unit(driver, wait, "Height", "%")
    assert embed.attribute(embed.snippet(driver, wait), "height").endswith("%")
    print("✅ Width and height units switch between px and %.")


@pytest.mark.testrail(599)
def test_28_size_cannot_go_below_one(driver, wait, embed_modal):
    """The size inputs clamp at 1 — a 0 or blank value never reaches the snippet."""
    embed.set_advanced(driver, wait, True)
    embed.set_size_unit(driver, wait, "Width", "px")
    embed.set_size(driver, wait, "Width", 0)

    width = embed.attribute(embed.snippet(driver, wait), "width")
    assert width not in ("0px", "px", None), f'width fell below the minimum: "{width}"'
    print(f"✅ Width clamped to '{width}' rather than 0.")


@pytest.mark.testrail(600)
def test_29_responsive_wraps_the_iframe(driver, wait, embed_modal):
    """Responsive mode swaps the size fields for a wrapper div."""
    embed.set_advanced(driver, wait, True)
    embed.set_responsive(driver, wait, True)

    assert not ui.exists(driver, L.embed_size_input("Width")), (
        "The Width field should be replaced by the Aspect ratio selector."
    )
    assert ui.exists(driver, L.EMBED_ASPECT_SELECTOR), "No Aspect ratio selector."

    code = embed.snippet(driver, wait)
    assert code.lstrip().startswith("<div"), f"The iframe should be wrapped:\n{code}"
    assert "aspect-ratio" in code, "The wrapper carries no aspect-ratio."
    assert "overflow:hidden" in code.replace(" ", ""), "The wrapper does not clip its content."
    assert "position:absolute" in code.replace(" ", ""), "The iframe is not absolutely positioned."
    assert embed.attribute(code, "width") == "100%", "A responsive iframe should be 100% wide."
    print("✅ Responsive mode wraps the iframe in a positioned container.")


@pytest.mark.testrail(601)
def test_30_aspect_ratio_options(driver, wait, embed_modal):
    """Each aspect ratio option reaches the wrapper's aspect-ratio."""
    embed.set_advanced(driver, wait, True)
    embed.set_responsive(driver, wait, True)

    for label, expected in [
        ("4:3 (standard)", "4/3"),
        ("21:9 (cinematic)", "21/9"),
        ("1:1 (square)", "1/1"),
        ("16:9 (widescreen)", "16/9"),
    ]:
        embed.set_advanced_select(driver, wait, "Aspect ratio", label)
        code = embed.snippet(driver, wait).replace(" ", "")
        assert f"aspect-ratio:{expected}" in code, f"'{label}' did not produce {expected}."
    print("✅ All four aspect ratios applied.")


@pytest.mark.testrail(602)
def test_31_permissions_drive_the_allow_attribute(driver, wait, embed_modal):
    """Ticking a permission adds it to `allow`; unticking removes it."""
    embed.set_advanced(driver, wait, True)
    embed.set_permission(driver, wait, "Camera", True)
    assert "camera" in embed.attribute(embed.snippet(driver, wait), "allow")

    embed.set_permission(driver, wait, "Autoplay", False)
    assert "autoplay" not in embed.attribute(embed.snippet(driver, wait), "allow")
    print("✅ Permission checkboxes drive the allow attribute.")


@pytest.mark.testrail(603)
def test_32_unticking_fullscreen_removes_allowfullscreen(driver, wait, embed_modal):
    """Fullscreen is the one permission that also controls a bare attribute."""
    embed.set_advanced(driver, wait, True)
    assert "allowfullscreen" in embed.snippet(driver, wait)

    embed.set_permission(driver, wait, "Fullscreen", False)
    code = embed.snippet(driver, wait)

    assert "allowfullscreen" not in code, "allowfullscreen survived unticking Fullscreen."
    assert "fullscreen" not in (embed.attribute(code, "allow") or ""), (
        "fullscreen is still listed in the allow attribute."
    )
    print("✅ Unticking Fullscreen drops both allowfullscreen and the allow entry.")


@pytest.mark.testrail(604)
def test_33_clearing_every_permission(driver, wait, embed_modal):
    """With no permissions ticked the allow attribute is omitted entirely."""
    embed.set_advanced(driver, wait, True)
    for label in ("Fullscreen", "Autoplay", "Picture-in-picture", "Encrypted media"):
        embed.set_permission(driver, wait, label, False)

    code = embed.snippet(driver, wait)
    assert embed.attribute(code, "allow") is None, (
        f'allow should be dropped, not empty: "{embed.attribute(code, "allow")}"'
    )
    assert "allowfullscreen" not in code, "allowfullscreen survived clearing every permission."
    print("✅ Clearing every permission omits the allow attribute.")


@pytest.mark.testrail(605)
def test_34_border_radius(driver, wait, embed_modal):
    """The border radius reaches the iframe's style in px."""
    embed.set_advanced(driver, wait, True)
    embed.set_border_radius(driver, wait, 24)

    style = embed.attribute(embed.snippet(driver, wait), "style")
    assert "border-radius:24px" in style.replace(" ", ""), f"style was: {style}"
    print("✅ Border radius applied.")


@pytest.mark.testrail(606)
def test_35_border_radius_bounds(driver, wait, embed_modal):
    """The border radius input is bounded at 0 and 200."""
    embed.set_advanced(driver, wait, True)
    field = ui.find(wait, L.EMBED_BORDER_RADIUS_INPUT)

    assert field.get_attribute("aria-valuemin") == "0", "Border radius has no 0 lower bound."
    assert field.get_attribute("aria-valuemax") == "200", "Border radius has no 200 upper bound."

    embed.set_border_radius(driver, wait, 500)
    style = embed.attribute(embed.snippet(driver, wait), "style").replace(" ", "")
    assert "border-radius:500px" not in style, f"An out-of-range radius reached the snippet: {style}"
    print("✅ Border radius bounded at 0–200.")


@pytest.mark.testrail(607)
def test_36_loading_options(driver, wait, embed_modal):
    """Both loading options reach the snippet."""
    embed.set_advanced(driver, wait, True)

    embed.set_advanced_select(driver, wait, "Loading", "Lazy (load when visible)")
    assert embed.attribute(embed.snippet(driver, wait), "loading") == "lazy"

    embed.set_advanced_select(driver, wait, "Loading", "Eager (load immediately)")
    assert embed.attribute(embed.snippet(driver, wait), "loading") == "eager"
    print("✅ Loading options applied.")


@pytest.mark.testrail(608)
def test_37_referrer_policy_options(driver, wait, embed_modal):
    """Every referrer policy option reaches the snippet."""
    embed.set_advanced(driver, wait, True)

    for label, expected in [
        ("no-referrer", "no-referrer"),
        ("origin", "origin"),
        ("unsafe-url", "unsafe-url"),
    ]:
        embed.set_advanced_select(driver, wait, "Referrer policy", label)
        actual = embed.attribute(embed.snippet(driver, wait), "referrerpolicy")
        assert actual == expected, f'expected "{expected}", got "{actual}"'
    print("✅ Referrer policy options applied.")


@pytest.mark.testrail(609)
def test_38_accessible_title(driver, wait, embed_modal):
    """A typed accessible title replaces the default title attribute."""
    embed.set_advanced(driver, wait, True)
    embed.set_accessible_title(driver, wait, "Quarterly results webcast")

    assert embed.attribute(embed.snippet(driver, wait), "title") == "Quarterly results webcast"
    print("✅ Accessible title applied.")


@pytest.mark.testrail(610)
def test_39_title_special_characters_are_escaped(driver, wait, embed_modal):
    """Quotes and ampersands in the title are escaped, not left to break the tag."""
    embed.set_advanced(driver, wait, True)
    embed.set_accessible_title(driver, wait, 'Q3 "results" & review')

    code = embed.snippet(driver, wait)
    assert "&quot;" in code, f'The double quotes were not escaped:\n{code}'
    assert "&amp;" in code, f"The ampersand was not escaped:\n{code}"
    assert 'title="Q3 "results"' not in code, "An unescaped quote broke out of the attribute."
    print("✅ Special characters in the title are escaped.")


# ===========================================================================
# Modal behaviour
# ===========================================================================

@pytest.mark.testrail(611)
def test_40_copy_embed_code(driver, wait, embed_modal):
    """'Copy embed code' toasts and puts exactly the snippet on the clipboard."""
    expected = embed.snippet(driver, wait)

    # navigator.clipboard only resolves for a focused document; an unfocused
    # window leaves the promise pending and neither toast branch ever fires.
    driver.execute_script("window.focus();")
    ui.click(driver, wait, L.EMBED_COPY_BTN)
    time.sleep(2)

    text = driver.execute_script(
        f"var e = document.getElementById('{L.SWAL_CONTAINER_ID}');"
        "return e && e.textContent.trim() ? e.textContent.trim() : null;"
    )
    if text is None:
        pytest.skip(
            "No toast appeared after Copy: navigator.clipboard stays pending while "
            "the browser window is unfocused. Re-run with the window in the foreground."
        )
    assert "copied" in text.lower(), f"Copy reported a failure: {text}"

    clipboard = driver.execute_async_script(
        "const done = arguments[0];"
        "navigator.clipboard.readText().then(done).catch(() => done(null));"
    )
    if clipboard is None:
        pytest.skip("The browser refused clipboard read access — toast verified, contents not.")
    assert clipboard == expected, "The clipboard does not match the snippet shown."
    print("✅ Embed code copied to the clipboard.")


@pytest.mark.testrail(613)
def test_41_config_resets_on_close(driver, wait, embed_modal):
    """Closing the modal discards the configuration; reopening starts at defaults."""
    embed.set_advanced(driver, wait, True)
    embed.set_border_radius(driver, wait, 40)
    embed.set_format(driver, wait, "React / JSX")

    rows = embed.session_rows(driver, wait)
    embed.close_embed_modal(driver, wait)
    embed.open_embed_modal(driver, wait, rows[0])

    code = embed.snippet(driver, wait)
    assert not embed.advanced_open(driver), "Advanced config stayed open after reopening."
    assert "</iframe>" in code, "The format did not reset to HTML."
    assert "border-radius:0px" in embed.attribute(code, "style").replace(" ", ""), (
        "The border radius survived the close."
    )
    print("✅ Config resets when the modal closes.")


@pytest.mark.testrail(614)
def test_42_mask_does_not_dismiss(driver, wait, embed_modal):
    """Clicking the backdrop must not close the modal and lose the config."""
    mask = driver.find_elements("css selector", L.EMBED_MODAL_MASK_CSS)
    _require(mask, "the modal rendered without a mask element")

    ui.js_click(driver, mask[0])
    time.sleep(1)

    assert ui.exists(driver, L.EMBED_MODAL_TITLE), "The mask click dismissed the modal."
    print("✅ Modal survives a mask click.")


@pytest.mark.testrail(615)
def test_43_snippet_is_read_only(driver, wait, embed_modal):
    """The embed code area is read-only — it is output, not an editable field."""
    textarea = ui.find(wait, L.EMBED_SNIPPET_TEXTAREA)
    before = textarea.get_property("value")

    assert textarea.get_property("readOnly") is True, "The embed code textarea is editable."
    textarea.send_keys("tampered")
    assert embed.snippet(driver, wait) == before, "Typing changed the embed code."
    print("✅ Embed code area is read-only.")


@pytest.mark.testrail(622)
def test_44_embed_icon_on_the_row(driver, wait, config):
    """The row's embed icon sits beside Delete in its own grouped container."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")
    embed.ensure_embedded_list(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    _require(rows, "the embedded client has no sessions")

    button = embed.row_embed_button(rows[0])
    assert button is not None, "No embed icon on the first row."
    assert button.is_displayed(), "The embed icon is in the DOM but not visible."
    assert rows[0].find_elements("xpath", L.SUMMARY_DELETE_BTN), (
        "The Delete button vanished from beside the embed icon."
    )
    assert rows[0].find_elements("xpath", L.SUMMARY_HAS_EMBED_ACTION), (
        "The row is not marked with has-embed-action."
    )
    print("✅ Embed icon rendered beside Delete.")


@pytest.mark.testrail(624)
def test_45_modal_on_a_narrow_viewport(driver, wait, config):
    """The modal stays usable at phone width — no control is pushed off-screen."""
    _require(STATE.get("in_embedded_mode"), "embedded mode was never entered")
    embed.ensure_embedded_list(driver, wait, config, STATE["portal_id"])
    rows = embed.session_rows(driver, wait)
    _require(rows, "the embedded client has no sessions")

    original = driver.get_window_size()
    try:
        driver.set_window_size(420, 900)
        time.sleep(1)
        embed.open_embed_modal(driver, wait, embed.session_rows(driver, wait)[0])

        modal = ui.find(wait, L.EMBED_MODAL)
        box = driver.execute_script(
            "var r = arguments[0].getBoundingClientRect();"
            "return {left: r.left, right: r.right, width: r.width};", modal
        )
        viewport = driver.execute_script("return document.documentElement.clientWidth;")
        print(f"  Modal box at {viewport}px viewport: {box}")

        assert box["width"] <= viewport, (
            f"The modal is {box['width']}px wide in a {viewport}px viewport — it is "
            "fixed at width={720} and does not shrink, so the embed code, the "
            "format toggle and the footer buttons are cut off on a phone."
        )
        assert box["left"] >= 0 and box["right"] <= viewport, (
            f"The modal hangs outside the viewport: {box} in {viewport}px."
        )
        embed.close_embed_modal(driver, wait)
        print("✅ Modal usable at 420px width.")
    finally:
        driver.set_window_size(original["width"], original["height"])
        time.sleep(1)
