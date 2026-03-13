"""
services/fetch_news.py - News Fetching from Multiple Sources (BeautifulSoup Version)
"""

import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import re
import validators
from typing import List, Dict, Optional
from config import NEWSAPI_KEY, NEWSAPI_BASE_URL


class NewsAPIFetcher:
    """Fetch news from NewsAPI.org"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or NEWSAPI_KEY
        self.base_url = NEWSAPI_BASE_URL
    
    def _make_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Make request to NewsAPI."""
        if not self.api_key or self.api_key == "your_newsapi_key_here":
            print("[NewsAPI] ERROR: API key not configured")
            return None
        
        params['apiKey'] = self.api_key
        
        try:
            print(f"[NewsAPI] Requesting: {self.base_url}/{endpoint}")
            response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
            print(f"[NewsAPI] Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[NewsAPI] Error: {response.text}")
                return None
            
            try:
                return response.json()
            except ValueError as je:
                print(f"[NewsAPI] JSON Decode Error: {je}")
                print(f"[NewsAPI] Response text: {response.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            print(f"[NewsAPI] Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[NewsAPI] Request Exception: {e}")
            return None
        except Exception as e:
            print(f"[NewsAPI] Exception: {e}")
            return None
    
    def fetch_top_headlines(self, category: str = "general", country: str = "us", 
                           page_size: int = 5) -> List[dict]:
        """Fetch top headlines by category and country."""
        params = {
            'category': category,
            'country': country,
            'pageSize': page_size
        }
        
        data = self._make_request("top-headlines", params)
        if data and data.get('status') == 'ok':
            return self._parse_articles(data.get('articles', []))
        return []
    
    def search_articles(self, query: str, from_date: str = None, to_date: str = None,
                       sort_by: str = "publishedAt", page_size: int = 5) -> List[dict]:
        """Search articles by keyword."""
        params = {
            'q': query,
            'sortBy': sort_by,
            'pageSize': page_size,
            'language': 'en'
        }
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        data = self._make_request("everything", params)
        if data and data.get('status') == 'ok':
            return self._parse_articles(data.get('articles', []))
        return []
    
    def _parse_articles(self, articles: List[dict]) -> List[dict]:
        """Parse and standardize article format from NewsAPI."""
        parsed = []
        
        for article in articles:
            content = article.get('description', '') or article.get('content', '')
            if '[+' in content:
                content = content[:content.rfind('[+')]
            
            if '[Removed]' in content:
                continue
            
            if not content or len(content) < 50:
                continue
            
            parsed.append({
                'id': hash(article.get('url', '')) % 100000,
                'title': article.get('title', 'Untitled'),
                'content': content,
                'source': article.get('source', {}).get('name', 'NewsAPI'),
                'url': article.get('url', ''),
                'image_url': article.get('urlToImage', ''),
                'published_at': article.get('publishedAt', ''),
                'author': article.get('author', '')
            })
        
        return parsed


class URLScraper:
    """Scrape article content from URLs using BeautifulSoup"""
    
    def scrape_article(self, url: str, timeout: int = 15) -> Optional[dict]:
        """Scrape article from URL using BeautifulSoup."""
        if not validators.url(url):
            print(f"[URLScraper] ERROR: Invalid URL: {url}")
            return None
        
        try:
            print(f"[URLScraper] Scraping: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            print(f"[URLScraper] Response received")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = None
            title_tag = soup.find('h1')
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            if not title:
                title_meta = soup.find('meta', property='og:title')
                if title_meta:
                    title = title_meta.get('content', 'Article')
                else:
                    title = soup.title.string if soup.title else "Article"
            
            # Extract content
            content_text = []
            article_tags = soup.find_all(['article', 'main'])
            
            if article_tags:
                for tag in article_tags:
                    paragraphs = tag.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 20:
                            content_text.append(text)
            else:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        content_text.append(text)
            
            content = ' '.join(content_text)
            
            if len(content) < 100:
                print(f"[URLScraper] ERROR: Content too short: {len(content)} chars")
                return None
            
            print(f"[URLScraper] SUCCESS: Extracted {len(content)} chars, title: {title}")
            
            return {
                'id': hash(url) % 100000,
                'title': title,
                'content': content,
                'source': url.split('/')[2],
                'url': url,
                'image_url': '',
                'published_at': '',
                'author': ''
            }
        
        except Exception as e:
            print(f"[URLScraper] ERROR: {e}")
            return None


class YouTubeTranscriptExtractor:
    """Extract transcripts from YouTube videos"""
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        match = re.search(r'youtube\.com/v/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    def get_transcript(self, video_url: str, languages: List[str] = None) -> Optional[dict]:
        """Get transcript from YouTube video."""
        if languages is None:
            languages = ['en', 'en-US', 'en-GB']
        
        video_id = self.extract_video_id(video_url)
        if not video_id:
            print(f"[YouTube] ERROR: Could not extract video ID from: {video_url}")
            return None
        
        print(f"[YouTube] Video ID: {video_id}")
        
        try:
            print(f"[YouTube] Getting transcript with languages: {languages}")
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            transcript_text = ' '.join([t['text'] for t in transcript_list])
            title = self._get_video_title(video_id)
            
            print(f"[YouTube] SUCCESS: Got {len(transcript_list)} segments")
            
            return {
                'id': hash(video_url) % 100000,
                'title': title or 'YouTube Video Transcript',
                'content': transcript_text,
                'source': 'YouTube',
                'url': video_url,
                'image_url': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
                'published_at': '',
                'author': ''
            }
        
        except Exception as e:
            print(f"[YouTube] ERROR: {e}")
            return None
    
    def _get_video_title(self, video_id: str) -> Optional[str]:
        """Get video title from YouTube via oEmbed API."""
        try:
            response = requests.get(
                f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('title')
        except Exception as e:
            print(f"Could not fetch video title: {e}")
        
        return None


# ============================================================================
# COMPREHENSIVE NEWS FETCHING (NewsAPI + RSS)
# ============================================================================

def fetch_news_comprehensive(topic: str, use_rss: bool = True, use_api: bool = True) -> List[dict]:
    """
    Fetch news from both NewsAPI and RSS feeds for comprehensive coverage.
    
    Args:
        topic: Topic/query to search for
        use_rss: Whether to fetch from RSS feeds
        use_api: Whether to fetch from NewsAPI
    
    Returns:
        List of unique articles from all sources, deduplicated by URL
    """
    articles = []
    
    print(f"[Comprehensive] Fetching news for topic: '{topic}'")
    print(f"[Comprehensive] Using NewsAPI: {use_api}, Using RSS: {use_rss}")
    
    # Fetch from NewsAPI if enabled
    if use_api:
        print(f"[Comprehensive] Fetching from NewsAPI...")
        try:
            fetcher = NewsAPIFetcher()
            api_articles = fetcher.search_articles(
                query=topic,
                page_size=10
            )
            
            # Add fetched_via marker
            for article in api_articles:
                article['fetched_via'] = 'api'
            
            articles.extend(api_articles)
            print(f"[Comprehensive] NewsAPI: {len(api_articles)} articles")
        except Exception as e:
            print(f"[Comprehensive] NewsAPI error: {str(e)}")
    
    # Fetch from RSS feeds if enabled
    if use_rss:
        print(f"[Comprehensive] Fetching from RSS feeds...")
        try:
            from services.rss_fetcher import RSSFetcher
            
            rss_fetcher = RSSFetcher()
            rss_results = rss_fetcher.fetch_topic_from_all_sources(topic, max_per_source=5)
            
            # Flatten results from all sources
            rss_articles = []
            for source_name, source_articles in rss_results.get('results', {}).items():
                rss_articles.extend(source_articles)
            
            articles.extend(rss_articles)
            print(f"[Comprehensive] RSS: {len(rss_articles)} articles from {len(rss_results.get('results', {}))} sources")
        except Exception as e:
            print(f"[Comprehensive] RSS error: {str(e)}")
    
    if not articles:
        print(f"[Comprehensive] WARNING: No articles found from any source")
        return []
    
    # Deduplicate by URL
    print(f"[Comprehensive] Deduplicating {len(articles)} articles...")
    seen_urls = set()
    unique_articles = []
    
    for article in articles:
        url = article.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
    
    print(f"[Comprehensive] After deduplication: {len(unique_articles)} unique articles")
    return unique_articles
