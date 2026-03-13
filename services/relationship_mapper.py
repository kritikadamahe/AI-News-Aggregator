"""
services/relationship_mapper.py - Article Relationship Calculation & Mapping
=============================================================================
Calculates similarity between articles and builds relationship graphs.
Combines entity overlap, phrase matching, sentiment, temporal, and category.
"""

from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
import logging
from services.entity_extractor import EntityExtractor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RelationshipMapper:
    """
    Calculate relationships between articles and build relationship graphs.
    """
    
    def __init__(self, storage=None):
        """
        Initialize relationship mapper.
        
        Args:
            storage: ArticleStorage instance (optional for lazy initialization)
        """
        self.entity_extractor = EntityExtractor()
        self.storage = storage
        self.entity_index = {}
        self.profile_cache = {}
        logger.info("[RelationshipMapper] Initialized")
    
    def set_storage(self, storage):
        """Set storage instance for retrieving articles."""
        self.storage = storage
    
    def get_article_profile(self, article_id: int) -> Optional[Dict]:
        """
        Get or create profile for article.
        
        Args:
            article_id: Article ID
        
        Returns:
            Article profile dict
        """
        # Check cache first
        if article_id in self.profile_cache:
            return self.profile_cache[article_id]
        
        if not self.storage:
            logger.warning(f"[RelationshipMapper] No storage set for article {article_id}")
            return None
        
        try:
            article = self.storage.get_by_id(article_id)
            if not article:
                return None
            
            # Use existing entities if available, otherwise extract
            if 'entities' in article and article['entities']:
                entities = article['entities']
                key_phrases = article.get('key_phrases', [])
            else:
                profile = self.entity_extractor.extract_article_profile(article)
                entities = profile['entities']
                key_phrases = profile['key_phrases']
            
            profile = {
                'article_id': article_id,
                'entities': entities,
                'key_phrases': key_phrases,
                'sentiment': article.get('sentiment', 0.5),
                'category': article.get('category', 'general'),
                'published_at': self._parse_date(article.get('published_at', datetime.now().isoformat())),
                'word_count': len(article.get('content', '').split()),
                'source': article.get('source', 'Unknown'),
                'title': article.get('title', '')
            }
            
            # Cache it
            self.profile_cache[article_id] = profile
            return profile
        
        except Exception as e:
            logger.error(f"[RelationshipMapper] Error getting profile for {article_id}: {str(e)}")
            return None
    
    def calculate_similarity(self, profile1: Dict, profile2: Dict) -> Dict:
        """
        Calculate multi-dimensional similarity score (0-100).
        
        Args:
            profile1: First article profile
            profile2: Second article profile
        
        Returns:
            Similarity dict with total_score, breakdown, shared entities/phrases
        """
        try:
            scores = {}
            
            # 1. Entity overlap (40% weight)
            entities1 = set(e['canonical_id'] for e in profile1.get('entities', []))
            entities2 = set(e['canonical_id'] for e in profile2.get('entities', []))
            shared_entities = entities1 & entities2
            all_entities = entities1 | entities2
            
            if all_entities:
                scores['entity'] = (len(shared_entities) / len(all_entities)) * 100
            else:
                scores['entity'] = 0
            
            # 2. Key phrase overlap (25% weight)
            phrases1 = set(p['text'].lower() for p in profile1.get('key_phrases', []))
            phrases2 = set(p['text'].lower() for p in profile2.get('key_phrases', []))
            shared_phrases = phrases1 & phrases2
            
            # Jaccard similarity for phrases
            if phrases1 or phrases2:
                scores['phrase'] = (len(shared_phrases) / max(len(phrases1 | phrases2), 1)) * 25
            else:
                scores['phrase'] = 0
            
            # 3. Sentiment alignment (15% weight)
            sentiment_diff = abs(profile1.get('sentiment', 0.5) - profile2.get('sentiment', 0.5))
            scores['sentiment'] = max(0, 15 - (sentiment_diff * 15))
            
            # 4. Temporal proximity (10% weight)
            try:
                date1 = profile1.get('published_at')
                date2 = profile2.get('published_at')
                if isinstance(date1, str):
                    date1 = self._parse_date(date1)
                if isinstance(date2, str):
                    date2 = self._parse_date(date2)
                
                days_diff = abs((date1 - date2).days) if date1 and date2 else 100
                scores['temporal'] = max(0, 10 - (days_diff * 0.2))
            except:
                scores['temporal'] = 5
            
            # 5. Category match (10% weight)
            scores['category'] = 10 if profile1.get('category') == profile2.get('category') else 0
            
            # Weighted total
            total_score = (
                scores.get('entity', 0) * 0.40 +
                scores.get('phrase', 0) * 0.25 +
                scores.get('sentiment', 0) * 0.15 +
                scores.get('temporal', 0) * 0.10 +
                scores.get('category', 0) * 0.10
            )
            
            # Get entity objects for shared_entities
            shared_entity_ids = set(e['canonical_id'] for e in profile1.get('entities', []))
            shared_entity_ids &= set(e['canonical_id'] for e in profile2.get('entities', []))
            
            shared_entity_objects = []
            for entity in profile1.get('entities', []):
                if entity['canonical_id'] in shared_entity_ids:
                    shared_entity_objects.append({
                        'text': entity['text'],
                        'type': entity['type'],
                        'canonical_id': entity['canonical_id']
                    })
            
            return {
                'total_score': round(total_score, 2),
                'breakdown': {k: round(v, 2) for k, v in scores.items()},
                'shared_entities': shared_entity_objects,
                'shared_phrases': list(shared_phrases)
            }
        
        except Exception as e:
            logger.error(f"[RelationshipMapper] Error calculating similarity: {str(e)}")
            return {
                'total_score': 0,
                'breakdown': {'entity': 0, 'phrase': 0, 'sentiment': 0, 'temporal': 0, 'category': 0},
                'shared_entities': [],
                'shared_phrases': []
            }
    
    def find_related_articles(self, article_id: int, min_score: float = 60, 
                             max_results: int = 5) -> List[Dict]:
        """
        Find articles related to given article.
        
        Args:
            article_id: Target article ID
            min_score: Minimum similarity score to include
            max_results: Maximum number of results
        
        Returns:
            List of relationship dicts
        """
        if not self.storage:
            logger.warning("[RelationshipMapper] No storage configured")
            return []
        
        try:
            # Get target article profile
            target = self.get_article_profile(article_id)
            if not target:
                return []
            
            # Candidate selection: articles sharing at least 1 entity
            candidate_ids = set()
            for entity in target.get('entities', []):
                # Find other articles with same canonical entity
                all_articles = self.storage.read_all()
                for article in all_articles:
                    if article.get('id') == article_id:
                        continue
                    
                    article_entities = article.get('entities', [])
                    if not article_entities:
                        # Extract if not present
                        profile = self.get_article_profile(article.get('id'))
                        article_entities = profile.get('entities', []) if profile else []
                    
                    for ae in article_entities:
                        if ae.get('canonical_id') == entity.get('canonical_id'):
                            candidate_ids.add(article.get('id'))
                            break
            
            # If no entity matches, use all other articles
            if not candidate_ids:
                all_articles = self.storage.read_all()
                candidate_ids = {a['id'] for a in all_articles if a['id'] != article_id}
            
            # Calculate similarity for candidates
            relationships = []
            for cand_id in candidate_ids:
                candidate = self.get_article_profile(cand_id)
                if not candidate:
                    continue
                
                similarity = self.calculate_similarity(target, candidate)
                
                if similarity['total_score'] >= min_score:
                    reason = self._generate_reason(similarity)
                    relationships.append({
                        'target_id': article_id,
                        'related_id': cand_id,
                        'score': similarity['total_score'],
                        'breakdown': similarity['breakdown'],
                        'shared_entities': similarity['shared_entities'],
                        'shared_phrases': similarity['shared_phrases'],
                        'reason': reason
                    })
            
            # Sort by score, return top max_results
            relationships.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"[RelationshipMapper] Found {len(relationships)} related articles for {article_id}")
            return relationships[:max_results]
        
        except Exception as e:
            logger.error(f"[RelationshipMapper] Error finding related articles: {str(e)}")
            return []
    
    def build_relationship_graph(self) -> Dict:
        """
        Build complete graph of all article relationships.
        
        Returns:
            Dict with nodes and edges for visualization
        """
        if not self.storage:
            logger.warning("[RelationshipMapper] No storage configured")
            return {'nodes': [], 'edges': []}
        
        try:
            articles = self.storage.read_all()
            if not articles:
                return {'nodes': [], 'edges': []}
            
            nodes = []
            edges = []
            edges_set = set()  # Avoid duplicate edges
            
            for article in articles:
                nodes.append({
                    'id': article['id'],
                    'title': (article.get('title', 'Unknown')[:40] + '...') 
                            if len(article.get('title', '')) > 40 
                            else article.get('title', 'Unknown'),
                    'source': article.get('source', 'Unknown'),
                    'category': article.get('category', 'general'),
                    'published': article.get('published_at', '')
                })
                
                # Find relationships for this article
                rels = self.find_related_articles(
                    article['id'],
                    min_score=50,
                    max_results=3
                )
                
                for rel in rels:
                    # Create edge key (order-agnostic)
                    edge_key = tuple(sorted([rel['target_id'], rel['related_id']]))
                    
                    # Avoid duplicate edges
                    if edge_key not in edges_set:
                        edges_set.add(edge_key)
                        edges.append({
                            'source': rel['target_id'],
                            'target': rel['related_id'],
                            'weight': min(rel['score'] / 100.0, 1.0),  # Normalize 0-1
                            'reason': rel['reason']
                        })
            
            logger.info(f"[RelationshipMapper] Built graph: {len(nodes)} nodes, {len(edges)} edges")
            return {'nodes': nodes, 'edges': edges}
        
        except Exception as e:
            logger.error(f"[RelationshipMapper] Error building relationship graph: {str(e)}")
            return {'nodes': [], 'edges': []}
    
    def _generate_reason(self, similarity_data: Dict) -> str:
        """
        Generate human-readable explanation of relationship.
        
        Args:
            similarity_data: Similarity calculation result
        
        Returns:
            Human-readable reason string
        """
        reasons = []
        breakdown = similarity_data.get('breakdown', {})
        shared_entities = similarity_data.get('shared_entities', [])
        shared_phrases = similarity_data.get('shared_phrases', [])
        
        # Entity match
        if shared_entities and breakdown.get('entity', 0) > 30:
            entity_names = ', '.join(e['text'] for e in shared_entities[:2])
            reasons.append(f"Shares {entity_names}")
        
        # Phrase match
        if shared_phrases and breakdown.get('phrase', 0) > 15:
            reasons.append("Similar topics")
        
        # Temporal proximity
        if breakdown.get('temporal', 0) > 5:
            reasons.append("Published near same time")
        
        # Category match
        if breakdown.get('category', 0) > 5:
            reasons.append("Same category")
        
        return "; ".join(reasons) if reasons else "Related coverage"
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse ISO format date string.
        
        Args:
            date_str: ISO format date string
        
        Returns:
            datetime object
        """
        try:
            if isinstance(date_str, datetime):
                return date_str
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return datetime.now()
