# Gaming News Scraper for Telegram
# Extracts news from the specified source and posts to Telegram every 30 minutes.

import requests
from bs4 import BeautifulSoup
import os
import telegram
import json

# Environment Variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
NEWS_URL = os.getenv('NEWS_URL')  # URL is now a secret
FALLBACK_IMAGE = 'https://example.com/default_image.png'

# Previously posted links
POSTED_LINKS_FILE = 'posted_links.json'

# Initialize Telegram Bot
bot = telegram.Bot(token=BOT_TOKEN)

# Load posted links
def load_posted_links():
    if os.path.exists(POSTED_LINKS_FILE):
        with open(POSTED_LINKS_FILE, 'r') as file:
            return json.load(file)
    return []

# Save posted links
def save_posted_links(links):
    with open(POSTED_LINKS_FILE, 'w') as file:
        json.dump(links, file)

# Extract hashtags
def extract_hashtags(title):
    keywords = ['PC', 'Xbox', 'PlayStation', 'Esports', 'Mobile']
    return ' '.join([f'#{word}' for word in keywords if word.lower() in title.lower()])

# Scrape news
def scrape_news():
    response = requests.get(NEWS_URL)
    soup = BeautifulSoup(response.content, 'html.parser')
    articles = soup.select('article')
    posted_links = load_posted_links()
    new_links = []

    for article in articles:
        try:
            title_tag = article.select_one('h3 a')
            title = title_tag.text.strip()
            link = title_tag['href']
            summary = article.select_one('p').text.strip()
            images = article.select('img')
            image_urls = [img['src'] for img in images if 'src' in img.attrs]
            image_urls = image_urls if image_urls else [FALLBACK_IMAGE]

            # Avoid duplicate posts
            if link in posted_links:
                continue

            # Construct message
            hashtags = extract_hashtags(title)
            message = f"<b>⚡ {title}</b>\n\n<i>{summary}</i>\n\n{hashtags}\n🍁 | @GamediaNews_acn"

            # Send all images
            media_group = [
                telegram.InputMediaPhoto(url, caption=message if idx == 0 else '', parse_mode='HTML')
                for idx, url in enumerate(image_urls)
            ]
            bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)

            # Track posted link
            new_links.append(link)

        except Exception as e:
            print(f"Error processing article: {e}")

    # Update posted links
    posted_links.extend(new_links)
    save_posted_links(posted_links)

if __name__ == '__main__':
    scrape_news()