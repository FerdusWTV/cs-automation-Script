"""End-to-end suite: create and configure two webcasts of every type — one with
the Kollective eCDN, one without.

The tests run in order and share one browser session:

    test_00_cleanup           delete leftovers from previous runs
    test_01_login             log into the admin org
    test_02_open_target_portal  open the portal under test
    test_03_create_all_webcasts create + configure each webcast type, with
                                eCDN 'None' and with eCDN 'Kollective'

Run from this directory:

    ..\\venv\\Scripts\\pytest -v --env=prod --html=report.html --self-contained-html

Useful options (see conftest.py): `--env=dev|prod`, `--base-url=...`,
`--webcast-type=VxS|AxS|V|A|AxE` to build just one type instead of all five, and
`--ecdn=both|kollective|none` to build only one eCDN variant of each.

The UI steps live in `webcast_flow.py`, the selectors in `locators.py`, and the
click/wait plumbing in `ui.py`.
"""

import os

import pytest
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import webcast_flow as flow

# The five webcast types test_03 builds: (index into config["webcast_titles"],
# config key for the type label, content-spec key in webcast_flow.CONTENT_SPECS).
WEBCAST_MATRIX = [
    (0, "webcast_type_1", "VxS"),
    (1, "webcast_type_2", "AxS"),
    (2, "webcast_type_3", "V"),
    (3, "webcast_type_4", "A"),
    (4, "webcast_type_5", "AxE"),
]

# Each type is built once per eCDN variant. The Kollective titles sit five
# places after the 'None' ones (NEW_WEBCAST_TITLE_6..10).
KOLLECTIVE_TITLE_OFFSET = 5


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
    return options


def _new_chrome(headless=False):
    """Build a Chrome driver, using the DRIVER env path if one is configured."""
    options = _chrome_options(headless)
    driver_path = os.getenv("DRIVER")
    if driver_path and os.path.exists(driver_path):
        return webdriver.Chrome(service=Service(driver_path), options=options)
    return webdriver.Chrome(options=options)


@pytest.fixture(scope="session")
def driver():
    """The browser shared by test_01 onwards."""
    load_dotenv()
    driver = _new_chrome()
    driver.implicitly_wait(5)
    driver.maximize_window()
    yield driver
    driver.quit()


@pytest.fixture
def wait(driver):
    """Standard 30s wait against the shared browser."""
    return WebDriverWait(driver, 30)


# ----------------------- TEST CASES -----------------------

def test_00_cleanup(config):
    """Start every run clean: delete 'Automated Webcast *' leftovers in each
    portal this run builds in.

    Uses its own short-lived headless browser so the shared session driver still
    starts logged-out for test_01_login.
    """
    for target in (t for t in _targets(config) if "same_as" not in t):
        print(f"\nCleaning '{target['portal']}' ({target['variant']} sessions)")
        cleanup_driver = _new_chrome(headless=True)
        cleanup_driver.implicitly_wait(5)
        try:
            cleanup_wait = WebDriverWait(cleanup_driver, 30)
            flow.login(cleanup_driver, target["account"])
            flow.open_portal(cleanup_driver, cleanup_wait, target["portal"])
            flow.open_sessions_page(cleanup_driver, cleanup_wait)
            flow.delete_all_webcasts(cleanup_driver, cleanup_wait)
        finally:
            cleanup_driver.quit()


def test_01_login(driver, config):
    welcome_text = flow.login(driver, _targets(config)[0]["account"])
    assert "Welcome" in welcome_text, "Login failed — 'Welcome' not found."
    print(f"✅ Login successful: {welcome_text}")


def test_02_open_target_portal(driver, wait, config):
    portal_title = flow.open_portal(driver, wait, _targets(config)[0]["portal"])
    assert "Portal" in portal_title, "Portal title validation failed."
    print(f"✅ Opened portal: {portal_title}")


def test_03_create_all_webcasts(driver, wait, config):
    """Create, activate, set eCDN + type, upload the type's content, and configure layout."""
    webcasts = _webcasts_to_build(config)
    current = _targets(config)[0]  # where test_01/test_02 left the browser

    for i, (title, type_label, type_key, ecdn, target) in enumerate(webcasts, start=1):
        if target is not current:
            _switch_target(driver, wait, target)
            current = target

        print(f"\n{'='*60}")
        print(f"  WEBCAST {i}/{len(webcasts)}: '{title}'  [{type_key}: {type_label} | eCDN: {ecdn}]")
        print(f"  in portal '{target['portal']}'")
        print(f"{'='*60}")

        flow.create_webcast(driver, wait, title)
        flow.activate_and_open_manage(driver, wait, title)
        flow.set_ecdn(driver, wait, ecdn)
        flow.set_webcast_type(driver, wait, type_label)
        flow.upload_content(driver, wait, config, type_key)
        flow.configure_layout(driver, wait, config, type_key)

        print(f"  🎉 Webcast {i}/{len(webcasts)} '{title}' fully done!\n")

    print("✅ All webcasts created and configured successfully!")


def _chosen_variants(config):
    """The eCDN variants this run builds, per --ecdn: 'none' first, then 'kollective'."""
    mode = config.get("ecdn_mode") or "both"
    return ["none", "kollective"] if mode == "both" else [mode]


_TARGETS = {}


def _targets(config):
    """Where each variant's sessions go: [{variant, portal, account}], in build order.

    'none' sessions go to TARGET_PORTAL with the org account (EMAIL_ORG).
    'kollective' sessions go to KOLLECTIVE_PORTAL — whose org has Kollective
    enabled — with the admin account (EMAIL), since the org account can't reach
    other organizations. With no KOLLECTIVE_PORTAL set, they fall back to
    TARGET_PORTAL and the org account. Built once, so test_03 can compare
    targets by identity.
    """
    if "list" in _TARGETS:
        return _TARGETS["list"]

    org_account = {k: config[k] for k in ("url_org", "email_org", "password_org")}
    targets = []
    for variant in _chosen_variants(config):
        if variant == "kollective" and config["kollective_portal"]:
            targets.append({"variant": variant, "portal": config["kollective_portal"],
                            "account": config["kollective_account"]})
        else:
            targets.append({"variant": variant, "portal": config["target_portal"],
                            "account": org_account})

    # Same portal + account for both variants: one target, no account switch.
    if len(targets) == 2 and (targets[0]["portal"], targets[0]["account"]) == \
            (targets[1]["portal"], targets[1]["account"]):
        targets[1] = {**targets[1], "same_as": targets[0]}
    _TARGETS["list"] = targets
    return targets


def _target_for(config, variant):
    target = next(t for t in _targets(config) if t["variant"] == variant)
    return target.get("same_as", target)


def _switch_target(driver, wait, target):
    """Log out, log in with the target's account, and open its portal."""
    print(f"\n↪️  Switching to portal '{target['portal']}' as {target['account']['email_org']}")
    driver.delete_all_cookies()
    driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    flow.login(driver, target["account"])
    flow.open_portal(driver, wait, target["portal"])


def _webcasts_to_build(config):
    """(title, type label, spec key, eCDN option, target) per webcast.

    Honours --ecdn (which variants) and --webcast-type (which type). The 'None'
    variants come first, then the Kollective ones.
    """
    variants = {
        "none": (0, flow.ECDN_NONE),
        "kollective": (KOLLECTIVE_TITLE_OFFSET, config["kollective_label"]),
    }

    webcasts = [
        (config["webcast_titles"][title_idx + offset], config[type_cfg], type_key, ecdn,
         _target_for(config, v))
        for v in _chosen_variants(config)
        for offset, ecdn in [variants[v]]
        for title_idx, type_cfg, type_key in WEBCAST_MATRIX
    ]

    single = config.get("single_webcast_type")
    if not single:
        return webcasts

    webcasts = [w for w in webcasts if w[2] == single]
    if not webcasts:
        pytest.fail(f"No webcast defined for type '{single}' — choose one of: VxS, AxS, V, A, AxE.")
    print(f"\nSingle-type mode: creating only the '{single}' webcast(s).")
    return webcasts
