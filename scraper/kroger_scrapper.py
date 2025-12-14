from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from database.models import Database, JobManager, DealManager

class KrogerScraper:
    def __init__(self, job_id: str, limit: int = 100):
        self.job_id = job_id
        self.limit = limit
        self.driver = None
        self.db = Database()
        self.job_manager = JobManager(self.db)
        self.deal_manager = DealManager(self.db)
        self.total_cards = 0
        self.successful_scrapes = 0
        self.failed_scrapes = 0

    def init_driver(self):
        """Initialize Chrome WebDriver with basic settings"""
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--accept-lang=en-US,en')
        options.add_argument('--accept=text/html,application/xhtml+xml,application/xml')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

    def close_popups(self):
        """Close any popups that appear"""
        try:
            # Close cookie notice if present
            cookie_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[data-testid='CloseButton']")
            for button in cookie_buttons:
                if button.is_displayed():
                    button.click()
                    time.sleep(1)
                    
            # Close modal if present
            modal_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close']")
            for button in modal_buttons:
                if button.is_displayed():
                    button.click()
                    time.sleep(1)
        except:
            pass

    def scroll_to_bottom(self):
        """Scroll to the bottom of the page gradually"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down gradually
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            
            # Calculate new scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Break if we've reached the bottom
            if new_height == last_height:
                break
                
            last_height = new_height

    def get_modal_html(self) -> str:
        """Get the HTML content of the product modal"""
        try:
            modal = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']"))
            )
            return modal.get_attribute('outerHTML')
        except TimeoutException:
            return ""

    def get_displayed_name(self, card) -> str:
        """Get the displayed name of a product from its card"""
        try:
            return card.find_element(By.TAG_NAME, "img").get_attribute("alt").strip()
        except:
            return card.text.strip().split("\n")[0].strip() or "Unknown Product"

    def parse_deal_details(self, html: str, name: str) -> List[Dict]:
        """Parse deal details from modal HTML"""
        soup = BeautifulSoup(html, 'lxml')
        products = []
        
        try:
            # Extract basic product info
            product = {
                "name": name,
                "price": "",
                "original_price": "",
                "discount": "",
                "description": "",
                "details": {}
            }
            
            # Try to find price information
            price_elem = soup.select_one(".kds-Price")
            if price_elem:
                product["price"] = price_elem.text.strip()
            
            # Try to find original price
            orig_price_elem = soup.select_one(".kds-Price--was")
            if orig_price_elem:
                product["original_price"] = orig_price_elem.text.strip()
            
            # Try to find discount
            discount_elem = soup.select_one(".kds-Price--savings")
            if discount_elem:
                product["discount"] = discount_elem.text.strip()
            
            # Try to find description
            desc_elem = soup.select_one(".kds-Text--l")
            if desc_elem:
                product["description"] = desc_elem.text.strip()
            
            # Add any additional details found
            details = {}
            detail_elems = soup.select(".kds-Text--s")
            for elem in detail_elems:
                text = elem.text.strip()
                if ":" in text:
                    key, value = text.split(":", 1)
                    details[key.strip()] = value.strip()
            
            product["details"] = details
            products.append(product)
            
        except Exception as e:
            print(f"Error parsing deal: {str(e)}")
            
        return products

    def scrape(self):
        """Main scraping method"""
        try:
            self.init_driver()
            self.job_manager.create_job(self.job_id)
            all_deals = []

            # Load homepage first
            print(f"[JOB {self.job_id}] Loading Kroger homepage...")
            self.driver.get("https://www.kroger.com")
            WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)

            # Navigate to weekly ad
            print(f"[JOB {self.job_id}] Navigating to weekly ad...")
            self.driver.get("https://www.kroger.com/weeklyad/weeklyad")
            WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)

            # Handle popups
            for _ in range(3):
                self.close_popups()
                time.sleep(1)

            # Scroll and get cards
            self.scroll_to_bottom()
            time.sleep(2)

            cards = self.driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")
            self.total_cards = len(cards)
            print(f"[JOB {self.job_id}] Found {self.total_cards} cards")

            processed = 0
            for idx in range(len(cards)):
                if processed >= self.limit:
                    break
                try:
                    time.sleep(1)
                    card = self.driver.find_elements(By.CSS_SELECTOR, "div.kds-Card.SWA-Omni")[idx]
                    
                    # Scroll card into view
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(1)
                    
                    name = self.get_displayed_name(card)
                    if not name or "Unknown" in name:
                        self.failed_scrapes += 1
                        continue

                    clicked = False
                    for sel in ["button[data-testid='SWA-Omni-ImageContainer']", "button[role='button'] img"]:
                        try:
                            btn = WebDriverWait(card, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                            self.driver.execute_script("arguments[0].click();", btn)
                            clicked = True
                            break
                        except:
                            continue
                    if not clicked:
                        self.failed_scrapes += 1
                        continue

                    time.sleep(1)
                    modal_html = self.get_modal_html()
                    products = self.parse_deal_details(modal_html, name)
                    
                    if products:
                        all_deals.extend(products)
                        self.successful_scrapes += 1
                    else:
                        self.failed_scrapes += 1
                    
                    processed += 1
                    
                    self.close_popups()
                    time.sleep(1)

                except Exception as e:
                    print(f"[JOB {self.job_id}] Card error: {e}")
                    self.failed_scrapes += 1
                    continue

            # Save results and update statistics
            self.deal_manager.save_deals(self.job_id, all_deals)
            self.job_manager.update_job_stats(
                self.job_id, 
                self.total_cards,
                self.successful_scrapes,
                self.failed_scrapes
            )
            self.job_manager.update_job_status(self.job_id, "completed")
            
            print(f"[JOB {self.job_id}] COMPLETED! {len(all_deals)} items")

        except Exception as e:
            self.job_manager.update_job_status(self.job_id, "failed", str(e))
            print(f"[JOB {self.job_id}] FAILED: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
