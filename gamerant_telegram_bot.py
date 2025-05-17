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
        # Add headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        response = requests.get(GAMERANT_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Log the first 1000 characters of the response for debugging
        logger.info(f"Response preview: {response.text[:1000]}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple selectors that might match articles
        selectors = [
            'article.browse-clip', 
            'article', 
            '.article-card',
            '.article-preview', 
            '.post',
            '.entry',
            'div.content-card'
        ]
        
        articles = None
        used_selector = None
        
        # Try each selector until we find articles
        for selector in selectors:
            articles = soup.select(selector)
            if articles:
                used_selector = selector
                logger.info(f"Found {len(articles)} articles with selector: {selector}")
                break
                
        if not articles:
            # If no articles found with specific selectors, look for any <a> tags that might be articles
            potential_articles = soup.find_all('a', href=True)
            articles = [a for a in potential_articles if '/gaming/' in a.get('href', '')]
            if articles:
                used_selector = "a[href*='/gaming/']"
                logger.info(f"Found {len(articles)} articles using href filtering")
        
        if not articles:
            logger.error("No articles found on the page")
            # Log HTML structure for debugging
            logger.error(f"Page structure: {soup.prettify()[:500]}...")
            return None
        
        latest_article = articles[0]
        
        # Extract title - try multiple approaches
        title_element = None
        title_selectors = ['h1', 'h2', 'h3', 'h4', 'h5.title', 'h5', '.title', '.headline', '.article-title']
        
        for selector in title_selectors:
            if used_selector == "a[href*='/gaming/']":
                # If we're using the fallback link approach
                title_element = latest_article
                break
            else:
                title_element = latest_article.select_one(selector)
                if title_element:
                    logger.info(f"Found title with selector: {selector}")
                    break
        
        if not title_element:
            # If still no title element, use the article element itself
            title_element = latest_article
            logger.warning("Using article element as title element")
        
        title = title_element.text.strip()
        if not title:
            logger.error("Empty title text")
            return None
        
        # Extract URL
        if used_selector == "a[href*='/gaming/']":
            # If we're using the fallback link approach
            article_url = latest_article['href']
        else:
            link_element = latest_article.find('a', href=True)
            if not link_element:
                # Try to find any link in the article
                link_element = latest_article.select_one('a[href]')
            
            if not link_element:
                logger.error("Could not find link element")
                return None
            
            article_url = link_element['href']
            
        if not article_url.startswith('http'):
            article_url = f"https://gamerant.com{article_url}"
        
        # Get full article to extract summary and main image
        article_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': GAMERANT_URL
        }
        
        logger.info(f"Fetching full article from: {article_url}")
        article_response = requests.get(article_url, headers=article_headers, timeout=30)
        article_response.raise_for_status()
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        
        # Extract summary - try multiple approaches
        summary_element = None
        summary_selectors = [
            'h2.subtitle', 
            '.subtitle', 
            '.summary', 
            '.article-excerpt',
            '.excerpt',
            'meta[name="description"]',
            'div.article-body > p:first-child',
            'div.article-body p',
            'div.entry-content > p:first-child',
            'p'
        ]
        
        for selector in summary_selectors:
            if selector == 'meta[name="description"]':
                summary_element = article_soup.select_one(selector)
                if summary_element:
                    summary = summary_element.get('content', '')
                    if summary:
                        logger.info(f"Found summary in meta description")
                        break
            else:
                summary_element = article_soup.select_one(selector)
                if summary_element and summary_element.text.strip():
                    logger.info(f"Found summary with selector: {selector}")
                    summary = summary_element.text.strip()
                    break
        
        if not summary_element or not summary:
            summary = "No summary available"
            logger.warning("Could not find summary, using default")
        
        # Extract main image - try multiple approaches
        image_url = None
        image_selectors = [
            'img.header-img',
            '.article-img-wrapper img',
            '.featured-image img',
            '.article-featured-image img',
            'meta[property="og:image"]',
            'img[src*="gamerant.com"]',
            'img'
        ]
        
        for selector in image_selectors:
            if selector == 'meta[property="og:image"]':
                img_element = article_soup.select_one(selector)
                if img_element:
                    image_url = img_element.get('content')
                    if image_url:
                        logger.info(f"Found image in og:image meta tag")
                        break
            else:
                img_elements = article_soup.select(selector)
                if img_elements:
                    for img in img_elements:
                        if 'src' in img.attrs:
                            # Skip tiny images and icons
                            src = img['src']
                            if ('icon' not in src.lower() and 
                                'logo' not in src.lower() and
                                'avatar' not in src.lower()):
                                image_url = src
                                logger.info(f"Found image with selector: {selector}")
                                break
                    if image_url:
                        break
        
        if not image_url:
            logger.warning("Could not find image")
        
        return {
            'title': title,
            'summary': summary,
            'url': article_url,
            'image_url': image_url
        }
    except Exception as e:
        logger.error(f"Error fetching article: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
    
    try:
        # If there's an image, try sending photo with caption
        if article['image_url']:
            logger.info(f"Attempting to send image: {article['image_url']}")
            send_url = f"{TELEGRAM_API_URL}/sendPhoto"
            payload = {
                'chat_id': TELEGRAM_CHANNEL_ID,
                'photo': article['image_url'],
                'caption': message,
                'parse_mode': 'Markdown'
            }
            
            try:
                response = requests.post(send_url, data=payload, timeout=30)
                # If image sending fails, fallback to text message
                if response.status_code != 200:
                    logger.warning(f"Failed to send image, error: {response.text}")
                    raise Exception("Image sending failed")
                response.raise_for_status()
                logger.info("Message with image sent successfully")
                return True
            except Exception as img_error:
                logger.warning(f"Error sending image: {img_error}, falling back to text message")
                # Fallback to text message below
        
        # Send text message (either as primary method or fallback)
        send_url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message + f"\n\n{article['url']}",  # Include the article URL in text-only messages
            'parse_mode': 'Markdown',
            'disable_web_page_preview': False  # Enable link preview which might show image
        }
        
        response = requests.post(send_url, data=payload, timeout=30)
        response.raise_for_status()
        logger.info("Text message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
