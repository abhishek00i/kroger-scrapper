# kroger_fast_scraper.py
# Optimized Kroger Weekly Ad Scraper - Runs in 2-3 minutes
# Single file - no dependencies other than listed below

import json
import time
import re
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

# ===================== FASTAPI SETUP =====================
app = FastAPI(title="Kroger Weekly Deals Fast Scraper")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeResponse(BaseModel):
    deals: List[Dict[str, Any]]
    total: int
    success: bool

# ===================== DRIVER SETUP =====================
def init_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-images")  # Critical for speed
    opts.add_argument("--disable-javascript")  # Optional: test without if needed
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.page_load_strategy = 'eager'

    # Block images & media
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.media": 2
    })

    ua = UserAgent(browsers=['chrome'])
    opts.add_argument(f"--user-agent={ua.random}")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=opts
    )

    # Hide webdriver fingerprint
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """
    })
    return driver

# ===================== HELPER FUNCTIONS =====================
def close_popups(driver):
    selectors = [
        "//button[contains(@aria-label,'Close') or contains(@aria-label,'close')]",
        "//button[@data-testid='ModalCloseButton']",
        "//button[contains(@class,'CloseButton') or contains(text(),'×')]",
        "//div[@role='dialog']//button"
    ]
    for sel in selectors:
        try:
            els = driver.find_elements(By.XPATH, sel)
            for el in els[:3]:
                if el.is_displayed():
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.2)
        except:
            pass

def get_modal_html(driver) -> str:
    try:
        modal = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.ReactModal__Content, div.kds-Modal-content, div[role='dialog'], div[data-testid*='modal']"
            ))
        )
        return modal.get_attribute("outerHTML")
    except:
        return driver.page_source

def fast_scroll_to_load_all(driver):
    print("Scrolling to load all deals...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    while scrolls < 40:  # Max 40 fast scrolls
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.7)  # Fast but stable
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            time.sleep(1)
            if new_height == driver.execute_script("return document.body.scrollHeight"):
                break
        last_height = new_height
        scrolls += 1
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    print(f"Scroll complete after {scrolls} attempts")

def get_displayed_name(card) -> str:
    selectors = [
        "span.SWA-OmniDealDescription2Lines",
        ".kds-Heading--m",
        "h2",
        "[data-testid*='description']"
    ]
    for sel in selectors:
        try:
            el = card.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            if text:
                return text
        except:
            continue
    try:
        return card.find_element(By.TAG_NAME, "img").get_attribute("alt").strip()
    except:
        lines = card.text.strip().split("\n")
        return lines[0] if lines else "Unknown"

def parse_kroger_modal(html: str, displayed_name: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    source_url = "https://www.kroger.com/pr/weekly-digital-deals"
    offer_event = "Weekly Digital Deals"
    offer_sale = "Digital coupon offer"

    is_coupon_modal = bool(soup.find(string=re.compile("Sign In To Clip", re.I)))
    competitor_price = "N/A"
    original_price_main = ""

    if is_coupon_modal:
        desc = soup.find("h2", {"data-testid": "CouponDetails-shortDescription"})
        if desc:
            text = desc.get_text(strip=True)
            match = re.search(r'\$\d[\d,.]*', text)
            competitor_price = match.group() if match else "N/A"
        orig = soup.find("s", class_="kds-Price-original")
        if orig:
            original_price_main = orig.get_text(strip=True)
    else:
        price_tag = soup.find("span", class_="SWA-ModalPriceText")
        if price_tag:
            competitor_price = price_tag.get_text(strip=True)
        orig = soup.find("del") or soup.find("s")
        if orig:
            original_price_main = orig.get_text(strip=True)

    # Qualifying products
    qualifying_cards = []
    section = soup.find("h2", string="Qualifying Products")
    if section:
        grid = section.find_next("div", class_=re.compile("ProductGrid|AutoGrid|CouponQualifying"))
        if grid:
            qualifying_cards = grid.find_all("div", class_=re.compile("MiniProductCard|flex flex-col"))

    # Main deal
    results.append({
        "competitor_product": displayed_name.strip(),
        "competitor_price": competitor_price,
        "original_price": original_price_main or "N/A",
        "offer_description": "Weekly Digital Deal",
        "offer_sale": offer_sale,
        "source_URL": source_url,
        "competitor_product_size": "N/A",
        "offer_event": offer_event,
        "Compatitor_name": "Kroger",
        "Qualifying Products": False
    })

    # Qualifying items
    for card in qualifying_cards:
        name_tag = card.find("span", {"data-testid": "cart-page-item-description"}) or \
                   card.find("span", class_=re.compile("kds-Text--m|kds-Text--bold"))
        name = name_tag.get_text(strip=True) if name_tag else "Unknown"

        price_tag = card.find("mark", class_="kds-Price-promotional") or \
                    card.find("data", class_="kds-Price")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        orig_tag = card.find("s", class_="kds-Price-original") or card.find("del")
        orig_price = orig_tag.get_text(strip=True) if orig_tag else ""

        size_tag = card.find("span", {"data-testid": "product-item-sizing"})
        size = size_tag.get_text(strip=True) if size_tag and not size_tag.get_text().startswith("$") else ""
        if not size:
            m = re.search(r'(\d[\d\.]* ?(oz|lb|g|ml|L|pack|ct|each))', name, re.I)
            size = m.group(1) if m else "N/A"

        results.append({
            "competitor_product": name,
            "competitor_price": price,
            "original_price": orig_price or "N/A",
            "offer_description": "Weekly Digital Deal",
            "offer_sale": offer_sale,
            "source_URL": source_url,
            "competitor_product_size": size,
            "offer_event": offer_event,
            "Compatitor_name": "Kroger",
            "Qualifying Products": True
        })

    return results if len(results) > 1 else results

# ===================== MAIN ENDPOINT =====================
@app.get("/scrape-kroger-deals", response_model=ScrapeResponse)
async def scrape_kroger_deals(limit: int = 500):
    driver = None
    try:
        start_time = time.time()
        driver = init_driver()
        all_deals = []

        print("Loading Kroger Weekly Ad...")
        driver.get("https://www.kroger.com/weeklyad/weeklyad")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        for _ in range(3):
            close_popups(driver)
            time.sleep(0.4)

        fast_scroll_to_load_all(driver)

        cards = driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")
        print(f"Found {len(cards)} deal cards")

        processed = 0
        for idx, card in enumerate(cards):
            if processed >= limit:
                break

            name = get_displayed_name(card)
            if not name or "Unknown" in name or len(name) < 3:
                continue

            print(f"[{processed+1}/{min(limit, len(cards))}] {name}")

            clicked = False
            for selector in [
                "button[data-testid='SWA-Omni-ImageContainer']",
                "img",
                "button[role='button']"
            ]:
                try:
                    btn = card.find_element(By.CSS_SELECTOR, selector)
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked = True
                    break
                except:
                    continue

            if not clicked:
                continue

            modal_html = get_modal_html(driver)
            products = parse_kroger_modal(modal_html, name)
            all_deals.extend(products)
            processed += len(products) if isinstance(products, list) else 1

            close_popups(driver)
            time.sleep(0.5)  # Minimal delay

        # Save result
        with open("kroger_deals_fast.json", "w", encoding="utf-8") as f:
            json.dump(all_deals, f, indent=2, ensure_ascii=False)

        elapsed = int(time.time() - start_time)
        print(f"Scraping completed in {elapsed} seconds! Total deals: {len(all_deals)}")

        return JSONResponse({
            "deals": all_deals,
            "total": len(all_deals),
            "success": True,
            "time_seconds": elapsed
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.quit()

@app.get("/")
def root():
    return {"message": "Kroger Fast Scraper Ready! Use /scrape-kroger-deals?limit=300"}

if __name__ == "__main__":
    import uvicorn
    print("Starting Kroger Fast Scraper on http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)