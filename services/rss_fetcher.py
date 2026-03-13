"""
services/rss_fetcher.py - RSS Feed Fetching and Parsing
========================================================
Fetches and parses RSS feeds from multiple Indian news sources.
Handles various feed formats, date parsing, and error recovery.
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dateutil import parser as dateutil_parser
import logging
from config import RSS_SOURCES, RSS_CONFIG

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSFetcher:
    """Fetch and parse RSS feeds from configured news sources."""
    
    def __init__(self):
        """Initialize RSS fetcher with configured sources."""
        self.sources = RSS_SOURCES
        self.config = RSS_CONFIG
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.config['user_agent']})
    
    def fetch_from_source(self, source_key: str, topic_keywords: List[str], 
                         max_articles: int = 5) -> List[Dict]:
        """
        Fetch articles from a specific RSS source based on topic keywords.
        
        Args:
            source_key: Key of the source from RSS_SOURCES config
            topic_keywords: Keywords to filter articles
            max_articles: Maximum articles to return
        
        Returns:
            List of article dicts with standardized format
        """
        source_config = self.sources.get(source_key)
        if not source_config:
            logger.warning(f"[RSS] Unknown source: {source_key}")
            return []
        
        articles = []
        rss_urls = source_config.get('rss_urls', {})
        
        # Try each RSS feed URL for this source
        for category, url in rss_urls.items():
            try:
                feed_articles = self._fetch_feed(source_key, url, topic_keywords, max_articles)
                articles.extend(feed_articles)
                
                if len(articles) >= max_articles:
                    break
            except Exception as e:
                logger.error(f"[RSS] Error fetching {source_key}/{category}: {str(e)}")
                continue
        
        # Limit to max_articles
        return articles[:max_articles]
    
    def _fetch_feed(self, source_key: str, feed_url: str, topic_keywords: List[str],
                   max_articles: int) -> List[Dict]:
        """
        Fetch and parse a single RSS feed.
        
        Args:
            source_key: Source identifier
            feed_url: URL of the RSS feed
            topic_keywords: Keywords to filter entries
            max_articles: Max articles to return
        
        Returns:
            List of parsed article dicts
        """
        try:
            logger.info(f"[RSS] Fetching feed: {feed_url}")
            
            # Fetch feed with timeout
            response = self.session.get(feed_url, timeout=self.config['timeout_per_feed'])
            response.raise_for_status()
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"[RSS] Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            articles = []
            
            for entry in feed.entries:
                # Check if entry matches keywords
                if not self._matches_keywords(entry, topic_keywords):
                    continue
                
                article = self._parse_entry(source_key, entry)
                if article:
                    articles.append(article)
                
                if len(articles) >= max_articles:
                    break
            
            logger.info(f"[RSS] Extracted {len(articles)} articles from {source_key}")
            return articles
        
        except requests.exceptions.Timeout:
            logger.error(f"[RSS] Timeout fetching {feed_url}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"[RSS] Network error fetching {feed_url}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"[RSS] Unexpected error parsing {feed_url}: {str(e)}")
            return []
    
    def _matches_keywords(self, entry: dict, keywords: List[str]) -> bool:
        """Check if entry title/summary matches any keyword."""
        title = entry.get('title', '').lower()
        summary = entry.get('summary', '').lower()
        text = f"{title} {summary}"
        
        return any(kw.lower() in text for kw in keywords)
    
    def _parse_entry(self, source_key: str, entry: dict) -> Optional[Dict]:
        """
        Parse RSS entry to standard article format.
        
        Args:
            source_key: Source identifier
            entry: RSS entry dict from feedparser
        
        Returns:
            Standardized article dict or None if invalid
        """
        try:
            title = entry.get('title', '').strip()
            if not title:
                return None
            
            # Get content (summary or description)
            content = entry.get('summary', '')
            if not content:
                content = entry.get('description', '')
            
            # Clean HTML tags from content
            content = self._clean_html(content).strip()
            
            if not content or len(content) < 30:
                return None
            
            # Get URL
            url = entry.get('link', '')
            if not url:
                return None
            
            # Parse date
            published_at = self._parse_date(entry)
            
            # Get source name
            source_name = self.sources[source_key]['name']
            
            article = {
                'title': title,
                'content': content,
                'source': source_name,
                'url': url,
                'published_at': published_at,
                'fetched_via': 'rss',
                'category': 'general'
            }
            
            return article
        
        except Exception as e:
            logger.error(f"[RSS] Error parsing entry: {str(e)}")
            return None
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        # Remove HTML tags
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', text)
        # Decode HTML entities
        import html
        text = html.unescape(text)
        return text.strip()
    
    def _parse_date(self, entry: dict) -> str:
        """
        Parse date from RSS entry.
        Handles various date formats.
        
        Args:
            entry: RSS entry dict
        
        Returns:
            ISO format date string
        """
        try:
            # Try published date first
            date_str = entry.get('published') or entry.get('updated')
            
            if not date_str:
                return datetime.now().isoformat()
            
            # Parse using dateutil (handles most formats)
            parsed_date = dateutil_parser.parse(date_str)
            return parsed_date.isoformat()
        
        except Exception as e:
            logger.warning(f"[RSS] Date parsing failed: {str(e)}, using current time")
            return datetime.now().isoformat()
    
    def fetch_topic_from_all_sources(self, topic: str, max_per_source: int = 3) -> Dict:
        """
        Fetch articles for a topic from all configured RSS sources.
        
        Args:
            topic: Topic to search for
            max_per_source: Max articles per source
        
        Returns:
            Dict with results by source and aggregated stats
        """
        results = {}
        total_found = 0
        total_failed = 0
        
        # Parse topic into keywords
        keywords = [kw.strip() for kw in topic.split() if len(kw.strip()) > 2]
        if not keywords:
            keywords = [topic]
        
        logger.info(f"[RSS] Fetching topic '{topic}' from all sources, keywords: {keywords}")
        
        # Fetch from each source
        for source_key in self.sources.keys():
            try:
                articles = self.fetch_from_source(source_key, keywords, max_per_source)
                
                if articles:
                    results[self.sources[source_key]['name']] = articles
                    total_found += len(articles)
                    logger.info(f"[RSS] {source_key}: {len(articles)} articles")
                
            except Exception as e:
                logger.error(f"[RSS] Failed to fetch from {source_key}: {str(e)}")
                total_failed += 1
        
        return {
            'results': results,
            'total_found': total_found,
            'sources_attempted': len(self.sources),
            'sources_failed': total_failed,
            'sources_succeeded': len(self.sources) - total_failed
        }
    
    def get_latest_from_all_sources(self, max_per_source: int = 3) -> Dict:
        """
        Get latest articles from all RSS sources (without keyword filtering).
        
        Args:
            max_per_source: Max articles per source
        
        Returns:
            Dict with latest articles by source
        """
        results = {}
        
        logger.info(f"[RSS] Fetching latest articles from all sources")
        
        for source_key in self.sources.keys():
            try:
                # Use empty keywords to get all articles
                articles = self.fetch_from_source(source_key, [], max_per_source)
                
                if articles:
                    results[self.sources[source_key]['name']] = articles
                    logger.info(f"[RSS] {source_key}: {len(articles)} latest articles")
                
            except Exception as e:
                logger.error(f"[RSS] Failed to fetch latest from {source_key}: {str(e)}")
        
        return {
            'results': results,
            'total_found': sum(len(articles) for articles in results.values())
        }
