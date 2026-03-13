"""
services/entity_extractor.py - Entity Extraction & Normalization
==================================================================
Extracts and normalizes entities from article text for relationship mapping.
Handles NER, canonicalization, and key phrase extraction.
"""

import spacy
from typing import List, Dict, Optional, Set
from collections import Counter
import hashlib
import re
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Extract entities and key phrases from article text.
    Normalizes entities for canonical matching (e.g., "PM Modi" = "Narendra Modi").
    """
    
    def __init__(self):
        """Initialize spaCy NLP model."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("[EntityExtractor] spaCy model loaded successfully")
        except OSError:
            logger.error("[EntityExtractor] spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract and normalize entities from text.
        
        Args:
            text: Article text to extract entities from
        
        Returns:
            List of entity dicts with canonical IDs
        """
        if not self.nlp or not text:
            return []
        
        try:
            doc = self.nlp(text[:10000])  # Limit to first 10k chars for performance
            entities = []
            seen_canonical = set()
            
            for ent in doc.ents:
                if ent.label_ not in ['PERSON', 'ORG', 'GPE', 'EVENT', 'PRODUCT']:
                    continue
                
                normalized = self.normalize_name(ent.text, ent.label_)
                canonical_id = self._generate_canonical_id(normalized['clean_name'], ent.label_)
                
                # Avoid duplicates
                if canonical_id in seen_canonical:
                    continue
                
                seen_canonical.add(canonical_id)
                
                entities.append({
                    'text': ent.text,
                    'type': ent.label_,
                    'canonical_id': canonical_id,
                    'clean_name': normalized['clean_name'],
                    'title_prefix': normalized['title_prefix'],
                    'span_start': ent.start_char,
                    'span_end': ent.end_char
                })
            
            logger.info(f"[EntityExtractor] Extracted {len(entities)} entities from text")
            return entities
        
        except Exception as e:
            logger.error(f"[EntityExtractor] Error extracting entities: {str(e)}")
            return []
    
    def normalize_name(self, name: str, entity_type: str) -> Dict:
        """
        Clean and standardize entity names.
        
        Args:
            name: Raw entity name from NER
            entity_type: Entity type (PERSON, ORG, etc.)
        
        Returns:
            Dict with clean_name, title_prefix, original_name
        """
        original = name
        title_prefix = ""
        
        # Remove honorifics for PERSON entities
        if entity_type == 'PERSON':
            honorifics = [
                r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sir|Madam)\s+',
                r'\b(Mr|Mrs|Ms|Dr|Prof)\s+'
            ]
            for pattern in honorifics:
                match = re.match(pattern, name, re.IGNORECASE)
                if match:
                    title_prefix = match.group(1)
                    name = name[match.end():].strip()
            
            # Common titles that appear after names
            titles = [
                r'\s+(PM|Prime Minister|President|Minister|CEO|CTO|CFO)',
                r'\s+\(([^)]+)\)$'  # Remove parenthetical notes
            ]
            for pattern in titles:
                match = re.search(pattern, name, re.IGNORECASE)
                if match and not title_prefix:
                    title_prefix = match.group(1)
                    name = name[:match.start()].strip()
        
        # Handle abbreviations
        replacements = {
            r'\bGovt\.?\b': 'Government',
            r'\bCo\.\b': 'Company',
            r'\bInc\.\b': '',
            r'\bLtd\.\b': '',
            r'\bCorp\.?\b': 'Corporation',
            r'\bU\.S\.\b': 'United States',
            r'\bU\.K\.\b': 'United Kingdom'
        }
        for abbrev, full in replacements.items():
            name = re.sub(abbrev, full, name, flags=re.IGNORECASE)
        
        # Standardize spacing
        name = re.sub(r'\s+', ' ', name).strip()
        
        return {
            'clean_name': name,
            'title_prefix': title_prefix,
            'original_name': original
        }
    
    def extract_key_phrases(self, text: str, n: int = 10) -> List[Dict]:
        """
        Extract important noun phrases for topic matching.
        
        Args:
            text: Article text
            n: Number of top phrases to return
        
        Returns:
            List of phrase dicts with scores
        """
        if not self.nlp or not text:
            return []
        
        try:
            doc = self.nlp(text)
            
            phrases = []
            phrase_scores = {}
            
            # Extract noun chunks
            for i, chunk in enumerate(doc.noun_chunks):
                # Filter: skip small phrases and pure stop words
                if len(chunk.text.split()) < 2 or chunk.text.lower() in ['it', 'this', 'that']:
                    continue
                
                text_lower = chunk.text.lower()
                if text_lower not in phrase_scores:
                    phrase_scores[text_lower] = 0
                
                # Score based on position (earlier = higher) and frequency
                position_score = (1.0 - (i / max(len(list(doc.noun_chunks)), 1))) * 10
                phrase_scores[text_lower] += position_score
            
            # Add frequency scoring
            phrase_freq = Counter(text_lower for chunk in doc.noun_chunks 
                                for text_lower in [chunk.text.lower()])
            for phrase, freq in phrase_freq.most_common():
                if phrase in phrase_scores:
                    phrase_scores[phrase] += freq * 2
            
            # Convert to list and sort
            for text, score in phrase_scores.items():
                phrases.append({
                    'text': text,
                    'score': round(score, 2)
                })
            
            # Sort by score and return top n
            phrases.sort(key=lambda x: x['score'], reverse=True)
            return phrases[:n]
        
        except Exception as e:
            logger.error(f"[EntityExtractor] Error extracting key phrases: {str(e)}")
            return []
    
    def extract_article_profile(self, article: Dict) -> Dict:
        """
        Build complete profile for relationship matching.
        
        Args:
            article: Article dict from storage
        
        Returns:
            Profile dict with entities, phrases, sentiment, etc.
        """
        try:
            text = article.get('content', '')
            title = article.get('title', '')
            
            # Combine title and content for better entity extraction
            full_text = f"{title}. {text}"
            
            # Extract entities and phrases
            entities = self.extract_entities(full_text)
            phrases = self.extract_key_phrases(full_text)
            
            # Calculate basic sentiment (using text length heuristic for now)
            # Can be enhanced with VADER or other tools
            sentiment = self._calculate_sentiment(text)
            
            profile = {
                'article_id': article.get('id'),
                'entities': entities,
                'key_phrases': phrases,
                'sentiment': sentiment,
                'category': article.get('category', 'general'),
                'published_at': article.get('published_at', datetime.now().isoformat()),
                'word_count': len(text.split()),
                'source': article.get('source', 'Unknown')
            }
            
            logger.info(f"[EntityExtractor] Profile created for article {article.get('id')}: "
                       f"{len(entities)} entities, {len(phrases)} phrases")
            
            return profile
        
        except Exception as e:
            logger.error(f"[EntityExtractor] Error creating profile: {str(e)}")
            return {
                'article_id': article.get('id'),
                'entities': [],
                'key_phrases': [],
                'sentiment': 0.0,
                'category': article.get('category', 'general'),
                'published_at': article.get('published_at', datetime.now().isoformat()),
                'word_count': 0,
                'source': article.get('source', 'Unknown')
            }
    
    def _generate_canonical_id(self, name: str, entity_type: str) -> str:
        """
        Generate canonical ID for entity (used for matching).
        
        Uses hash to ensure "Modi", "PM Modi", "Narendra Modi" all map to same ID.
        
        Args:
            name: Cleaned entity name
            entity_type: Entity type
        
        Returns:
            Canonical ID string
        """
        # Normalize for hashing: lowercase, remove extra spaces
        normalized = name.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Generate hash
        hash_obj = hashlib.md5(normalized.encode())
        hash_hex = hash_obj.hexdigest()[:6]
        
        return f"{entity_type}_{hash_hex}"
    
    def _calculate_sentiment(self, text: str) -> float:
        """
        Basic sentiment calculation (0.0 to 1.0).
        Can be enhanced with VADER or other tools.
        
        Args:
            text: Text to analyze
        
        Returns:
            Sentiment score (0.0 = negative, 0.5 = neutral, 1.0 = positive)
        """
        try:
            # Simple heuristic: count positive/negative words
            positive_words = {
                'great', 'good', 'excellent', 'amazing', 'wonderful', 'fantastic',
                'success', 'win', 'profit', 'growth', 'increase', 'boost',
                'approved', 'happy', 'pleased', 'positive', 'strong'
            }
            negative_words = {
                'bad', 'terrible', 'awful', 'poor', 'fail', 'loss', 'crisis',
                'decline', 'decrease', 'rejected', 'sad', 'concerns', 'issue',
                'problem', 'weak', 'negative', 'worst'
            }
            
            text_lower = text.lower()
            words = text_lower.split()
            
            positive_count = sum(1 for w in words if w.strip('.,!?;:') in positive_words)
            negative_count = sum(1 for w in words if w.strip('.,!?;:') in negative_words)
            
            total = positive_count + negative_count
            if total == 0:
                return 0.5  # Neutral
            
            sentiment = (positive_count - negative_count) / (2 * total) + 0.5
            return max(0.0, min(1.0, sentiment))  # Clamp to 0-1
        
        except Exception as e:
            logger.error(f"[EntityExtractor] Error calculating sentiment: {str(e)}")
            return 0.5  # Default to neutral
