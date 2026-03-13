"""
storage.py - Hybrid Storage System (JSON + In-Memory Cache)
============================================================
Provides fast, persistent storage without needing a database.
Perfect for RAG implementation with instant context retrieval.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from threading import Lock
import hashlib


class HybridStorage:
    """
    Base hybrid storage class with JSON persistence + in-memory caching.
    Thread-safe for concurrent access.
    """
    
    def __init__(self, filename: str, cache_enabled: bool = True):
        self.filename = filename
        self.cache_enabled = cache_enabled
        self._cache = None
        self._cache_lock = Lock()
        self.ensure_file_exists()
    
    def ensure_file_exists(self):
        """Create directory and file if they don't exist."""
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump([], f)
    
    def _load_to_cache(self):
        """Load data from JSON into memory."""
        with self._cache_lock:
            with open(self.filename, 'r') as f:
                self._cache = json.load(f)
    
    def _save_from_cache(self):
        """Save cache to JSON file."""
        with self._cache_lock:
            with open(self.filename, 'w') as f:
                json.dump(self._cache, f, indent=2)
    
    def invalidate_cache(self):
        """Clear cache, forcing reload."""
        with self._cache_lock:
            self._cache = None
    
    def read_all(self) -> List[Dict]:
        """Read all items (uses cache if available)."""
        if self.cache_enabled and self._cache is not None:
            return self._cache.copy()
        
        try:
            with open(self.filename, 'r') as f:
                content = f.read().strip()
                if not content:  # File is empty
                    print(f"[WARNING] {self.filename} is empty, initializing with default data")
                    data = []
                    self.write_all(data)
                else:
                    data = json.loads(content)
        except FileNotFoundError:
            print(f"[WARNING] {self.filename} not found, creating new file")
            data = []
            self.write_all(data)
        except json.JSONDecodeError as e:
            print(f"[WARNING] {self.filename} contains invalid JSON: {e}, reinitializing")
            data = []
            self.write_all(data)
        except Exception as e:
            print(f"[ERROR] Error reading {self.filename}: {e}")
            data = []
        
        if self.cache_enabled:
            with self._cache_lock:
                self._cache = data
        
        return data
    
    def write_all(self, data: List[Dict]):
        """Write all items to storage."""
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        if self.cache_enabled:
            with self._cache_lock:
                self._cache = data.copy()
    
    def add(self, item: Dict) -> Dict:
        """Add a new item."""
        data = self.read_all()
        item['id'] = len(data) + 1
        item['created_at'] = datetime.now().isoformat()
        data.append(item)
        self.write_all(data)
        return item
    
    def get_by_id(self, item_id: int) -> Optional[Dict]:
        """Get item by ID."""
        data = self.read_all()
        return next((item for item in data if item['id'] == item_id), None)
    
    def update(self, item_id: int, updates: Dict) -> bool:
        """Update an existing item."""
        data = self.read_all()
        updated = False
        
        for item in data:
            if item['id'] == item_id:
                item.update(updates)
                item['updated_at'] = datetime.now().isoformat()
                updated = True
                break
        
        if updated:
            self.write_all(data)
        return updated
    
    def delete(self, item_id: int) -> bool:
        """Delete an item by ID."""
        data = self.read_all()
        original_length = len(data)
        data = [item for item in data if item['id'] != item_id]
        
        if len(data) < original_length:
            self.write_all(data)
            return True
        return False
    
    def search(self, **filters) -> List[Dict]:
        """Search items by filters."""
        data = self.read_all()
        results = data
        
        for key, value in filters.items():
            results = [item for item in results if item.get(key) == value]
        
        return results
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get most recent items."""
        data = self.read_all()
        sorted_data = sorted(data, key=lambda x: x.get('created_at', ''), reverse=True)
        return sorted_data[:limit]


class ArticleStorage(HybridStorage):
    """Specialized storage for articles with deduplication."""
    
    def add_article(self, title: str, content: str, source: str, 
                    url: str = None, category: str = None, 
                    summary: str = None) -> Dict:
        """Add article with automatic deduplication."""
        # Generate content hash for deduplication
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Check for duplicates
        existing = self.search(content_hash=content_hash)
        if existing:
            return existing[0]
        
        article = {
            'title': title,
            'content': content,
            'source': source,
            'url': url,
            'category': category,
            'summary': summary,
            'content_hash': content_hash,
            'word_count': len(content.split()),
            'analysis_results': None  # Misinformation/bias analysis (populated later)
        }
        
        return self.add(article)

    def update_analysis(self, article_id: int, analysis_results: Dict) -> bool:
        """Store misinformation/bias analysis results for an article."""
        return self.update(article_id, {'analysis_results': analysis_results})
    
    def get_article_content(self, article_id: int) -> Optional[str]:
        """Get just the content text."""
        article = self.get_by_id(article_id)
        return article.get('content') if article else None
    
    def search_by_keywords(self, keywords: List[str]) -> List[Dict]:
        """Search by keywords in title or content."""
        data = self.read_all()
        results = []
        
        for article in data:
            text = f"{article.get('title', '')} {article.get('content', '')}".lower()
            if any(kw.lower() in text for kw in keywords):
                results.append(article)
        
        return results
    
    def get_by_category(self, category: str) -> List[Dict]:
        """Get articles by category."""
        return self.search(category=category)


class ChatHistoryStorage(HybridStorage):
    """Storage for chat conversations."""
    
    def add_message(self, article_id: int, user_message: str, 
                    ai_response: str, session_id: str = None) -> Dict:
        """Add a chat message."""
        message = {
            'article_id': article_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }
        return self.add(message)
    
    def get_conversation(self, article_id: int, limit: int = 20) -> List[Dict]:
        """Get conversation for an article."""
        messages = self.search(article_id=article_id)
        sorted_messages = sorted(messages, key=lambda x: x.get('timestamp', ''))
        return sorted_messages[-limit:]
    
    def clear_conversation(self, article_id: int) -> int:
        """Clear all messages for an article."""
        data = self.read_all()
        original_count = len(data)
        data = [msg for msg in data if msg.get('article_id') != article_id]
        self.write_all(data)
        return original_count - len(data)


class QuizStorage(HybridStorage):
    """Storage for quizzes and flashcards."""
    
    def add_quiz(self, article_id: int, mcqs: List[Dict], 
                 flashcards: List[Dict]) -> Dict:
        """Add a quiz."""
        quiz = {
            'article_id': article_id,
            'mcqs': mcqs,
            'flashcards': flashcards,
            'num_questions': len(mcqs),
            'num_flashcards': len(flashcards)
        }
        return self.add(quiz)
    
    def get_quiz_by_article(self, article_id: int) -> Optional[Dict]:
        """Get quiz for an article."""
        quizzes = self.search(article_id=article_id)
        return quizzes[0] if quizzes else None


class ChatSessionManager:
    """
    Manages active chat sessions in memory for RAG.
    Each session maintains full article context.
    """
    
    def __init__(self):
        self.sessions = {}
        self._lock = Lock()
    
    def create_session(self, session_id: str, article_id: int, 
                      article_content: str):
        """Create new chat session with article context."""
        with self._lock:
            self.sessions[session_id] = {
                'article_id': article_id,
                'article_content': article_content,
                'messages': [],
                'created_at': datetime.now().isoformat()
            }
    
    def add_message(self, session_id: str, role: str, content: str):
        """Add message to session."""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id]['messages'].append({
                    'role': role,
                    'content': content,
                    'timestamp': datetime.now().isoformat()
                })
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data."""
        return self.sessions.get(session_id)
    
    def get_context(self, session_id: str, max_messages: int = 10) -> Optional[Dict]:
        """Get RAG context for session."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        return {
            'article_content': session['article_content'],
            'messages': session['messages'][-max_messages:]
        }
    
    def clear_session(self, session_id: str):
        """Delete a session."""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove old sessions."""
        from datetime import timedelta
        
        with self._lock:
            current_time = datetime.now()
            to_remove = []
            
            for sid, session in self.sessions.items():
                created = datetime.fromisoformat(session['created_at'])
                if current_time - created > timedelta(hours=max_age_hours):
                    to_remove.append(sid)
            
            for sid in to_remove:
                del self.sessions[sid]
            
            return len(to_remove)
