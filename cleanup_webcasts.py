"""Delete leftover automation-created webcasts ('Automated Webcast ...') from the portal.

Only touches summaries whose event name starts with 'Automated Webcast'.
Discovers and handles the delete-confirmation dialog, logging everything.
"""
import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PREFIX = "Automated Webcast"
NAME_XPATH = ".//div[contains(@class,'webcast-summary-event-name')]//div[contains(@class,'webcast-summary-background')]"
DELETE_BTN_XPATH = ".//div[contains(@class,'webcast-summary-delete')]//button"

load_dotenv()
options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(options=options)
driver.implicitly_wait(5)

def get_summaries(wait):
    try:
        return wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "webcast-summary")))
    except Exception:
        return []

try:
    driver.get(os.getenv("URL_PROD"))
    driver.find_element(By.ID, "email").send_keys(os.getenv("EMAIL_PROD"))
    driver.find_element(By.ID, "password").send_keys(os.getenv("PASSWORD_PROD"))
    driver.find_element(By.CLASS_NAME, "login-button").click()
    WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CLASS_NAME, "header-title")))
    print("Logged in.")

    wait = WebDriverWait(driver, 30)
    sb = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search portal']")))
    sb.send_keys(os.getenv("TARGET_PORTAL_PROD") or os.getenv("TARGET_PORTAL", "General Information"))
    eb = wait.until(EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Edit']")))
    driver.execute_script("arguments[0].click();", eb)
    wait.until(EC.presence_of_element_located((By.XPATH, "(//p[@class='branding-information-text mt-1'])[1]")))
    time.sleep(2)
    s = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Sessions')]")))
    driver.execute_script("arguments[0].click();", s)
    time.sleep(3)

    deleted = 0
    for round_no in range(50):  # safety cap
        summaries = get_summaries(wait)
        target = None
        for summary in summaries:
            try:
                name = summary.find_element(By.XPATH, NAME_XPATH).text.strip()
            except Exception:
                continue
            if name.startswith(PREFIX):
                target = (summary, name)
                break
        if target is None:
            print(f"\nDone. {deleted} automation webcasts deleted; "
                  f"{len(summaries)} non-automation summaries remain.")
            break

        summary, name = target
        before = len(summaries)
        print(f"Deleting: {name!r} ...")
        trash = summary.find_element(By.XPATH, DELETE_BTN_XPATH)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", trash)
        trash.click()

        # 'Delete Webcast — Are you sure...?' antd modal with a 'Confirm' footer button
        confirm = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class,'ant-modal-footer')]//button[normalize-space()='Confirm']")
        ))
        confirm.click()
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".ant-modal-mask")))
        time.sleep(2)

        after = len(get_summaries(WebDriverWait(driver, 10))) if before > 1 else 0
        if after >= before:
            print(f"  ⚠️ Summary count did not decrease ({before} -> {after}); aborting to avoid a loop.")
            break
        print(f"  Deleted ({before} -> {after}).")
        deleted += 1
    else:
        print("Safety cap reached.")
finally:
    driver.quit()
