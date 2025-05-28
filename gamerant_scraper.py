import requests
from bs4 import BeautifulSoup
import telegram
from telegram import Bot
import asyncio
import logging
from urllib.parse import urljoin
from io import BytesIO
import html
import os
from datetime import datetime, date

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Telegram bot setup (use environment variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Example: '123456:ABC-DEF...'
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Example: '@YourChannel'
POST_WITHOUT_IMAGE = True
MAX_RETRIES = 3
RETRY_DELAY = 2
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", 5))
TODAY = date.today()
POSTED_FILE = "gamerant_posted.txt"

# Telegram bot instance
bot = Bot(token=BOT_TOKEN)

def load_posted_articles():
    posted = {}
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    date_str, title = line.strip().split("|", 1)
                    posted[title] = datetime.strptime(date_str, "%Y-%m-%d").date()
    return posted

def save_posted_article(title):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{TODAY}|{title}\n")

def is_duplicate(title, posted_articles):
    return title in posted_articles and posted_articles[title] == TODAY

def escape_html(text):
    return html.escape(text) if text else ""

def parse_article_date(article):
    try:
        date_elem = article.select_one("time, [class*='date']")
        if date_elem and date_elem.text:
            date_str = date_elem.text.strip()
            for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
    except Exception as e:
        logger.warning(f"Date parsing failed: {e}")
    return TODAY  # Fallback to today

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
            return
        except telegram.error.TimedOut:
            logger.warning(f"Timeout on attempt {attempt} for {title}. Retrying...")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
        except telegram.error.BadRequest as e:
            logger.error(f"BadRequest for {title}: {e}")
            return
        except Exception as e:
            logger.error(f"Error posting {title}: {e}")
            return
    logger.error(f"Failed to post {title} after {MAX_RETRIES} attempts")

async def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {"User-Agent": "Mozilla/5.0"}

    posted_articles = load_posted_articles()

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.select("div.display-card.article")[:MAX_ARTICLES]
        if not articles:
            logger.warning("No articles found. HTML saved to gamerant.html.")
            with open("gamerant.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            return

        for article in articles:
            article_date = parse_article_date(article)
            if article_date != TODAY:
                logger.info(f"Skipping old article ({article_date}): Not from today.")
                continue

            title_elem = article.select_one("h5, h3, [class*='title']")
            title = title_elem.text.strip() if title_elem else None
            if not title:
                logger.info("No title found; skipping article.")
                continue

            if is_duplicate(title, posted_articles):
                logger.info(f"Duplicate found: {title}")
                continue

            summary_elem = article.select_one("p.synopsis, p, [class*='excerpt']")
            summary = summary_elem.text.strip()[:150] + "..." if summary_elem else "No summary available."

            image_data = None
            image_elem = article.select_one("img[data-src], img[src]")
            image_url = None
            if image_elem:
                image_url = urljoin(url, image_elem.get("data-src") or image_elem.get("src"))

            if image_url:
                try:
                    img_res = requests.get(image_url, timeout=5)
                    img_res.raise_for_status()
                    image_data = BytesIO(img_res.content)
                except Exception as e:
                    logger.error(f"Image download failed for {title}: {e}")

            if image_data or POST_WITHOUT_IMAGE:
                await send_to_telegram(title, summary, image_data)

            save_posted_article(title)
            posted_articles[title] = TODAY

    except Exception as e:
        logger.error(f"Scraping failed: {e}")

async def main():
    await scrape_gamerant()

if __name__ == "__main__":
    asyncio.run(main())
