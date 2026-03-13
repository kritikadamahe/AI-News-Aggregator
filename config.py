"""
config.py - Application Configuration
======================================
All settings and constants for the application.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Storage file paths
ARTICLES_FILE = str(DATA_DIR / 'articles.json')
QUIZZES_FILE = str(DATA_DIR / 'quizzes.json')
CHAT_HISTORY_FILE = str(DATA_DIR / 'chat_history.json')

# Cache settings
ENABLE_CACHE = True
CACHE_MAX_SIZE = 1000

# Session settings
SESSION_MAX_AGE_HOURS = 24
MAX_CHAT_HISTORY = 20

# API settings (loaded from .env)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-change-me")

# API URLs
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
NEWSAPI_BASE_URL = "https://newsapi.org/v2"

# News fetching settings
NEWS_FETCH_LIMIT = 10
SUPPORTED_CATEGORIES = [
    'business', 'entertainment', 'general', 
    'health', 'science', 'sports', 'technology'
]
SUPPORTED_COUNTRIES = ['us', 'gb', 'in', 'ca', 'au']

# Quiz settings
DEFAULT_MCQ_COUNT = 5
DEFAULT_FLASHCARD_COUNT = 5

# AI Model settings
SUMMARY_MODEL = "meta-llama/llama-3.1-8b-instruct"
SUMMARY_TEMPERATURE = 0.25
SUMMARY_MAX_TOKENS = 4000

CHAT_MODEL = "meta-llama/llama-3.1-8b-instruct"
CHAT_TEMPERATURE = 0.3
CHAT_MAX_TOKENS = 1000

QUIZ_MODEL = "meta-llama/llama-3.1-8b-instruct"
QUIZ_TEMPERATURE = 0.3
QUIZ_MAX_TOKENS = 2000

# File upload settings
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
MAX_FILE_SIZE_MB = 10

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = 'app.log'


# ============================================================================
# RSS FEED CONFIGURATION FOR MULTI-SOURCE NEWS FETCHING
# ============================================================================

RSS_SOURCES = {
    'the_hindu': {
        'name': 'The Hindu',
        'rss_urls': {
            'national': 'https://www.thehindu.com/news/national/?service=rss',
            'business': 'https://www.thehindu.com/business/?service=rss',
            'tech': 'https://www.thehindu.com/sci-tech/?service=rss'
        },
        'bias': 'center-left',
        'description': 'Major Indian English daily newspaper'
    },
    
    'times_of_india': {
        'name': 'Times of India',
        'rss_urls': {
            'top': 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',
            'india': 'https://timesofindia.indiatimes.com/rssfeeds/1012048734.cms',
            'tech': 'https://timesofindia.indiatimes.com/tech/rss.cms'
        },
        'bias': 'center',
        'description': 'Leading English-language newspaper in India'
    },
    
    'indian_express': {
        'name': 'Indian Express',
        'rss_urls': {
            'india': 'https://feeds.indianexpress.com/feeds/india.xml',
            'tech': 'https://feeds.indianexpress.com/feeds/technology.xml',
            'opinion': 'https://feeds.indianexpress.com/feeds/opinion.xml'
        },
        'bias': 'center-right',
        'description': 'Premium news and analysis from Indian Express'
    },
    
    'ndtv': {
        'name': 'NDTV',
        'rss_urls': {
            'latest': 'https://feeds.ndtv.com/ndtvnews-latest.xml',
            'india': 'https://feeds.ndtv.com/ndtv-india-news.xml',
            'tech': 'https://feeds.ndtv.com/ndtv-tech.xml'
        },
        'bias': 'center',
        'description': 'NDTV News - India\'s largest news network'
    },
    
    'the_wire': {
        'name': 'The Wire',
        'rss_urls': {
            'latest': 'https://feeds.thewire.in/thewire-latest.xml',
            'tech': 'https://feeds.thewire.in/tech.xml',
            'opinions': 'https://feeds.thewire.in/opinions.xml'
        },
        'bias': 'left-leaning',
        'description': 'Independent news and opinion platform'
    },
    
    'scroll_in': {
        'name': 'Scroll.in',
        'rss_urls': {
            'latest': 'https://scroll.in/latest/feed.xml',
            'tech': 'https://scroll.in/tech/feed.xml',
            'india': 'https://scroll.in/india/feed.xml'
        },
        'bias': 'center-left',
        'description': 'News and opinion from Scroll.in'
    }
}

# RSS Configuration settings
RSS_CONFIG = {
    'timeout_per_feed': 10,  # seconds
    'max_articles_per_source': 5,  # articles per source when fetching
    'cache_duration': 3600,  # seconds (1 hour)
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
