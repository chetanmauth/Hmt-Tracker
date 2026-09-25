"""
HMT Watches — In-Stock Checker + Telegram Alert
------------------------------------------------
Scans hmtwatches.in (Men + Women) via the site's internal
`filter_products` endpoint and sends the current in-stock list
to a Telegram chat. 

UPDATED: 
- Deduplicates watches that appear in both Men's and Women's sections.
- Remembers previously alerted watches using a local JSON file to prevent spam looping.
"""

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

# gender_type=1 -> Men, gender_type=2 -> Women
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
    """Load previously seen watch IDs to prevent duplicate alerts."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_current_stock(stock_ids):
    """Save currently in-stock watch IDs for the next run."""
    with open(STATE_FILE, "w") as f:
        json.dump(list(stock_ids), f)


def fetch_page(gender_type: int, load_more_count: int) -> str:
    """POST to filter_products and return the raw HTML fragment."""
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
    """Extract structured product info from a raw HTML fragment."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for item in soup.select("div.bc_p_item"):
        link_tag = item.select_one("a.bc_p_img")
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        
        if not url:
            continue

        img_tag = item.select_one("a.bc_p_img img")
        name_tag = item.select_one("a.bc_p_name span")
        detail = item.select_one("div.bc_p_detail")
        price_tag = detail.find("p", recursive=False) if detail else None

        name = name_tag.get_text(strip=True) if name_tag else "Unknown"
        price_text = price_tag.get_text(strip=True) if price_tag else ""
        price_match = PRICE_RE.search(price_text)
        price_val = price_match.group(1) if price_match else "N/A"

        # Match duplicates by combining Name and Price
        product_id = f"{name}_{price_val}"

        product = {
            "id": product_id,
            "name": name,
            "price": price_val if price_val != "N/A" else None,
            "image": img_tag["src"] if img_tag and img_tag.has_attr("src") else None,
            "url": url,
            "in_stock": item.select_one("div.outofstock") is None,
        }
        products.append(product)

    return products


def scan_gender(gender_type: int, max_pages: int = 30, pause_sec: float = 1.0):
    """Page through filter_products until no new products are returned."""
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
    """Scan both categories and deduplicate cross-category overlap."""
    in_stock = {}
    for label, gender_type in GENDER_TYPES.items():
        products = scan_gender(gender_type)
        for p in products:
            if p["in_stock"]:
                # If watch is already found in another category, just append the label
                if p["id"] in in_stock:
                    in_stock[p["id"]]["category"] += f" & {label}"
                else:
                    p["category"] = label
                    in_stock[p["id"]] = p
    return list(in_stock.values())


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing — printing instead:\n")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    if not resp.ok:
        print(f"Telegram send failed: {resp.status_code} {resp.text}", file=sys.stderr)


def format_message(products):
    lines = [f"🆕 <b>{len(products)} NEW HMT watch(es) in stock!</b>\n"]
    for p in products:
        price = f"₹{p['price']}" if p["price"] else "Price N/A"
        lines.append(
            f"• <b>{p['name']}</b> ({p['category'].title()}) — {price}\n"
            f"  {p['url']}"
        )
    return "\n".join(lines)


def main():
    print("Scanning HMT Watches (Men + Women)...")
    current_in_stock = scan_all()
    print(f"Found {len(current_in_stock)} total in-stock item(s) on the website.")

    # 1. Load what we already notified you about last time
    previous_stock_ids = load_previous_stock()
    
    # 2. Filter out watches we've already sent a message for
    new_watches = []
    current_stock_ids = set()

    for p in current_in_stock:
        current_stock_ids.add(p["id"])
        if p["id"] not in previous_stock_ids:
            new_watches.append(p)
            
    # 3. Save the current state for the next run so it doesn't loop
    save_current_stock(current_stock_ids)

    if not new_watches:
        print("No NEW watches found since last run. Skipping Telegram alert.")
        return

    message = format_message(new_watches)

    MAX_LEN = 3800
    if len(message) <= MAX_LEN:
        send_telegram_message(message)
    else:
        chunk = ""
        for line in message.split("\n"):
            if len(chunk) + len(line) + 1 > MAX_LEN:
                send_telegram_message(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk.strip():
            send_telegram_message(chunk)


if __name__ == "__main__":
    main()
