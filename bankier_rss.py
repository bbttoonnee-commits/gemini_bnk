import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta
import pytz
import time
import random
import re

# Konfiguracja
BASE_URL = "https://www.bankier.pl/wiadomosc/"
PAGES_TO_SCAN = 5
RSS_FILE = "bankier_news.xml"
TIME_LIMIT_HOURS = 48
LOCAL_TZ = pytz.timezone('Europe/Warsaw')

# Nagłówki udające przeglądarkę
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def parse_date(date_str):
    """Konwertuje datę ze strony na obiekt datetime."""
    # Bankier często podaje daty w formacie "Dziś, 12:00" lub "2025-12-30 08:30"
    now = datetime.now(LOCAL_TZ)
    date_str = date_str.strip()
    
    try:
        if "dzisiaj" in date_str.lower() or "dziś" in date_str.lower():
            time_part = re.search(r'(\d{2}:\d{2})', date_str).group(1)
            h, m = map(int, time_part.split(':'))
            return now.replace(hour=h, minute=m, second=0, microsecond=0)
        elif "wczoraj" in date_str.lower():
            time_part = re.search(r'(\d{2}:\d{2})', date_str).group(1)
            h, m = map(int, time_part.split(':'))
            return (now - timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)
        else:
            # Format standardowy: YYYY-MM-DD HH:MM
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            return LOCAL_TZ.localize(dt)
    except Exception:
        return now # Fallback

def get_articles():
    articles = []
    seen_urls = set()
    cutoff_date = datetime.now(LOCAL_TZ) - timedelta(hours=TIME_LIMIT_HOURS)

    for page in range(1, PAGES_TO_SCAN + 1):
        url = f"{BASE_URL}{page}" if page > 1 else BASE_URL
        print(f"Skanowanie strony {page}: {url}")
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Lokalizacja kontenerów na podstawie screena (div.entry-description / div.article)
            # Bankier używa klasy 'article' lub 'entry-description' w zależności od sekcji
            items = soup.find_all('div', class_=re.compile(r'article|entry-description|item'))

            for item in items:
                title_tag = item.find('span', class_='entry-title') or item.find('a')
                if not title_tag or not title_tag.text.strip(): continue
                
                link = title_tag.find_parent('a')['href'] if title_tag.name != 'a' else title_tag['href']
                if not link.startswith('http'):
                    link = f"https://www.bankier.pl{link}"
                
                if link in seen_urls: continue

                # Pobieranie daty i opisu
                date_tag = item.find('time') or item.find('span', class_='entry-date')
                pub_date = parse_date(date_tag.text) if date_tag else datetime.now(LOCAL_TZ)

                # Filtr 48h
                if pub_date < cutoff_date:
                    continue

                summary_tag = item.find('p') or item.find('div', class_='lead')
                summary = summary_tag.text.strip() if summary_tag else ""

                articles.append({
                    'title': title_tag.text.strip(),
                    'link': link,
                    'date': pub_date,
                    'summary': summary
                })
                seen_urls.add(link)

            time.sleep(random.uniform(1.5, 3.0)) # Anti-bot delay
        except Exception as e:
            print(f"Błąd na stronie {page}: {e}")
            continue
            
    return articles

def generate_rss(articles):
    fg = FeedGenerator()
    fg.title('Bankier.pl - Wiadomości (Custom RSS)')
    fg.link(href=BASE_URL, rel='alternate')
    fg.description('Zautomatyzowany kanał RSS z najnowszymi informacjami')
    fg.language('pl')

    for entry in articles:
        fe = fg.add_entry()
        fe.title(entry['title'])
        fe.link(href=entry['link'])
        fe.description(entry['summary'])
        fe.pubDate(entry['date'])
        fe.guid(entry['link'], permalink=True)

    fg.rss_file(RSS_FILE, pretty=True)
    print(f"Sukces! Wygenerowano {len(articles)} wpisów w {RSS_FILE}")

if __name__ == "__main__":
    news_list = get_articles()
    if news_list:
        generate_rss(news_list)
    else:
        print("Nie znaleziono nowych artykułów spełniających kryteria.")
