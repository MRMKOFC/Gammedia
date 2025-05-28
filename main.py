import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import logging
from urllib.parse import urljoin
from io import BytesIO
import html
import os

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Telegram setup from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
POST_WITHOUT_IMAGE = True
MAX_RETRIES = 3
RETRY_DELAY = 2

bot = telegram.Bot(token=BOT_TOKEN)

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
            return
        except telegram.error.TimedOut:
            logger.warning(f"Timeout on attempt {attempt} for {title}")
            await asyncio.sleep(RETRY_DELAY)
        except telegram.error.BadRequest as e:
            logger.error(f"BadRequest for {title}: {e}")
            return
        except Exception as e:
            logger.error(f"Error posting {title}: {e}")
            return

    logger.error(f"Failed to post {title} after retries")

def is_already_posted(title):
    if not os.path.exists("posted_titles.txt"):
        return False
    with open("posted_titles.txt", "r", encoding="utf-8") as f:
        return title.strip() in [line.strip() for line in f.readlines()]

def mark_as_posted(title):
    with open("posted_titles.txt", "a", encoding="utf-8") as f:
        f.write(f"{title.strip()}\n")

async def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        articles = soup.select("div.display-card.article")[:10]
        if not articles:
            logger.warning("No articles found")
            return

        for article in articles:
            title_elem = article.select_one("h5, h3, [class*='title']")
            title = title_elem.text.strip() if title_elem else None

            if not title or is_already_posted(title):
                continue

            summary_elem = article.select_one("p.synopsis, p, [class*='excerpt']")
            summary = summary_elem.text.strip()[:150] + "..." if summary_elem else "No summary available"

            image_data = None
            image_elem = article.select_one("img[data-src], img[src]")
            if image_elem:
                image_url = image_elem.get("data-src") or image_elem.get("src")
                image_url = urljoin(url, image_url)
                try:
                    img_response = requests.get(image_url, timeout=5)
                    img_response.raise_for_status()
                    image_data = BytesIO(img_response.content)
                except Exception as e:
                    logger.error(f"Image error for {title}: {e}")

            await send_to_telegram(title, summary, image_data if image_data or POST_WITHOUT_IMAGE else None)
            mark_as_posted(title)

    except Exception as e:
        logger.error(f"Scrape error: {e}")

async def main():
    await scrape_gamerant()

if __name__ == "__main__":
    asyncio.run(main())
