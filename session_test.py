"""End-to-end suite: create and configure one webcast of every type.

The tests run in order and share one browser session:

    test_00_cleanup           delete leftovers from previous runs
    test_01_login             log into the admin org
    test_02_open_target_portal  open the portal under test
    test_03_create_all_webcasts create + configure each webcast type

Run from this directory:

    ..\\venv\\Scripts\\pytest -v --env=prod --html=report.html --self-contained-html

Useful options (see conftest.py): `--env=dev|prod`, `--base-url=...`, and
`--webcast-type=VxS|AxS|V|A|AxE` to build just one webcast instead of all five.

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

# The five webcasts test_03 builds: (config key for the title, config key for
# the type label, content-spec key in webcast_flow.CONTENT_SPECS).
WEBCAST_MATRIX = [
    (0, "webcast_type_1", "VxS"),
    (1, "webcast_type_2", "AxS"),
    (2, "webcast_type_3", "V"),
    (3, "webcast_type_4", "A"),
    (4, "webcast_type_5", "AxE"),
]


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
    """Start every run clean: delete 'Automated Webcast *' leftovers.

    Uses its own short-lived headless browser so the shared session driver still
    starts logged-out for test_01_login.
    """
    cleanup_driver = _new_chrome(headless=True)
    cleanup_driver.implicitly_wait(5)
    try:
        cleanup_wait = WebDriverWait(cleanup_driver, 30)
        flow.login(cleanup_driver, config)
        flow.open_portal(cleanup_driver, cleanup_wait, config["target_portal"])
        flow.open_sessions_page(cleanup_driver, cleanup_wait)
        flow.delete_all_webcasts(cleanup_driver, cleanup_wait)
    finally:
        cleanup_driver.quit()


def test_01_login(driver, config):
    welcome_text = flow.login(driver, config)
    assert "Welcome" in welcome_text, "Login failed — 'Welcome' not found."
    print(f"✅ Login successful: {welcome_text}")


def test_02_open_target_portal(driver, wait, config):
    portal_title = flow.open_portal(driver, wait, config["target_portal"])
    assert "Portal" in portal_title, "Portal title validation failed."
    print(f"✅ Opened portal: {portal_title}")


def test_03_create_all_webcasts(driver, wait, config):
    """Create, activate, set type, upload the type's content, and configure layout."""
    webcasts = _webcasts_to_build(config)

    for i, (title, type_label, type_key) in enumerate(webcasts, start=1):
        print(f"\n{'='*60}")
        print(f"  WEBCAST {i}/{len(webcasts)}: '{title}'  [{type_key}: {type_label}]")
        print(f"{'='*60}")

        flow.create_webcast(driver, wait, title)
        flow.activate_and_open_manage(driver, wait, title)
        flow.set_webcast_type(driver, wait, type_label)
        flow.upload_content(driver, wait, config, type_key)
        flow.configure_layout(driver, wait, type_key)

        print(f"  🎉 Webcast {i}/{len(webcasts)} '{title}' fully done!\n")

    print("✅ All webcasts created and configured successfully!")


def _webcasts_to_build(config):
    """(title, type label, spec key) per webcast, honouring --webcast-type."""
    webcasts = [
        (config["webcast_titles"][title_idx], config[type_cfg], type_key)
        for title_idx, type_cfg, type_key in WEBCAST_MATRIX
    ]

    single = config.get("single_webcast_type")
    if not single:
        return webcasts

    webcasts = [w for w in webcasts if w[2] == single]
    if not webcasts:
        pytest.fail(f"No webcast defined for type '{single}' — choose one of: VxS, AxS, V, A, AxE.")
    print(f"\nSingle-webcast mode: creating only the '{single}' webcast.")
    return webcasts
