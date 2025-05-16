import requests
from bs4 import BeautifulSoup
import os
import telegram
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def scrape_gamerant():
    url = "https://gamerant.com/gaming/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = []
        
        # Find all article cards - this selector might need adjustment if site changes
        for article in soup.select('div.browse-card'):
            try:
                title = article.select_one('h3.browse-title').get_text(strip=True)
                summary = article.select_one('p.browse-excerpt').get_text(strip=True)
                image = article.select_one('img.browse-image')['src']
                link = article.select_one('a.browse-link')['href']
                
                # Ensure we have absolute URL for image and link
                if image.startswith('/'):
                    image = f"https://gamerant.com{image}"
                if link.startswith('/'):
                    link = f"https://gamerant.com{link}"
                
                articles.append({
                    'title': title,
                    'summary': summary,
                    'image': image,
                    'link': link
                })
            except Exception as e:
                logger.warning(f"Error parsing article: {e}")
                continue
        
        return articles
    
    except Exception as e:
        logger.error(f"Error scraping Gamerant: {e}")
        return []

def format_post(article):
    return (
        f"<b>⚡ {article['title']}</b>\n\n"
        f"<i>{article['summary']}</i>\n\n"
        f"🍁 | @GamediaNews_acn"
    )

def send_to_telegram(articles, bot_token, channel_id, last_post_cache):
    bot = telegram.Bot(token=bot_token)
    new_last_post = last_post_cache
    
    try:
        # Send articles in reverse order to get newest first
        for article in reversed(articles):
            # Skip if we've already posted this article
            if article['link'] == last_post_cache:
                continue
                
            try:
                # Download image
                image_response = requests.get(article['image'], stream=True)
                image_response.raise_for_status()
                
                # Send photo with caption
                bot.send_photo(
                    chat_id=channel_id,
                    photo=image_response.raw,
                    caption=format_post(article),
                    parse_mode='HTML'
                )
                
                # Update last posted article
                new_last_post = article['link']
                logger.info(f"Posted: {article['title']}")
                
                # Break after first new article to post one at a time
                break
                
            except Exception as e:
                logger.error(f"Error sending article {article['title']}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in Telegram communication: {e}")
    
    return new_last_post

def read_last_post():
    try:
        with open('last_post.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def write_last_post(last_post):
    with open('last_post.txt', 'w') as f:
        f.write(last_post)

def main():
    # Get configuration from environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not bot_token or not channel_id:
        logger.error("Missing Telegram bot token or channel ID")
        return
    
    # Get last posted article
    last_post = read_last_post()
    
    # Scrape new articles
    articles = scrape_gamerant()
    
    if not articles:
        logger.warning("No articles found")
        return
    
    # Send new articles to Telegram
    new_last_post = send_to_telegram(articles, bot_token, channel_id, last_post)
    
    # Update last posted article if new one was posted
    if new_last_post != last_post:
        write_last_post(new_last_post)

if __name__ == "__main__":
    main()
