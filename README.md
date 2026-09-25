# HMT Watches — In-Stock Telegram Alert

Scans hmtwatches.in (Men + Women) and sends individual photo alerts for newly stocked items to a Telegram chat.

## How it works

- Calls the site's own `filter_products` endpoint (the same one the "Load More" button on hmtwatches.in uses) directly via POST — no browser automation needed.
- Pages through results until no new products appear.
- A product is considered **in stock** if its card does NOT contain a `class="outofstock"` block (i.e. no "Coming Soon" label).
- **Smart Tracking & Memory:** Tracks previously seen stock using a `previous_stock.json` file. It only alerts you about *newly added* watches, preventing duplicate spam loops on every run.
- **Deduplication:** Uses the watch's Name and Price to identify duplicates, seamlessly merging identical watches listed across multiple categories.
- **Image Alerts:** Sends individual Telegram photo cards containing the watch image, category, price, and a direct checkout link instead of a single giant text list.

## 1. Create your Telegram bot

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the prompts. You'll get a **bot token** like `123456:ABC-DEF...`.
2. Message your new bot anything (e.g. "hi") so it has a chat to talk to.
3. Get your **chat ID**: open this URL in a browser (replace `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Look for `"chat":{"id": ...}` in the response — that number is your `TELEGRAM_CHAT_ID`.

## 2. Run it locally (optional, to test)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="12345"
python hmt_stock_check.py
```

If the env vars aren't set, it just prints the message to your terminal instead of sending — handy for testing the scraper alone.

## 3. Deploy for free with GitHub Actions (recommended)

1. Create a new **public** GitHub repo and push this folder to it (public repos get unlimited free Actions minutes).
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**. Add two secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Ensure your workflow file (`.github/workflows/stock_check.yml`) includes `permissions: contents: write` so the bot can commit the `previous_stock.json` state file back to the repository.
4. `.github/workflows/stock_check.yml` is already set up to run **every hour** automatically.
5. To trigger it manually right away: go to the **Actions** tab → "HMT Stock Check" → **Run workflow**.

## Changing the schedule

Edit the `cron` line in `.github/workflows/stock_check.yml`:

| Frequency         | Cron expression   |
|--------------------|-------------------|
| Every hour          | `0 * * * *`       |
| Every 30 minutes     | `*/30 * * * *`     |
| Every 15 minutes     | `*/15 * * * *`     |
| Every 6 hours        | `0 */6 * * *`      |

(GitHub Actions cron times are UTC and can occasionally run a few minutes late during high load — fine for this use case.)

## Notes / limitations

- Only **quantity is not available** anywhere on the site (only a boolean in-stock/out-of-stock signal) — this was confirmed by inspecting the actual API response, so the alert can't include stock count.
- Product page links use short-lived/session-bound encrypted IDs. The script bypasses this limitation by identifying and remembering watches using a combination of their Name and Price.
- Currently covers `gender_type=1` (Men) and `gender_type=2` (Women). If HMT adds a "Pair"/"Unisex" gender_type value later, add it to the `GENDER_TYPES` dict in `hmt_stock_check.py`.
