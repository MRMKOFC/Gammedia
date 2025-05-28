import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import logging
from urllib.parse import urljoin
from io import BytesIO
import html
import datetime
import json
import os
import time

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Secrets (from GitHub Actions env)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Settings
POST_WITHOUT_IMAGE = True
MAX_RETRIES = 3
RETRY_DELAY = 2
MIN_POSTS = 7

bot = telegram.Bot(token=BOT_TOKEN)

# Load posted articles
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

async def send_to_telegram(title, summary, image_data=None):
    title = escape_html(title)
    summary = escape_html(summary)
    message = f"<b>{title}</b> ⚡\n\n<i>{summary}</i>\n\n🍁 | @GamediaNews_acn"
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if image_data:
                await bot.send_photo(chat_id=CHANNEL_ID, photo=image_data, caption=message, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
            logger.info(f"Posted: {title}")
            return True
        except telegram.error.TimedOut:
            logger.warning(f"Timeout (try {attempt}) for {title}")
            await asyncio.sleep(RETRY_DELAY)
        except telegram.error.BadRequest as e:
            logger.error(f"BadRequest for {title}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error posting {title}: {e}")
            return False
    logger.error(f"Failed to post: {title}")
    return False

def safe_request(url, headers, retries=3):
    for i in range(retries):
        try:
            return requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error (try {i+1}): {e}")
            time.sleep(2)
    raise Exception("Failed after retries")

async def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
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
                if image_url:
                    try:
                        image_response = requests.get(urljoin(url, image_url), timeout=5)
                        image_response.raise_for_status()
                        image_data = BytesIO(image_response.content)
                    except Exception as e:
                        logger.error(f"Image download failed for {title}: {e}")

            success = await send_to_telegram(title, summary, image_data if image_data or POST_WITHOUT_IMAGE else None)
            if success:
                posted_today.append(title)
                posted_count += 1
                save_cache()

            await asyncio.sleep(1)

            if posted_count >= MIN_POSTS:
                break

        if posted_count == 0:
            logger.info("No new articles to post.")

    except Exception as e:
        logger.error(f"Scrape error: {e}")

async def main():
    await scrape_gamerant()

if __name__ == "__main__":
    asyncio.run(main())
