"""
HMT Watches — In-Stock Checker + Telegram Alert
------------------------------------------------
Scans hmtwatches.in (Men + Women) via the site's internal
`filter_products` endpoint and sends the current in-stock list
to a Telegram chat.

Run manually:
    python hmt_stock_check.py

Env vars required (set as GitHub Actions secrets, or a local .env):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hmtwatches.in"
FILTER_URL = f"{BASE_URL}/filter_products"

# gender_type=1 -> Men, gender_type=2 -> Women (confirmed from live requests)
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


def fetch_page(gender_type: int, load_more_count: int) -> str:
    """POST to filter_products and return the raw HTML fragment."""
    payload = {
        "load_more_count": load_more_count,
        "menu_val": "",
        "gender_type": gender_type,
    }
    
    # Dynamically assign the correct referer
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
    """Extract structured product info from a raw HTML fragment using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for item in soup.select("div.bc_p_item"):
        link_tag = item.select_one("a.bc_p_img")
        url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        
        # If there's no URL, the card is malformed
        if not url:
            continue

        # Extract numeric ID from the URL (e.g., ?id=123), or fallback to using the URL string as the ID
        id_match = re.search(r'id=(\d+)', url)
        product_id = id_match.group(1) if id_match else url

        img_tag = item.select_one("a.bc_p_img img")
        name_tag = item.select_one("a.bc_p_name span")
        detail = item.select_one("div.bc_p_detail")
        price_tag = detail.find("p", recursive=False) if detail else None

        name = name_tag.get_text(strip=True) if name_tag else "Unknown"
        price_text = price_tag.get_text(strip=True) if price_tag else ""
        price_match = PRICE_RE.search(price_text)

        product = {
            "id": product_id,
            "name": name,
            "price": price_match.group(1) if price_match else None,
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

        # If this page gave us nothing new, we've reached the end
        if new_count == 0:
            break

        time.sleep(pause_sec)  # be polite to the server

    return list(all_products.values())


def scan_all():
    """Scan both Men and Women categories, return combined in-stock list."""
    in_stock = []
    for label, gender_type in GENDER_TYPES.items():
        products = scan_gender(gender_type)
        for p in products:
            if p["in_stock"]:
                p["category"] = label
                in_stock.append(p)
    return in_stock


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
    if not products:
        return "😴 No HMT watches currently in stock (Men or Women)."

    lines = [f"✅ <b>{len(products)} HMT watch(es) in stock</b>\n"]
    for p in products:
        price = f"₹{p['price']}" if p["price"] else "Price N/A"
        lines.append(
            f"• <b>{p['name']}</b> ({p['category'].title()}) — {price}\n"
            f"  {p['url']}"
        )
    return "\n".join(lines)


def main():
    print("Scanning HMT Watches (Men + Women)...")
    in_stock = scan_all()
    print(f"Found {len(in_stock)} in-stock item(s).")

    message = format_message(in_stock)

    # Telegram messages have a ~4096 char limit — chunk if needed
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
