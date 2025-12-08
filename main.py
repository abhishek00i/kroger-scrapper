from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scraper.driver import init_driver
from scraper.bs4_parser import parse_kroger_modal
from scraper.kroger_scrapper import close_popups, get_modal_html, enhanced_scroll_to_bottom, get_displayed_name
import time
import json


app = FastAPI(title="Kroger Weekly Deals Scraper API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= ENDPOINT =================
class ScrapeResponse(BaseModel):
    deals: List[Dict[str, Any]]
    total: int
    success: bool


@app.get("/scrape-kroger-deals", response_model=ScrapeResponse)
async def scrape_kroger_deals(limit: int = 1000):
    driver = None
    try:
        driver = init_driver()
        all_deals = []

        driver.get("https://www.kroger.com/weeklyad/weeklyad")
        time.sleep(5)

        for _ in range(5):
            close_popups(driver)
            time.sleep(0.5)

        enhanced_scroll_to_bottom(driver)

        cards = driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")
        print(f"Found {len(cards)} deal cards")

        processed = 0
        for idx, card in enumerate(cards):
            if processed >= limit:
                break

            try:
                name = get_displayed_name(card)
                if not name or "Unknown" in name:
                    continue

                print(f"Processing {idx + 1}: {name}")

                # Click image/button
                clicked = False
                for sel in ["button[data-testid='SWA-Omni-ImageContainer']", "button[role='button'] img"]:
                    try:
                        btn = WebDriverWait(card, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.5)
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
                processed += 1

                close_popups(driver)
                time.sleep(0.5)

            except Exception as e:
                print(f"Error on card {idx + 1}: {e}")
                close_popups(driver)
                time.sleep(0.5)
                continue

        # Save for debugging
        with open("/Users/abhishek/kroger/scrapper_v2/output/kroger_full.json", "w", encoding="utf-8") as f:
            json.dump(all_deals, f, indent=2, ensure_ascii=False)

        return JSONResponse(
                    content={
                        "deals": all_deals,
                        "total": len(all_deals),
                        "success": True
                    }
                )
        

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.quit()


@app.get("/")
def root():
    return {"message": "Kroger Weekly Deals Scraper - Use /scrape-kroger-deals?limit=100"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)