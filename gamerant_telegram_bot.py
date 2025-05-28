import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import logging
from urllib.parse import urljoin
from io import BytesIO
import time
import html
import os
from datetime import datetime, date

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Telegram bot setup (use environment variables for GitHub Secrets)
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set in GitHub Secrets
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Set in GitHub Secrets
POST_WITHOUT_IMAGE = True  # Post text-only if no image
MAX_RETRIES = 3  # Retry attempts for Telegram API
RETRY_DELAY = 2  # Seconds between retries
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", 5))  # Configurable via environment variable, default 5
TODAY = date.today()  # May 28, 2025 (updates to May 29 at midnight)
POSTED_FILE = "posted_articles.txt"  # File to store posted article titles

# Initialize Telegram bot
bot = telegram.Bot(token=BOT_TOKEN)

def load_posted_articles():
    """Load previously posted article titles and their dates."""
    posted = {}
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            for line in f:
                if line.strip():
                    date_str, title = line.strip().split("|", 1)
                    posted_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    posted[title] = posted_date
    return posted

def save_posted_article(title):
    """Save a posted article title with the current date."""
    with open(POSTED_FILE, "a") as f:
        f.write(f"{TODAY}|{title}\n")

def is_duplicate(title, posted_articles):
    """Check if the article has already been posted today."""
    if title in posted_articles:
        posted_date = posted_articles[title]
        if posted_date == TODAY:
            return True
    return False

def escape_html(text):
    """Escape HTML special characters to prevent formatting issues."""
    if not text:
        return text
    return html.escape(text)

def parse_article_date(article):
    """Extract and parse the article's publication date."""
    try:
        date_elem = article.select_one("time, [class*='date']")
        if date_elem and date_elem.text:
            date_str = date_elem.text.strip()
            try:
                article_date = datetime.strptime(date_str, "%B %d, %Y").date()
            except ValueError:
                article_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            return article_date
    except Exception as e:
        logger.error(f"Error parsing date for article: {e}")
    return None

async def send_to_telegram(title, summary, image_data=None):
    # Escape HTML characters
    title = escape_html(title)
    summary = escape_html(summary)
    
    # Format message using HTML
    message = f"<b>{title}</b> ⚡\n\n<i>{summary}</i>\n\n🍁 | @GamediaNews_acn"
    
    # Log the formatted message for debugging
    logger.info(f"Formatted message: {message}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if image_data:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_data,
                    caption=message,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message,
                    parse_mode="HTML"
                )
            logger.info(f"Posted: {title}")
            return
        except telegram.error.TimedOut:
            logger.warning(f"Timeout on attempt {attempt} for {title}. Retrying...")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            continue
        except telegram.error.BadRequest as e:
            logger.error(f"BadRequest for {title}: {e}")
            return
        except Exception as e:
            logger.error(f"Error posting {title}: {e}")
            return
    
    logger.error(f"Failed to post {title} after {MAX_RETRIES} attempts")

async def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Load previously posted articles
    posted_articles = load_posted_articles()
    
    try:
        # Fetch webpage
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find article elements
        articles = soup.select("div.display-card.article")[:MAX_ARTICLES]
        if not articles:
            logger.warning("No articles found with 'div.display-card.article'. Check HTML in gamerant.html.")
            with open("gamerant.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            return
        
        for article in articles:
            # Extract publication date
            article_date = parse_article_date(article)
            if not article_date or article_date != TODAY:
                logger.info(f"Skipping article dated {article_date}, not from today ({TODAY})")
                continue
            
            # Extract title
            title_elem = article.select_one("h5, h3, [class*='title']")
            title = title_elem.text.strip() if title_elem else None
            if not title or title == "No title":
                logger.info("Skipping article with no valid title")
                continue
            
            # Check for duplicates
            if is_duplicate(title, posted_articles):
                logger.info(f"Skipping duplicate article: {title}")
                continue
            
            # Extract short summary (150 characters)
            summary_elem = article.select_one("p.synopsis, p, [class*='excerpt']")
            summary = summary_elem.text.strip()[:150] + "..." if summary_elem else "No summary available"
            
            # Extract and download image
            image_data = None
            image_elem = article.select_one("img[data-src], img[src]")
            if image_elem and "data-src" in image_elem.attrs:
                image_url = urljoin(url, image_elem["data-src"])
            elif image_elem and "src" in image_elem.attrs:
                image_url = urljoin(url, image_elem["src"])
            else:
                image_url = None
            
            if image_url:
                try:
                    image_response = requests.get(image_url, timeout=5)
                    image_response.raise_for_status()
                    image_data = BytesIO(image_response.content)
                except Exception as e:
                    logger.error(f"Error downloading image for {title}: {e}")
            
            # Send to Telegram
            await send_to_telegram(title, summary, image_data if image_data or POST_WITHOUT_IMAGE else None)
            
            # Save the posted article title
            save_posted_article(title)
            posted_articles[title] = TODAY
    
    except Exception as e:
        logger.error(f"Error scraping GameRant: {e}")

async def main():
    await scrape_gamerant()

if __name__ == "__main__":
    asyncio.run(main())
