import time
from selenium.webdriver.common.by import By

def close_popups(driver):
    selectors = [
        "//button[contains(@aria-label,'Close')]",
        "//button[@data-testid='ModalCloseButton']",
        "//button[contains(@class,'kds-CloseButton')]",
        "//button[text()='×']",
        "//div[@role='dialog']//button"
    ]
    for sel in selectors:
        try:
            elements = driver.find_elements(By.XPATH, sel)
            for el in elements:
                if el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.5)
        except:
            pass


def get_modal_html(driver) -> str:
    time.sleep(6)  # Give modal time to fully render
    try:
        modal = driver.find_element(By.CSS_SELECTOR, "div.ReactModal__Content")
        return modal.get_attribute("outerHTML")
    except:
        pass
    try:
        modal = driver.find_element(By.CSS_SELECTOR, "div.kds-Modal-content")
        return modal.get_attribute("outerHTML")
    except:
        pass
    try:
        modal = driver.find_element(By.CSS_SELECTOR, "div[role='dialog']")
        return modal.get_attribute("outerHTML")
    except:
        return driver.page_source


# ================= ENHANCED SCROLLING =================
def enhanced_scroll_to_bottom(driver):
    print("Starting enhanced scroll to load all deals...")
    for i in range(10):
        driver.execute_script("window.scrollBy(0, 1500);")
        time.sleep(0.5)

    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    while attempts < 20:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            time.sleep(0.5)
            if new_height == driver.execute_script("return document.body.scrollHeight"):
                break
        last_height = new_height
        attempts += 1
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    print("Enhanced scroll complete")


# ================= NAME EXTRACTION =================
def get_displayed_name(card) -> str:
    selectors = [
        "span.SWA-OmniDealDescription2Lines",
        ".kds-Heading--m",
        "h2",
        "[data-testid*='description']"
    ]
    for sel in selectors:
        try:
            elem = card.find_element(By.CSS_SELECTOR, sel)
            text = elem.text.strip()
            if text:
                return text
        except:
            continue
    try:
        return card.find_element(By.TAG_NAME, "img").get_attribute("alt").strip()
    except:
        return card.text.strip().split("\n")[0].strip() or "Unknown Product"
