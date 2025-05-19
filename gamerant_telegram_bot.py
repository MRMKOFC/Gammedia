import os import requests import time from bs4 import BeautifulSoup import logging from datetime import datetime

Setup logging

logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' ) logger = logging.getLogger(name)

Constants

GAMERANT_URL = "https://gamerant.com/gaming/" TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID") TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

MAX_CAPTION_LENGTH = 1024 RETRY_COUNT = 3 RETRY_DELAY = 5

def escape_markdown_v2(text): """Escape special characters for Telegram Markdown V2.""" special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'] for char in special_chars: text = text.replace(char, f'{char}') return text

def validate_image_url(image_url): """Validate if the image URL is accessible and likely a real image.""" try: if not image_url or 'og-img.png' in image_url.lower() or 'social' in image_url.lower(): logger.warning(f"Skipping image URL likely a placeholder: {image_url}") return False headers = {'User-Agent': 'Mozilla/5.0'} response = requests.head(image_url, headers=headers, timeout=10, allow_redirects=True) if response.status_code != 200: logger.warning(f"Image URL not accessible, status code: {response.status_code}") return False content_type = response.headers.get('content-type', '') if not content_type.startswith('image/'): logger.warning(f"Image URL does not point to an image, content-type: {content_type}") return False return True except Exception as e: logger.warning(f"Error validating image URL {image_url}: {e}") return False

def send_telegram_message(article): """Send article information to Telegram channel with retries.""" if not article: logger.error("No article data to send") return False

title = escape_markdown_v2(article['title'])
summary = escape_markdown_v2(article['summary'])
image_url = escape_markdown_v2(article['image_url']) if article['image_url'] else ""

# Construct message
message = f"⚡\n*{title}*\n\n_{summary}_\n\n🍁 | @GamediaNews_acn"

# Ensure message length does not exceed Telegram limit
if len(message) > MAX_CAPTION_LENGTH:
    message = message[:MAX_CAPTION_LENGTH - 3] + "..."

for attempt in range(RETRY_COUNT):
    try:
        # Send Image if valid
        if image_url and validate_image_url(article['image_url']):
            logger.info(f"Attempting to send image: {image_url}")
            send_url = f"{TELEGRAM_API_URL}/sendPhoto"
            payload = {
                'chat_id': TELEGRAM_CHANNEL_ID,
                'photo': article['image_url'],
                'caption': message,
                'parse_mode': 'MarkdownV2'
            }
            response = requests.post(send_url, data=payload, timeout=30)
            response.raise_for_status()
            logger.info("Message with image sent successfully")
            return True
        else:
            logger.warning("Skipping image due to invalid or missing image URL")

        # Send Text Message
        send_url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHANNEL_ID,
            'text': message,
            'parse_mode': 'MarkdownV2',
            'disable_web_page_preview': True
        }
        response = requests.post(send_url, data=payload, timeout=30)
        response.raise_for_status()
        logger.info("Text message sent successfully")
        return True

    except Exception as e:
        logger.error(f"Error sending message (attempt {attempt+1}/{RETRY_COUNT}): {e}")
        time.sleep(RETRY_DELAY)

logger.error("Max retries reached. Message sending failed.")
return False

def main(): logger.info("Starting GameRant News Bot") articles = [ { 'title': "New Game Update: Exciting Features Unveiled!", 'summary': "The latest game update introduces new characters, missions, and an expanded world map.", 'image_url': "https://example.com/image.png" }, { 'title': "Upcoming Event in Popular Game", 'summary': "A special in-game event is set to begin next week.", 'image_url': "https://example.com/invalid-image.png" } ]

for article in articles:
    send_telegram_message(article)

if name == "main": main()

