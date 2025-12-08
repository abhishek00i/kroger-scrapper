# main.py — FINAL 100% WORKING ASYNC KROGER SCRAPER
import json
import time
import os
import uuid
import threading
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Your scraper imports
from scraper.driver import init_driver
from scraper.bs4_parser import parse_kroger_modal
from scraper.kroger_scrapper import close_popups, get_modal_html, enhanced_scroll_to_bottom, get_displayed_name
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

JOBS_DIR = "/Users/abhishek/kroger/scrapper_v2/jobs"
os.makedirs(JOBS_DIR, exist_ok=True)
STATUS_FILE = os.path.join(JOBS_DIR, "status.json")

# === Initialize status.json safely ===
def init_status_file():
    if not os.path.exists(STATUS_FILE) or os.path.getsize(STATUS_FILE) == 0:
        initial = {
            "current_job": None,
            "jobs": {}
        }
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2)

init_status_file()  # ← This was missing!

def load_status():
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return {"current_job": None, "jobs": {}}
        return json.loads(content)

def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_job_result(job_id: str, deals):
    path = os.path.join(JOBS_DIR, f"{job_id}.json")
    result = {
        "job_id": job_id,
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
        "total": len(deals),
        "deals": deals
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

# === Background Scraper ===
def run_scraper(job_id: str, limit: int):
    print(f"[JOB {job_id}] Starting...")
    status = load_status()
    status["current_job"] = job_id
    status["jobs"][job_id] = {"status": "running", "started_at": datetime.now().isoformat()}
    save_status(status)

    driver = None
    try:
        driver = init_driver()
        all_deals = []

        driver.get("https://www.kroger.com/weeklyad/weeklyad")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)

        for _ in range(5):
            close_popups(driver)
            time.sleep(0.5)

        enhanced_scroll_to_bottom(driver)
        cards = driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")
        print(f"[JOB {job_id}] Found {len(cards)} cards")

        processed = 0
        for idx in range(len(cards)):
            if processed >= limit:
                break
            try:
                card = driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")[idx]
                name = get_displayed_name(card)
                if not name or "Unknown" in name:
                    continue

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
                print(f"[JOB {job_id}] Card error: {e}")
                continue

        save_job_result(job_id, all_deals)

        status = load_status()
        status["current_job"] = None
        status["jobs"][job_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "total": len(all_deals)
        })
        save_status(status)
        print(f"[JOB {job_id}] COMPLETED! {len(all_deals)} items")

    except Exception as e:
        status = load_status()
        status["current_job"] = None
        status["jobs"][job_id]["status"] = "failed"
        status["jobs"][job_id]["error"] = str(e)
        save_status(status)
        print(f"[JOB {job_id}] FAILED: {e}")
    finally:
        if driver:
            driver.quit()

# === ENDPOINTS ===

@app.get("/scrape-kroger-deals")
def start_scrape(limit: int = 1000):
    status = load_status()

    if status["current_job"]:
        return {
            "job_id": status["current_job"],
            "status": "running",
            "message": "A job is already running. Check status below.",
            "check_url": f"/status/{status['current_job']}"
        }

    job_id = str(uuid.uuid4())
    threading.Thread(target=run_scraper, args=(job_id, limit), daemon=True).start()

    return {
        "job_id": job_id,
        "status": "started",
        "message": "Scraping started in background!",
        "check_url": f"/status/{job_id}"
    }

@app.get("/status/{job_id}")
def get_status(job_id: str):
    status = load_status()
    job = status["jobs"].get(job_id)

    if status["current_job"] == job_id:
        return {"job_id": job_id, "status": "running", "deals": []}

    if job and job["status"] == "completed":
        result_file = os.path.join(JOBS_DIR, f"{job_id}.json")
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                return json.load(f)

    if job:
        return {**job, "deals": []}

    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/")
def root():
    return {"message": "Kroger Async Scraper — Use /scrape-kroger-deals"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("test:app", host="0.0.0.0", port=8080, reload=False)