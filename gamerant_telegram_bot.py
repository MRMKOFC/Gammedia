import os
import requests
import time
from bs4 import BeautifulSoup
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
GAMERANT_URL = "https://gamerant.com/gaming/"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_latest_article():
    """Fetch the latest article from GameRant."""
    try:
        response = requests.get(GAMERANT_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the first/latest article
        articles = soup.select('article.browse-clip')
        if not articles:
            logger.error("No articles found on the page")
            return None
        
        latest_article = articles[0]
        
        # Extract title
        title_element = latest_article.select_one('h5.title')
        if not title_element:
            logger.error("Could not find title element")
            return None
        
        title = title_element.text.strip()
        
        # Extract URL
        link_element = latest_article.find('a', href=True)
        if not link_element:
            logger.error("Could not find link element")
            return None
        
        article_url = link_element['href']
        if not article_url.startswith('http'):
            article_url = f"https://gamerant.com{article_url}"
        
        # Get full article to extract summary and main image
        article_response = requests.get(article_url, timeout=30)
        article_response.raise_for_status()
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        
        # Extract summary
        summary_element = article_soup.select_one('h2.subtitle')
        if not summary_element:
            # Fallback to first paragraph if subtitle is not available
            summary_element = article_soup.select_one('div.article-body > p')
        
        summary = summary_element.text.strip() if summary_element else "No summary available"
        
        # Extract main image
        img_element = article_soup.select_one('img.header-img')
        if not img_element:
            # Fallback to any image in the article
            img_element = article_soup.select_one('div.article-img-wrapper img')
        
        image_url = img_element['src'] if img_element and 'src' in img_element.attrs else None
        
        return {
            'title': title,
            'summary': summary,
            'url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.error(f"Error fetching article: {e}")
        return None

def send_telegram_message(article):
    """Send article information to Telegram channel."""
    if not article:
        logger.error("No article data to send")
        return False
    
    # Format the message according to requirements
    message = f"⚡ *{article['title']}*\n\n" \
              f"_{article['summary']}_\n\n" \
              f"🍁 | @GamediaNews_acn"
    
    # If there's an image, send photo with caption
    if article['image_url']:
        send_url = f"{TELEGRAM_API_URL}/sendPhoto"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'photo': article['image_url'],
            'caption': message,
            'parse_mode': 'Markdown'
        }
    else:
        # Otherwise just send text message
        send_url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
    
    try:
        response = requests.post(send_url, data=payload, timeout=30)
        response.raise_for_status()
        logger.info("Message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def store_last_article_url(url):
    """Store the URL of the last posted article to avoid duplicates."""
    with open('last_article.txt', 'w') as f:
        f.write(url)

def get_last_article_url():
    """Get the URL of the last posted article."""
    try:
        with open('last_article.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def main():
    """Main function to run the bot."""
    logger.info("Starting GameRant News Bot")
    
    # Check if Telegram credentials are set
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        logger.error("Telegram Bot Token or Channel ID not set in environment variables")
        return
    
    article = get_latest_article()
    
    if not article:
        logger.error("Failed to fetch latest article")
        return
    
    # Check if we've already posted this article
    last_url = get_last_article_url()
    if last_url and last_url == article['url']:
        logger.info("No new articles found")
        return
    
    success = send_telegram_message(article)
    
    if success:
        store_last_article_url(article['url'])
        logger.info(f"Posted new article: {article['title']}")
    else:
        logger.error("Failed to send message to Telegram")

if __name__ == "__main__":
    main()
