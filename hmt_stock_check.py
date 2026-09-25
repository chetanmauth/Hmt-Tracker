import os
import re
import sys
import time
import json
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hmtwatches.in"
FILTER_URL = f"{BASE_URL}/filter_products"
STATE_FILE = "previous_stock.json"

GENDER_TYPES = {"men": 1, "women": 2}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PRICE_RE = re.compile(r"RS\.\s*([\d,]+)")

def load_previous_stock():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_current_stock(stock_ids):
    with open(STATE_FILE, "w") as f:
        json.dump(list(stock_ids), f)

def fetch_page(gender_type: int, load_more_count: int) -> str:
    payload = {
        "load_more_count": load_more_count,
        "menu_val": "",
        "gender_type": gender_type,
    }
    req_headers = HEADERS.copy()
    referer_slug = "mens" if gender_type == 1 else "womens"
    req_headers["Referer"] = f"{BASE_URL}/{referer_slug}"

    resp = requests.post(FILTER_URL, data=payload, headers=req_headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        return ""
    return data.get("html", "")

def parse_cards(html: str):
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for item in soup.select("div.bc_p_item"):
        link_tag = item.select_one("a.bc_p_img")
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        
        if not url:
            continue

        name_anchor = item.select_one("a.bc_p_name")
        if name_anchor and name_anchor.has_attr("title"):
            name = name_anchor["title"].strip()
        else:
            name_tag = item.select_one("a.bc_p_name span")
            name = name_tag.get_text(strip=True) if name_tag else "Unknown"

        img_tag = item.select_one("a.bc_p_img img")
        image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None
        
        if image_url and not image_url.startswith("http"):
            image_url = f"{BASE_URL}{image_url}"

        detail = item.select_one("div.bc_p_detail")
        price_tag = detail.find("p", recursive=False) if detail else None
        price_text = price_tag.get_text(strip=True) if price_tag else ""
        price_match = PRICE_RE.search(price_text)
        price_val = price_match.group(1) if price_match else "N/A"

        product_id = f"{name}_{price_val}"

        product = {
            "id": product_id,
            "name": name,
            "price": price_val if price_val != "N/A" else None,
            "image": image_url,
            "url": url,
            "in_stock": item.select_one("div.outofstock") is None,
        }
        products.append(product)
    return products

def scan_gender(gender_type: int, max_pages: int = 30, pause_sec: float = 1.0):
    all_products = {}
    for page in range(1, max_pages + 1):
        html = fetch_page(gender_type, page)
        if not html.strip():
            break

        cards = parse_cards(html)
        if not cards:
            break

        new_count = 0
        for p in cards:
            if p["id"] not in all_products:
                all_products[p["id"]] = p
                new_count += 1

        if new_count == 0:
            break
        time.sleep(pause_sec)
    return list(all_products.values())

def scan_all():
    in_stock = {}
    for label, gender_type in GENDER_TYPES.items():
        products = scan_gender(gender_type)
        for p in products:
            if p["in_stock"]:
                if p["id"] in in_stock:
                    in_stock[p["id"]]["category"] += f" & {label}"
                else:
                    p["category"] = label
                    in_stock[p["id"]] = p
    return list(in_stock.values())

def send_telegram_alert(watch):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    price = f"₹{watch['price']}" if watch['price'] else "Price N/A"
    caption = (
        f"🚨 <b>HMT IN STOCK</b> 🚨\n\n"
        f"⌚️ <b>{watch['name']}</b>\n"
        f"🏷 <b>Category:</b> {watch['category'].title()}\n"
        f"💰 <b>Price:</b> {price}\n\n"
        f"🛒 <a href='{watch['url']}'><b>BUY NOW</b></a>"
    )

    if watch["image"]:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": watch["image"], "caption": caption, "parse_mode": "HTML"}
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": caption, "parse_mode": "HTML", "disable_web_page_preview": False}
        
    requests.post(url, data=payload, timeout=20)

def main():
    current_in_stock = scan_all()
    previous_stock_ids = load_previous_stock()
    new_watches = []
    current_stock_ids = set()

    for p in current_in_stock:
        current_stock_ids.add(p["id"])
        if p["id"] not in previous_stock_ids:
            new_watches.append(p)
            
    save_current_stock(current_stock_ids)

    if not new_watches:
        return

    summary_text = f"🆕 <b>{len(new_watches)} NEW HMT watch(es) in stock!</b>"
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": summary_text, "parse_mode": "HTML"},
            timeout=20
        )

    for watch in new_watches:
        send_telegram_alert(watch)
        time.sleep(1)

if __name__ == "__main__":
    main()
