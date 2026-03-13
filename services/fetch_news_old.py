"""
services/fetch_news.py - News Fetching from Multiple Sources
=============================================================
Supports:
1. NewsAPI for top headlines and search
2. URL web scraping for any article
3. YouTube transcript extraction
"""

import requests
from newspaper import Article as NewspaperArticle
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
        if not self.api_key:
            print("ERROR: NewsAPI key not configured")
            return None
        
        params['apiKey'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 426:
                print("ERROR: NewsAPI - Upgrade required (rate limit exceeded)")
            elif e.response.status_code == 401:
                print("ERROR: NewsAPI - Invalid API key")
            else:
                print(f"ERROR: NewsAPI HTTP error - {e}")
            return None
        
        except requests.exceptions.Timeout:
            print("ERROR: NewsAPI request timed out")
            return None
        
        except requests.exceptions.RequestException as e:
            print(f"ERROR: NewsAPI request failed - {e}")
            return None
    
    def fetch_top_headlines(
        self, 
        category: str = None, 
        country: str = 'us', 
        page_size: int = 10,
        page: int = 1
    ) -> List[Dict]:
        """Fetch top headlines."""
        params = {
            'country': country,
            'pageSize': min(page_size, 100),
            'page': page
        }
        
        if category:
            params['category'] = category
        
        data = self._make_request('top-headlines', params)
        
        if not data or data.get('status') != 'ok':
            return []
        
        return self._parse_articles(data.get('articles', []), category)
    
    def search_articles(
        self, 
        query: str, 
        from_date: str = None, 
        to_date: str = None,
        sort_by: str = 'publishedAt',
        page_size: int = 10,
        page: int = 1
    ) -> List[Dict]:
        """Search for articles by keyword."""
        params = {
            'q': query,
            'sortBy': sort_by,
            'pageSize': min(page_size, 100),
            'page': page
        }
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        data = self._make_request('everything', params)
        
        if not data or data.get('status') != 'ok':
            return []
        
        return self._parse_articles(data.get('articles', []))
    
    def _parse_articles(self, articles: List[dict], category: str = None) -> List[Dict]:
        """Parse NewsAPI response into standardized format."""
        parsed = []
        
        for item in articles:
            if item.get('content') == "[Removed]" or not item.get('content'):
                continue
            
            content = item.get('content', '')
            content = re.sub(r'\[\+\d+ chars\]$', '', content)
            
            if not content or len(content) < 50:
                content = item.get('description', '')
            
            if not content:
                continue
            
            article = {
                'title': item.get('title', 'Untitled'),
                'content': content,
                'source': item.get('source', {}).get('name', 'Unknown'),
                'url': item.get('url'),
                'category': category,
                'published_at': item.get('publishedAt'),
                'author': item.get('author'),
                'image_url': item.get('urlToImage')
            }
            
            parsed.append(article)
        
        return parsed


class URLScraper:
    """Scrape articles from any URL using newspaper3k."""
    
    @staticmethod
    def scrape_article(url: str, timeout: int = 15) -> Optional[Dict]:
        """Extract article from URL."""
        if not validators.url(url):
            print(f"ERROR: Invalid URL format - {url}")
            return None
        
        try:
            article = NewspaperArticle(url)
            article.download()
            article.parse()
            
            if not article.text or len(article.text.strip()) < 100:
                print("ERROR: Article text too short or empty")
                return None
            
            return {
                'title': article.title or 'Untitled',
                'content': article.text,
                'source': article.source_url,
                'url': url,
                'authors': ', '.join(article.authors) if article.authors else None,
                'publish_date': article.publish_date.isoformat() if article.publish_date else None,
                'image_url': article.top_image,
                'keywords': article.keywords[:10] if article.keywords else []
            }
        
        except Exception as e:
            print(f"ERROR: Failed to scrape URL - {e}")
            return URLScraper._fallback_scrape(url, timeout)
    
    @staticmethod
    def _fallback_scrape(url: str, timeout: int = 15) -> Optional[Dict]:
        """Fallback scraping method using BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_tag = soup.find('h1') or soup.find('title')
            title = title_tag.get_text().strip() if title_tag else 'Untitled'
            
            content_tags = soup.find_all(['article', 'p'])
            content = '\n'.join([tag.get_text().strip() for tag in content_tags])
            
            content = re.sub(r'\s+', ' ', content).strip()
            
            if len(content) < 100:
                return None
            
            return {
                'title': title,
                'content': content,
                'source': url,
                'url': url
            }
        
        except Exception as e:
            print(f"ERROR: Fallback scraping also failed - {e}")
            return None


class YouTubeTranscriptExtractor:
    """Extract transcripts from YouTube videos."""
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=)([\w-]+)',
            r'(?:youtu\.be\/)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
            r'(?:youtube\.com\/v\/)([\w-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def get_transcript(
        video_url: str, 
        languages: List[str] = ['en', 'en-US', 'en-GB']
    ) -> Optional[Dict]:
        """Get transcript from YouTube video."""
        try:
            video_id = YouTubeTranscriptExtractor.extract_video_id(video_url)
            
            if not video_id:
                print("ERROR: Could not extract video ID from URL")
                return None
            
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=languages
            )
            
            full_transcript = ' '.join([item['text'] for item in transcript_list])
            
            title = YouTubeTranscriptExtractor._get_video_title(video_id)
            
            return {
                'title': title or f"YouTube Video {video_id}",
                'content': full_transcript,
                'source': 'YouTube',
                'url': video_url,
                'video_id': video_id
            }
        
        except Exception as e:
            print(f"ERROR: Failed to get YouTube transcript - {e}")
            return None
    
    @staticmethod
    def _get_video_title(video_id: str) -> Optional[str]:
        """Get video title using YouTube oEmbed API."""
        try:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get('title')
        except:
            return None
