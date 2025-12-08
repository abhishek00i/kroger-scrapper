from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any

# ================= UNIVERSAL PARSING (Both Modal Types) =================
def parse_kroger_modal(html: str, displayed_name: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    source_url = "https://www.kroger.com/pr/weekly-digital-deals"
    offer_event = "Weekly Digital Deals"
    offer_sale = "Digital coupon offer"

    # Detect modal type
    is_coupon_modal = bool(soup.find("button", string=re.compile("Sign In To Clip", re.I))) or "CouponModal-contentWrapper" in html

    competitor_price = "N/A"
    original_price_main = "N/A"

    if is_coupon_modal:
        # --- Coupon Modal (Sign In To Clip) ---
        short_desc = soup.find("h2", {"data-testid": "CouponDetails-shortDescription"})
        if short_desc:
            text = short_desc.get_text(strip=True)
            price_match = re.search(r'\$\d+\.?\d*(?:/lb|/ea)?', text)
            competitor_price = price_match.group() if price_match else text.split("$")[-1] if "$" in text else "N/A"

        # Original price in coupon modal
        orig = soup.find("s", class_="kds-Price-original")
        if orig:
            original_price_main = orig.get_text(strip=True)
    else:
        # --- Regular Deal Modal ---
        price_tag = soup.find("span", class_="SWA-ModalPriceText")
        if price_tag:
            competitor_price = price_tag.get_text(strip=True)
        strikethrough = soup.find("del") or soup.find("span", string=re.compile("strikethrough", re.I))
        if strikethrough:
            original_price_main = strikethrough.get_text(strip=True)

    # === Qualifying Products (Works for BOTH modal types) ===
    qualifying_section = soup.find("h2", string="Qualifying Products")
    qualifying_cards = []

    if qualifying_section:
        # Try list-style (coupon modal)
        product_list = qualifying_section.find_next("ul", class_="ProductListView")
        if product_list:
            items = product_list.find_all("li")
            for item in items:
                card_div = item.find("div", class_=re.compile("flex flex-col border-solid"))
                if card_div:
                    qualifying_cards.append(card_div)

        # Try grid-style (regular modal)
        if not qualifying_cards:
            grid = qualifying_section.find_next("div", class_=re.compile("ProductGridContainer|AutoGrid|CouponQualifyingProductGridContainer"))
            if grid:
                qualifying_cards = grid.find_all("div", class_=re.compile("MiniProductCard-card-container|flex flex-col border-solid"))

    all_products = []

    # Main product
    all_products.append({
        "competitor_product": displayed_name.strip(),
        "competitor_price": competitor_price,
        "original_price": original_price_main,
        "offer_description": "Weekly Digital Deal",
        "offer_sale": offer_sale,
        "source_URL": source_url,
        "competitor_product_size": "N/A",
        "offer_event": offer_event,
        "Compatitor_name": "Kroger",
        "Qualifying Products": False
    })

    # Qualifying products
    for card in qualifying_cards:
        name_tag = card.find("span", {"data-testid": "cart-page-item-description"}) or \
                   card.find("span", class_=re.compile("kds-Text--m|kds-Text--bold"))
        product_name = name_tag.get_text(strip=True) if name_tag else "Unknown Product"

        # Sale price
        promo_price = card.find("mark", class_="kds-Price-promotional")
        sale_price = promo_price.get_text(strip=True) if promo_price else "N/A"
        if sale_price == "N/A":
            data_price = card.find("data", class_="kds-Price")
            if data_price:
                sale_price = data_price.get_text(strip=True)

        # Original price
        orig_price = ""
        orig_tag = card.find("s", class_="kds-Price-original") or card.find("del")
        if orig_tag:
            orig_price = orig_tag.get_text(strip=True)

        # Size
        size_tag = card.find("span", {"data-testid": "product-item-sizing"})
        raw_size = size_tag.get_text(strip=True) if size_tag else ""
        if not raw_size or raw_size.startswith("$"):
            match = re.search(r'(\d[\d\.]*\s*(oz|lb|g|ml|L|count|pack|each|ct)|Each|Half Gallon)', product_name, re.I)
            competitor_product_size = match.group(1) if match else "N/A"
        else:
            competitor_product_size = raw_size

        all_products.append({
            "competitor_product": product_name,
            "competitor_price": sale_price,
            "original_price": orig_price,
            "offer_description": "Weekly Digital Deal",
            "offer_sale": offer_sale,
            "source_URL": source_url,
            "competitor_product_size": competitor_product_size,
            "offer_event": offer_event,
            "Compatitor_name": "Kroger",
            "Qualifying Products": True
        })

    return all_products
