"""
services/translator_service.py - Caching Wrapper for M2M100 Translation
=========================================================================
Integrates the 9-step translation pipeline with LRU cache management.
Handles Step 9: cache lookup/store operations.
"""

import hashlib
import logging
from typing import Dict, Optional
from config import TRANSLATION_ENABLED, TRANSLATION_CACHE_FILE, M2M100_LANG_CODES
from storage import TranslationCacheStorage
from services.translator_m2m100 import translate_summary as translate_text_m2m100

logger = logging.getLogger(__name__)

# Global cache instance
_cache = None


def get_cache() -> TranslationCacheStorage:
    """Get or initialize translation cache (singleton)."""
    global _cache
    
    if _cache is None:
        _cache = TranslationCacheStorage(TRANSLATION_CACHE_FILE)
    
    return _cache


def compute_cache_key(
    text: str,
    target_lang: str,
    entity_mode: str = "transliterate",
    model_name: str = "facebook/m2m100_418M"
) -> str:
    """
    Compute cache key from:
    - MD5 hash of input text
    - Target language
    - Entity mode
    - Model name
    """
    input_hash = hashlib.md5(text.encode()).hexdigest()
    key_material = f"{input_hash}:{target_lang}:{entity_mode}:{model_name}"
    cache_key = hashlib.md5(key_material.encode()).hexdigest()
    return cache_key


def translate_summary(
    summary_text: str,
    target_lang: str,
    article_id: int = None
) -> Dict:
    """
    Translate summary with cache integration (Step 9 of pipeline).
    
    Args:
        summary_text: English summary
        target_lang: Target language code (hi/mr/ta/te)
        article_id: Optional article ID for cache tracking
    
    Returns:
        {
            "translated_text": "...",
            "target_lang": "hi",
            "entity_count": N,
            "placeholders_used": N,
            "chunks": 1,
            "provider": "m2m100",
            "cached": True/False,
            "error": None
        }
    """
    if not TRANSLATION_ENABLED:
        return {
            "translated_text": None,
            "target_lang": target_lang,
            "cached": False,
            "error": "Translation feature disabled"
        }
    
    try:
        from config import TRANSLATION_MODEL_NAME
        
        # Compute cache key
        cache_key = compute_cache_key(
            summary_text,
            target_lang,
            entity_mode="transliterate",
            model_name=TRANSLATION_MODEL_NAME
        )
        
        # Check cache
        cache = get_cache()
        cached_entry = cache.get_by_key(cache_key)
        
        if cached_entry:
            print(f"[Translation] ✓ Cache HIT for {target_lang}")
            result = {
                "translated_text": cached_entry["translated_text"],
                "target_lang": target_lang,
                "entity_count": cached_entry.get("entity_count", 0),
                "placeholders_used": cached_entry.get("placeholders_used", 0),
                "chunks": cached_entry.get("chunks", 1),
                "provider": "m2m100",
                "cached": True,
                "error": None
            }
            return result
        
        print(f"[Translation] Cache MISS for {target_lang}, computing...")
        
        # Translate using pipeline
        result = translate_text_m2m100(
            summary_text,
            target_lang,
            article_id=article_id
        )
        
        # Store in cache
        if not result.get("error"):
            cache_entry = {
                "key": cache_key,
                "article_id": article_id,
                "target_lang": target_lang,
                "source_lang": "en",
                "input_hash": hashlib.md5(summary_text.encode()).hexdigest(),
                "translated_text": result["translated_text"],
                "entity_count": result.get("entity_count", 0),
                "placeholders_used": result.get("placeholders_used", 0),
                "chunks": result.get("chunks", 1),
                "entity_mode": "transliterate",
                "model_name": TRANSLATION_MODEL_NAME
            }
            cache.put(cache_entry)
            print(f"[Translation] ✓ Cached result for {target_lang}")
        
        result["cached"] = False
        return result
    
    except Exception as e:
        logger.error(f"[Translation Service] Error: {e}")
        return {
            "translated_text": None,
            "target_lang": target_lang,
            "cached": False,
            "error": str(e)
        }


def get_cache_stats() -> Dict:
    """Get translation cache statistics."""
    try:
        cache = get_cache()
        return cache.get_cache_stats()
    except Exception as e:
        logger.error(f"[Translation Service] Failed to get cache stats: {e}")
        return {}


def clear_cache_for_article(article_id: int) -> Dict:
    """Clear all cached translations for an article."""
    try:
        cache = get_cache()
        count = cache.clear_by_article(article_id)
        return {
            "success": True,
            "cleared_entries": count,
            "article_id": article_id
        }
    except Exception as e:
        logger.error(f"[Translation Service] Failed to clear cache: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def validate_language(lang: str) -> bool:
    """Validate that language is supported."""
    from config import SUPPORTED_TRANSLATION_LANGS
    return lang in SUPPORTED_TRANSLATION_LANGS
