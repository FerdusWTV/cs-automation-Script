"""Organization navigation and Create Portal branding steps shared by the suites.

Used by `01_client_test.py`, `02_portal_test.py` and `04_language_test.py`.
The rules encoded here:

* **Always find an organization with the Organizations search bar.** The list is
  paginated (17+ pages on dev), so a named org is never looked up on page 1.
* **An org user only ever sees its own organization.** `EMAIL_ORG`
  (automation@wtv.com on dev) belongs to 'Automated Test ORG' and lands straight
  on that client list. Asking it for any other org fails loudly instead of
  quietly working in the wrong place - use the admin account (`EMAIL`) there.
* **Create Portal asks for the organization again.** The Organization and Client
  selects are rendered with `value={null}`, so antd shows no placeholder text to
  find them by; they are located by their form label, and the name is typed into
  the select's search box.
* **Material-template orgs also require the 'Registration, Login page logo'**
  (`handleOnSave` in components/Branding/index.js returns early without it).
"""

import os
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import locators as L

DROPDOWN = ("//div[contains(@class,'ant-select-dropdown') and "
            "not(contains(@class,'ant-select-dropdown-hidden'))]")
DROPDOWN_OPTION = f"{DROPDOWN}//div[contains(@class,'ant-select-item-option')]"


def _click(driver, element):
    driver.execute_script("arguments[0].click();", element)


# ==========================================================================
# Organizations list
# ==========================================================================

def open_organization(driver, org_name=None, timeout=30):
    """From the Organizations page, land on `org_name`'s client list.

    Returns the organization name the client list shows. With no `org_name`, an
    admin gets the first organization card and an org user its own org.
    Raises AssertionError when the org can't be reached or the wrong one opened.
    """
    wait = WebDriverWait(driver, timeout)
    wait.until(lambda d: d.find_elements(
        By.CSS_SELECTOR, ".org-card, .client-list-table-container"
    ))
    org_user = not driver.find_elements(By.CSS_SELECTOR, ".org-card")

    if not org_user:
        if org_name:
            box = wait.until(EC.presence_of_element_located((By.XPATH, L.ORG_SEARCH_INPUT)))
            box.send_keys(org_name)
            try:
                arrow = WebDriverWait(driver, 15).until(EC.presence_of_element_located(
                    (By.XPATH, L.org_card_open(org_name))
                ))
            except TimeoutException:
                found = [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, ".org-card h6")]
                raise AssertionError(
                    f"Organization '{org_name}' not found with the Organizations search "
                    f"(results: {found})."
                )
        else:
            arrow = driver.find_element(By.CSS_SELECTOR, ".org-card .org-card-arrow")
        _click(driver, arrow)
        wait.until(EC.url_contains("/organization/client"))

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".client-list-table-container")))
    time.sleep(3)
    shown = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".client-org-name")
    )).text.strip()

    if org_name and shown != org_name:
        hint = (
            f" The logged-in account is an org user for '{shown}' and cannot reach other "
            "organizations - log in with the admin account (EMAIL / PASSWORD) instead."
            if org_user else ""
        )
        raise AssertionError(f"Opened organization '{shown}', expected '{org_name}'.{hint}")
    return shown


# ==========================================================================
# Create Portal -> Branding
# ==========================================================================

def branding_select(label):
    """The antd Select inside the Branding form field labelled `label`."""
    return (
        f"//div[contains(@class,'bf-field')][label[normalize-space()='{label}']]"
        "//div[contains(@class,'ant-select')]"
    )


def has_branding_org_select(driver):
    """The Organization select only renders for ADMIN / SUPER_ADMIN accounts."""
    return bool(driver.find_elements(By.XPATH, branding_select("Organization")))


def pick_branding_option(driver, label, wanted=None, timeout=30):
    """Choose `wanted` in the Branding select labelled `label` by typing it in.

    None takes the first option. Returns the chosen option text.
    """
    wait = WebDriverWait(driver, timeout)
    select = wait.until(EC.presence_of_element_located((By.XPATH, branding_select(label))))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", select)
    time.sleep(1)
    # antd opens on a real mousedown against the selector; a JS click does nothing.
    select.find_element(By.CSS_SELECTOR, ".ant-select-selector").click()
    time.sleep(1)

    if wanted:
        select.find_element(By.CSS_SELECTOR, "input.ant-select-selection-search-input").send_keys(wanted)
        try:
            option = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"{DROPDOWN_OPTION}[normalize-space()='{wanted}']")
            ))
        except TimeoutException:
            shown = [e.text for e in driver.find_elements(By.XPATH, DROPDOWN_OPTION)]
            raise AssertionError(f"{label}: '{wanted}' is not offered (options: {shown}).")
    else:
        option = wait.until(lambda d: d.find_elements(By.XPATH, DROPDOWN_OPTION) or False)[0]

    chosen = option.text.strip()
    _click(driver, option)
    time.sleep(1)
    wait.until(lambda d: chosen in select.text)
    return chosen


def upload_cropped_logo(driver, field_label, path, timeout=30):
    """Upload `path` into the Branding logo field `field_label` and confirm the crop.

    The crop modal only yields an image after a real crop interaction -
    `onComplete` never fires from the auto-centered initial crop alone.
    """
    wait = WebDriverWait(driver, timeout)
    file_input = wait.until(EC.presence_of_element_located((
        By.XPATH,
        f"//div[contains(@class,'bf-field')][label[contains(normalize-space(),'{field_label}')]]"
        "//input[@type='file']",
    )))
    # react-dropzone's file input is hidden but writable.
    driver.execute_script(
        "arguments[0].style.display='block';arguments[0].style.opacity=1;", file_input
    )
    file_input.send_keys(os.path.abspath(path))

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".crop-image-modal")))
    handle = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".ReactCrop__drag-handle.ord-se")
    ))
    ActionChains(driver).click_and_hold(handle).move_by_offset(-12, -9).release().perform()
    time.sleep(2)
    _click(driver, wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//div[contains(@class,'crop-image-modal')]//button[normalize-space()='Set']")
    )))
    try:
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".crop-image-modal")))
    except TimeoutException:
        raise AssertionError(f"Crop modal never closed for '{field_label}' - 'Set' had no cropped image.")
    time.sleep(1)


def upload_branding_logos(driver, path):
    """Upload the header logo, plus the registration logo when the template needs it."""
    upload_cropped_logo(driver, "Header menu logo", path)
    template = driver.find_element(By.XPATH, branding_select("Template style")).text
    if template.strip().lower().startswith("material"):
        upload_cropped_logo(driver, "Registration, Login page logo", path)
