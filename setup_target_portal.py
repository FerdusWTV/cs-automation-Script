"""Create (or reuse) a client and a portal in an organization, for the session suite.

Standalone script, not a test. Idempotent: an existing client or portal with the
requested name is reused, never duplicated. Logs in with the ADMIN account
(`EMAIL` / `PASSWORD`, or the `_PROD` pair) because an org user such as
automation@ cannot reach organizations other than its own.

    ..\\venv\\Scripts\\python setup_target_portal.py \\
        --org "Automated Kollective Test Org" \\
        --client "Automated Kollective Client" \\
        --portal "Automated Kollective Portal 001"

Add `--env=prod` for production. It also reports whether the organization has
Kollective enabled (Organization -> Edit -> 'Enable Kollective'), which the
Kollective session variants depend on.
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import org_flow

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENT_MODAL = "//div[contains(@class,'add-client-modal')][contains(@class,'ant-modal-wrap')]"
DROPDOWN_OPTION = (
    "//div[contains(@class,'ant-select-dropdown') and not(contains(@class,'ant-select-dropdown-hidden'))]"
    "//div[contains(@class,'ant-select-item-option')]"
)


def _wait(driver, timeout=30):
    return WebDriverWait(driver, timeout)


def _click(driver, element):
    driver.execute_script("arguments[0].click();", element)


def _type_search(box, term):
    """Replace a React search box's text (clear() would bypass onChange)."""
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys(Keys.BACKSPACE)
    time.sleep(2)
    box.send_keys(term)
    time.sleep(4)  # 1s debounce, then a refetch


def login(driver, url, email, password):
    driver.get(url)
    _wait(driver).until(EC.presence_of_element_located((By.ID, "email"))).send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CLASS_NAME, "login-button").click()
    _wait(driver, 60).until(EC.presence_of_element_located((By.CLASS_NAME, "header-title")))
    print(f"Logged in as {email}")


def open_org(driver, org):
    """Sidebar 'Organization' -> search -> the org's client list."""
    time.sleep(6)  # sidebar links resolve only once the user lands in redux
    for _ in range(3):
        _click(driver, _wait(driver).until(EC.presence_of_element_located(
            (By.XPATH, "//div[normalize-space()='Organization']")
        )))
        try:
            _wait(driver, 15).until(EC.url_contains("/organization"))
            break
        except TimeoutException:
            time.sleep(4)
    time.sleep(3)
    shown = org_flow.open_organization(driver, org)
    print(f"Opened organization '{shown}'")
    return driver.current_url


def client_listed(driver, client):
    box = _wait(driver).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".client-list-table-container input.search-input")
    ))
    _type_search(box, client)
    return driver.find_elements(
        By.XPATH, f"//div[contains(@class,'client-list-table-container')]//tbody//tr[td[1][normalize-space()='{client}']]"
    )


def create_client(driver, client, language):
    _click(driver, _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[@class='add-client-modal']//button[contains(@class,'save-button')]")
    )))
    _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, f"{CLIENT_MODAL}//div[contains(@class,'con-title')][normalize-space()='New Client']")
    ))
    time.sleep(1)
    driver.find_element(By.XPATH, f"{CLIENT_MODAL}//input[@name='name']").send_keys(client)

    select = driver.find_element(
        By.XPATH, f"{CLIENT_MODAL}//div[contains(@class,'ant-select')][.//span[normalize-space()='Select Language']]"
    )
    select.find_element(By.CSS_SELECTOR, ".ant-select-selector").click()  # antd needs a real mousedown
    time.sleep(1)
    _click(driver, _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, f"{DROPDOWN_OPTION}[normalize-space()='{language}']")
    )))
    time.sleep(1)

    _click(driver, _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, f"{CLIENT_MODAL}//button[contains(@class,'custom-save-btn')]")
    )))
    toast = _wait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".swal2-container"))).text
    if "successfully added" not in toast.lower():
        raise AssertionError(f"Client create failed - toast said {toast!r}")
    _wait(driver).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
    time.sleep(3)
    print(f"Created client '{client}'")


def open_client_portals(driver, client):
    rows = client_listed(driver, client)
    if not rows:
        raise AssertionError(f"Client '{client}' not found in the client list")
    _click(driver, rows[0].find_element(By.CSS_SELECTOR, "td.portal-view-button"))
    _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[@class='con-title'][normalize-space()='Portals']")
    ))
    time.sleep(3)


def portal_listed(driver, portal):
    box = _wait(driver).until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input.connect-studio-search-input-small")
    ))
    _type_search(box, portal)
    return [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, ".portal-name-text")
            if e.text.strip() == portal]


def create_portal(driver, org, client, portal, logo_path):
    """Sidebar 'Create Portal' -> Branding (org, client, logos) -> Home (name)."""
    _click(driver, _wait(driver).until(EC.presence_of_element_located(
        (By.XPATH, "//div[normalize-space()='Create Portal']")
    )))
    _wait(driver).until(EC.url_contains("/new/branding"))
    time.sleep(3)

    if org_flow.has_branding_org_select(driver):
        org_flow.pick_branding_option(driver, "Organization", org)
        time.sleep(3)
    org_flow.pick_branding_option(driver, "Client", client)
    org_flow.upload_branding_logos(driver, logo_path)

    _click(driver, _wait(driver).until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-testid='branding-next-button']")
    )))
    _wait(driver, 120).until(EC.url_matches(r".*/[0-9a-f]{6,}/home"))
    portal_id = driver.current_url.rstrip("/").split("/")[-2]

    name_input = _wait(driver).until(EC.presence_of_element_located((By.ID, "eventName")))
    name_input.send_keys(Keys.CONTROL, "a")
    name_input.send_keys(Keys.BACKSPACE)
    name_input.send_keys(portal)
    time.sleep(1)
    _click(driver, _wait(driver).until(EC.element_to_be_clickable(
        (By.XPATH, "//button[@type='submit'][contains(normalize-space(),'Save')]")
    )))
    time.sleep(6)
    print(f"Created portal '{portal}' (id {portal_id})")
    return portal_id


def kollective_status(driver, org_list_url, org):
    """Read the org's 'Enable Kollective' switch from its Edit modal (read-only)."""
    driver.get(org_list_url.split("/organization")[0] + "/organization")
    try:
        box = _wait(driver).until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='search']")))
        box.send_keys(org)
        card = _wait(driver).until(EC.presence_of_element_located(
            (By.XPATH, f"//div[contains(@class,'org-card')][.//h6[normalize-space()='{org}']]")
        ))
        # The pencil is a bare react-icons <svg>; SVG elements have no .click().
        pencil = card.find_element(By.CSS_SELECTOR, ".edit-icon svg")
        driver.execute_script(
            "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", pencil
        )
        checkbox = _wait(driver, 15).until(EC.presence_of_element_located((
            By.XPATH,
            "//div[contains(@class,'switch-button-container')]"
            "[div[normalize-space()='Enable Kollective']]//input[@type='checkbox']",
        )))
        return "enabled" if checkbox.is_selected() else "DISABLED"
    except TimeoutException:
        return "unknown (could not read the Edit Organization modal)"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True)
    parser.add_argument("--client", required=True)
    parser.add_argument("--portal", required=True)
    parser.add_argument("--language", default="English", help="New client's language (default English)")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev")
    parser.add_argument("--headed", action="store_true", help="Show the browser")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    sfx = "_PROD" if args.env == "prod" else ""
    url, email, password = (os.getenv(f"URL{sfx}"), os.getenv(f"EMAIL{sfx}"), os.getenv(f"PASSWORD{sfx}"))
    if not all((url, email, password)):
        sys.exit(f"URL{sfx} / EMAIL{sfx} / PASSWORD{sfx} must be set in .env")
    logo = os.getenv("PORTAL_LOGO_PATH") or os.getenv("HEADSHOT_PATH")
    if not logo or not os.path.exists(logo) or os.path.getsize(logo) > 200 * 1024:
        sys.exit(f"Need a portal logo image under 200 KB (PORTAL_LOGO_PATH / HEADSHOT_PATH), got {logo!r}")

    options = Options()
    if not args.headed:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(2)
    try:
        login(driver, url, email, password)
        org_url = open_org(driver, args.org)

        if client_listed(driver, args.client):
            print(f"Client '{args.client}' already exists - reusing it")
        else:
            create_client(driver, args.client, args.language)

        open_client_portals(driver, args.client)
        if portal_listed(driver, args.portal):
            print(f"Portal '{args.portal}' already exists - reusing it")
        else:
            create_portal(driver, args.org, args.client, args.portal, logo)
            driver.get(org_url)
            _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".client-list-table-container")))
            time.sleep(3)
            open_client_portals(driver, args.client)
            if not portal_listed(driver, args.portal):
                raise AssertionError(f"Portal '{args.portal}' not listed under '{args.client}' after creating it")
            print(f"Verified portal '{args.portal}' is listed under '{args.client}'")

        print(f"Kollective on '{args.org}': {kollective_status(driver, org_url, args.org)}")
    except Exception:
        driver.save_screenshot("failure_setup_target_portal.png")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
