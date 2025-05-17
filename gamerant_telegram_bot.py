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
        
        logger.info(f"Response preview: {response.text[:1000]}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        selectors = [
            'article.browse-clip', 
            'article:not(.sidebar--trending)',
            'div.article-card', 
            'div.article-preview', 
            'div.post', 
            'div.entry', 
            'div.content-card',
            'div[class*="article"]',
            'div[class*="post"]',
            'div[class*="news"]'
        ]
        
        articles = None
        used_selector = None
        
        for selector in selectors:
            articles = soup.select(selector)
            articles = [
                article for article in articles 
                if 'sidebar' not in article.get('class', [])
                and article.get_text(strip=True)
            ]
            if articles:
                used_selector = selector
                logger.info(f"Found {len(articles)} articles with selector: {selector}")
                break
        
        if not articles:
            potential_articles = soup.find_all('a', href=True)
            articles = [a for a in potential_articles if '/gaming/' in a.get('href', '')]
            if articles:
                used_selector = "a[href*='/gaming/']"
                logger.info(f"Found {len(articles)} articles using href filtering")
        
        if not articles:
            logger.error("No articles found on the page")
            logger.error(f"Page structure: {soup.prettify()[:1000]}...")
            return None
        
        for i, article in enumerate(articles[:3]):
            logger.info(f"Article {i+1} HTML: {str(article)[:500]}...")
        
        latest_article = articles[0]
        
        title_element = None
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 
            'h5.title', 'h5', 
            '.title', '.headline', '.article-title', 
            '[class*="title"]', '[class*="headline"]',
            'a[href] span', 'a[href] div'
        ]
        
        for selector in title_selectors:
            if used_selector == "a[href*='/gaming/']":
                title_element = latest_article
                break
            else:
                title_element = latest_article.select_one(selector)
                if title_element:
                    logger.info(f"Found title with selector: {selector}")
                    break
        
        if not title_element:
            logger.error(f"Could not find title element. Article HTML: {str(latest_article)[:1000]}...")
            title_element = latest_article
            logger.warning("Using article element as title element")
        
        title = title_element.text.strip() if title_element else ""
        if not title:
            title = latest_article.get_text(strip=True)[:100]
            logger.warning(f"Extracted title from article text: {title}")
            if not title:
                logger.error("No title could be extracted, skipping article")
                return None
        
        if used_selector == "a[href*='/gaming/']":
            article_url = latest_article['href']
        else:
            link_element = latest_article.find('a', href=True)
            if not link_element:
                link_element = latest_article.select_one('a[href]')
            
            if not link_element:
                logger.error("Could not find link element")
                return None
            
            article_url = link_element['href']
            
        if not article_url.startswith('http'):
            article_url = f"https://gamerant.com{article_url}"
        
        article_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': GAMERANT_URL
        }
        
        logger.info(f"Fetching full article from: {article_url}")
        article_response = requests.get(article_url, headers=article_headers, timeout=30)
        article_response.raise_for_status()
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        
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
        
        image_url = None
        image_selectors = [
            'img.header-img',
            '.article-img-wrapper img',
            '.featured-image img',
            '.article-featured-image img',
            'div.featured-image-container img',
            'img[src*="gamerant.com"]',
            'meta[property="og:image"]',
            'img'
        ]
        
        for selector in image_selectors:
            if selector == 'meta[property="og:image"]':
                img_element = article_soup.select_one(selector)
                if img_element:
                    image_url = img_element.get('content')
                    if image_url and 'og-img.png' not in image_url.lower():
                        logger.info(f"Found image in og:image meta tag")
                        break
            else:
                img_elements = article_soup.select(selector)
                if img_elements:
                    for img in img_elements:
                        if 'src' in img.attrs:
                            src = img['src']
                            if ('icon' not in src.lower() and 
                                'logo' not in src.lower() and
                                'avatar' not in src.lower() and
                                'og-img.png' not in src.lower() and
                                'social' not in src.lower()):
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

def escape_markdown(text):
    """Escape special characters for Telegram Markdown."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def validate_image_url(image_url):
    """Validate if the image URL is accessible and likely a real image."""
    try:
        if 'og-img.png' in image_url.lower() or 'social' in image_url.lower():
            logger.warning(f"Skipping image URL likely a placeholder: {image_url}")
            return False
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.head(image_url, headers=headers, timeout=10, allow_redirects=True)
        if response.status_code != 200:
            logger.warning(f"Image URL not accessible, status code: {response.status_code}")
            return False
        
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"Image URL does not point to an image, content-type: {content_type}")
            return False
        
        return True
    except Exception as e:
        logger.warning(f"Error validating image URL {image_url}: {e}")
        return False

def send_telegram_message(article):
    """Send article information to Telegram channel."""
    if not article:
        logger.error("No article data to send")
        return False
    
    # Escape special characters in title and summary for Markdown
    title = escape_markdown(article['title'])
    summary = escape_markdown(article['summary'])
    
    # Format the message with emojis, escaping the '|' character
    message = f"⚡\n*{title}*\n\n_{summary}_\n\n🍁 \\| @GamediaNews_acn"
    
    logger.info(f"Formatted message: {message}")
    
    # Log byte offsets for debugging
    byte_message = message.encode('utf-8')
    logger.info(f"Message byte length: {len(byte_message)}")
    for i, char in enumerate(message):
        char_bytes = char.encode('utf-8')
        logger.debug(f"Char at position {i}: {char} (bytes: {char_bytes})")
    
    try:
        if article['image_url'] and validate_image_url(article['image_url']):
            logger.info(f"Attempting to send image: {article['image_url']}")
            send_url = f"{TELEGRAM_API_URL}/sendPhoto"
            payload = {
                'chat_id': TELEGRAM_CHANNEL_ID,
                'photo': article['image_url'],
                'caption': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(send_url, data=payload, timeout=30)
            if response.status_code != 200:
                logger.warning(f"Failed to send image, error: {response.text}")
                raise Exception("Image sending failed")
            response.raise_for_status()
            logger.info("Message with image sent successfully")
            return True
        else:
            logger.warning("Skipping image sending due to invalid or missing image URL")
        
        # Send text message as fallback
        send_url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message + f"\n\n{article['url']}",
            'parse_mode': 'Markdown',
            'disable_web_page_preview': False
        }
        
        response = requests.post(send_url, data=payload, timeout=30)
        if response.status_code != 200:
            logger.error(f"Failed to send text message, error: {response.text}")
            raise Exception("Text message sending failed")
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
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        logger.error("Telegram Bot Token or Channel ID not set in environment variables")
        return
    
    article = get_latest_article()
    
    if not article:
        logger.error("Failed to fetch latest article")
        return
    
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
