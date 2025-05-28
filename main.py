import requests
from bs4 import BeautifulSoup
import telegram
import logging
from urllib.parse import urljoin
from io import BytesIO
import html
import datetime
import json
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = telegram.Bot(token=BOT_TOKEN)

today = datetime.date.today().isoformat()
CACHE_FILE = "posted.json"
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        posted_cache = json.load(f)
else:
    posted_cache = {}

if today not in posted_cache:
    posted_cache[today] = []

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(posted_cache, f, indent=2)

def escape_html(text):
    return html.escape(text) if text else text

def send_to_telegram(title, summary, image_data=None):
    title = escape_html(title)
    summary = escape_html(summary)
    message = f"<b>{title}</b> ⚡\n\n<i>{summary}</i>\n\n🍁 | @GamediaNews_acn"
    try:
        if image_data:
            bot.send_photo(chat_id=CHANNEL_ID, photo=image_data, caption=message, parse_mode="HTML")
        else:
            bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
        logger.info(f"Posted: {title}")
        return True
    except Exception as e:
        logger.error(f"Error posting {title}: {e}")
        return False

def safe_request(url, headers, retries=3):
    for i in range(retries):
        try:
            return requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error (try {i+1}): {e}")
            time.sleep(2)
    raise Exception("Failed after retries")

def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
    }

    try:
        response = safe_request(url, headers)
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("div.display-card.article")[:15]

        posted_today = posted_cache[today]
        posted_count = 0

        for article in articles:
            title_elem = article.select_one("h5, h3, [class*='title']")
            title = title_elem.text.strip() if title_elem else None
            if not title or title in posted_today:
                continue

            summary_elem = article.select_one("p.synopsis, p, [class*='excerpt']")
            summary = summary_elem.text.strip()[:150] + "..." if summary_elem else "No summary available"

            image_data = None
            image_elem = article.select_one("img[data-src], img[src]")
            if image_elem:
                image_url = image_elem.get("data-src") or image_elem.get("src")
                try:
                    image_response = requests.get(urljoin(url, image_url), timeout=5)
                    image_response.raise_for_status()
                    image_data = BytesIO(image_response.content)
                except Exception as e:
                    logger.warning(f"Image download failed: {e}")

            if send_to_telegram(title, summary, image_data):
                posted_today.append(title)
                posted_count += 1
                save_cache()

            if posted_count >= 7:
                break

            time.sleep(1)

        if posted_count == 0:
            logger.info("No new articles to post.")

    except Exception as e:
        logger.error(f"Scrape error: {e}")

if __name__ == "__main__":
    scrape_gamerant()
