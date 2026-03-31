"""
services/fetch_news.py - News Fetching from Multiple Sources (BeautifulSoup Version)
"""

import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import re
import validators
import time
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
    """Extract transcripts from YouTube videos with robust fallback strategy.
    
    Fallback Strategy (3 layers):
    1. youtube-transcript-api with retry (specified languages)
    2. youtube-transcript-api (any available language)
    3. youtube-transcript-api (auto-generated captions)
    """
    
    def __init__(self, max_retries: int = 3, timeout: int = 10):
        """Initialize YouTubeTranscriptExtractor with retry and timeout configuration."""
        self.max_retries = max_retries
        self.timeout = timeout
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        # Comprehensive regex patterns for different YouTube URL formats
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'youtu\.be/([a-zA-Z0-9_-]+)',
            r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
            r'youtube\.com/v/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                # Validate that video_id is exactly 11 characters (YouTube standard)
                if len(video_id) == 11:
                    print(f"[YouTube] Extracted video ID: {video_id}")
                    return video_id
        
        return None
    
    def get_transcript(self, video_url: str, languages: List[str] = None) -> Optional[dict]:
        """Get transcript from YouTube video with robust fallback."""
        if languages is None:
            languages = ['en', 'en-US', 'en-GB', 'hi', 'es', 'fr', 'de', 'pt', 'ja', 'zh-Hans', 'ar']
        
        video_id = self.extract_video_id(video_url)
        if not video_id:
            print(f"[YouTube] ERROR: Could not extract video ID from: {video_url}")
            return None
        
        print(f"[YouTube] Video ID: {video_id}")
        transcript_text = None
        
        # STRATEGY 1: Try specified languages with retry
        print(f"[YouTube] STRATEGY 1: Trying specified languages...")
        transcript_text = self._get_transcript_with_retry(video_id, languages)
        
        # STRATEGY 2: If that fails, try ANY available language
        if not transcript_text:
            print(f"[YouTube] STRATEGY 2: Trying any available language...")
            transcript_text = self._get_transcript_any_language(video_id)
        
        # STRATEGY 3: If that fails, try auto-generated captions
        #if not transcript_text:
        #    print(f"[YouTube] STRATEGY 3: Trying auto-generated captions...")
        #    transcript_text = self._get_autogenerated_transcript(video_id)
        
        # All strategies exhausted
        #if not transcript_text:
        #    print(f"[YouTube] ERROR: Could not fetch transcript in any format")
        #    return None
        # STRATEGY 3: If that fails, try auto-generated captions
        if not transcript_text:
            print(f"[YouTube] STRATEGY 3: Trying auto-generated captions...")
            transcript_text = self._get_autogenerated_transcript(video_id)

        # STRATEGY 4: Download audio and transcribe with Whisper
        if not transcript_text:
            print(f"[YouTube] STRATEGY 4: Trying Whisper transcription...")
            transcript_text = self._transcribe_with_whisper(video_id, video_url)

        # All strategies exhausted
        if not transcript_text:
            print(f"[YouTube] ERROR: Could not fetch transcript in any format")
            return None 
        title = self._get_video_title(video_id)
        
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
    
    def _get_transcript_with_retry(self, video_id: str, languages: List[str]) -> Optional[str]:
        """Get transcript with specified languages and retry logic."""
        for attempt in range(self.max_retries):
            try:
                print(f"[YouTube] Attempt {attempt + 1}/{self.max_retries}: Trying languages: {languages}")
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
                #transcript_text = ' '.join([t['text'] for t in transcript_list])
                transcript_text = ' '.join([t['text'] if isinstance(t, dict) else t.text for t in transcript_list])
                print(f"[YouTube] SUCCESS: Got {len(transcript_list)} segments")
                return transcript_text
            except Exception as e:
                error_msg = str(e).lower()
                # Don't retry for "no element found" XML errors - they indicate unavailable captions
                if 'no element found' in error_msg or 'xml' in error_msg:
                    print(f"[YouTube] Attempt {attempt + 1} failed: No captions available - {str(e)}")
                    return None  # Exit early, don't retry
                print(f"[YouTube] Attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
        
        return None
    
    def _get_transcript_any_language(self, video_id: str) -> Optional[str]:
        """Get transcript in ANY available language by trying all available transcripts."""
        try:
            print(f"[YouTube] Fetching available transcripts for video...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Get all available transcripts (both manual and auto-generated)
            all_transcripts = []
            
            # Try to get manually created transcripts
            try:
                manually_created = transcript_list.manually_created_transcripts
                if manually_created:
                    all_transcripts.extend(manually_created)
                    print(f"[YouTube] Found {len(manually_created)} manually created transcripts")
            except (AttributeError, TypeError):
                pass
            
            # Try to get auto-generated transcripts
            try:
                generated = transcript_list.generated_transcripts
                if generated:
                    all_transcripts.extend(generated)
                    print(f"[YouTube] Found {len(generated)} auto-generated transcripts")
            except (AttributeError, TypeError):
                pass
            
            # Try private attributes as fallback
            if not all_transcripts:
                try:
                    if hasattr(transcript_list, '_manually_created_transcripts'):
                        all_transcripts.extend(transcript_list._manually_created_transcripts)
                    if hasattr(transcript_list, '_generated_transcripts'):
                        all_transcripts.extend(transcript_list._generated_transcripts)
                except Exception:
                    pass
            
            # Fetch transcript from available transcripts
            if all_transcripts:
                print(f"[YouTube] Trying {len(all_transcripts)} available transcripts...")
                #for transcript in all_transcripts:
                #    try:
                #        fetched = transcript.fetch()
                #        #transcript_text = ' '.join([t['text'] for t in fetched])
                #        transcript_text = ' '.join([t['text'] if isinstance(t, dict) else t.text for t in fetched])
                #        if transcript_text and len(transcript_text) > 50:
                #            print(f"[YouTube] SUCCESS: Got transcript in {transcript.language}")
                #            return transcript_text
                #    except Exception as e:
                #        print(f"[YouTube] Failed to fetch {getattr(transcript, 'language', 'unknown')} language: {e}")
                #        continue
                for transcript in all_transcripts:
                    try:
                        fetched = transcript.fetch()
                        if isinstance(fetched, list):
                            if len(fetched) > 0 and isinstance(fetched[0], str):
                                transcript_text = ' '.join(fetched)
                            else:
                                transcript_text = ' '.join([t['text'] if isinstance(t, dict) else t.text for t in fetched])
                        else:
                            transcript_text = str(fetched)
                        if transcript_text and len(transcript_text) > 50:
                            print(f"[YouTube] SUCCESS: Got transcript in {getattr(transcript, 'language', 'unknown')}")
                            return transcript_text
                    except Exception as e:
                        print(f"[YouTube] Failed to fetch {getattr(transcript, 'language', 'unknown')} language: {e}")
                        continue
            else:
                print(f"[YouTube] No available transcripts found")
        
        except Exception as e:
            print(f"[YouTube] Error listing transcripts: {e}")
        
        return None
    
    def _get_autogenerated_transcript(self, video_id: str) -> Optional[str]:
        """Get auto-generated captions as final fallback."""
        try:
            print(f"[YouTube] Attempting to fetch auto-generated captions...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try standard property
            try:
                generated = getattr(transcript_list, 'generated_transcripts', None)
                if generated and len(generated) > 0:
                    transcript = generated[0]
                    fetched = transcript.fetch()
                    #transcript_text = ' '.join([t['text'] for t in fetched])
                    transcript_text = ' '.join([t['text'] if isinstance(t, dict) else t.text for t in fetched])
                    print(f"[YouTube] SUCCESS: Got auto-generated captions")
                    return transcript_text
            except Exception:
                pass
            
            # Try private attribute
            try:
                if hasattr(transcript_list, '_generated_transcripts'):
                    generated = transcript_list._generated_transcripts
                    if generated and len(generated) > 0:
                        transcript = generated[0]
                        fetched = transcript.fetch()
                        transcript_text = ' '.join([t['text'] for t in fetched])
                        print(f"[YouTube] SUCCESS: Got auto-generated captions")
                        return transcript_text
            except Exception:
                pass
        
        except Exception as e:
            print(f"[YouTube] Auto-generated captions failed: {e}")
        
        return None
    
    def _transcribe_with_whisper(self, video_id: str, video_url: str) -> Optional[str]:
        """Download audio and transcribe using OpenAI Whisper."""
        import tempfile
        import os
        try:
            import yt_dlp
            import whisper
        except ImportError:
            print("[YouTube] yt-dlp or whisper not installed")
            return None

        tmp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(tmp_dir, f"{video_id}.mp3")

        try:
            print(f"[YouTube] Downloading audio for {video_id}...")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(tmp_dir, f"{video_id}.%(ext)s"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            if not os.path.exists(audio_path):
                print("[YouTube] Audio download failed")
                return None

            print(f"[YouTube] Audio downloaded. Transcribing with Whisper...")
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            transcript_text = result.get("text", "").strip()

            if transcript_text:
                print(f"[YouTube] Whisper transcription SUCCESS: {len(transcript_text)} chars")
                return transcript_text
            else:
                print("[YouTube] Whisper returned empty transcript")
                return None

        except Exception as e:
            print(f"[YouTube] Whisper transcription failed: {e}")
            return None

        finally:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                os.rmdir(tmp_dir)
            except Exception:
                pass

    def _get_video_title(self, video_id: str) -> Optional[str]:
        """Get video title from YouTube via oEmbed API with retry logic."""
        for attempt in range(2):
            try:
                response = requests.get(
                    f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    title = data.get('title')
                    print(f"[YouTube] Title fetched: {title}")
                    return title
            except Exception as e:
                print(f"[YouTube] Title fetch attempt {attempt + 1} failed: {str(e)}")
        
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
