from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent


# ================= SELENIUM SETUP =================
def init_driver():
    opts = Options()
    # opts.add_argument("--headless=new")  # Uncomment for production
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1920,1080")

    ua = UserAgent(browsers=['chrome'])
    opts.add_argument(f"--user-agent={ua.random}")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=opts
    )
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
        """
    })
    return driver