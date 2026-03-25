"""
misinformation_detector.py - Hybrid Misinformation & Bias Detection System
============================================================================
Combines strong rule-based linguistic analysis with pre-trained NLP models
to detect potential misinformation, bias, and manipulative writing patterns.

NLP Techniques Used (Mapped to Syllabus Concepts):
----------------------------------------------------
1. POS Tagging        - spaCy assigns Part-of-Speech tags to each token
2. Dependency Parsing - spaCy builds syntactic dependency trees per sentence
3. Named Entity Recognition (NER) - spaCy identifies PERSON, ORG, GPE entities
4. Sentiment Analysis - VADER lexicon-based sentiment scoring
5. Emotion Detection  - text2emotion for categorical emotion profiling
6. Phrase Matching    - spaCy PhraseMatcher for trigger phrase detection
7. Semantic Analysis  - Combining rule outputs with model scores

Approach: Hybrid (Rule-Based + Pre-Trained Models)
---------------------------------------------------
Rule-based analysis provides interpretable, deterministic checks for
passive voice, unattributed claims, hedging, and loaded language.
Pre-trained models (VADER, text2emotion) provide sentiment and emotion
profiling that complements rule-based flags.
"""

import re
import math
import hashlib
from typing import Dict, List, Optional, Tuple
from collections import Counter

# ============================================================================
# spaCy - Core NLP pipeline for POS tagging, dependency parsing, NER
# ============================================================================
try:
    import spacy
    from spacy.matcher import PhraseMatcher, Matcher
    SPACY_AVAILABLE = True
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("[Misinformation] WARNING: spaCy model not found")
        SPACY_AVAILABLE = False
        nlp = None
except ImportError:
    print("[Misinformation] WARNING: spaCy not installed. Misinformation detection disabled.")
    SPACY_AVAILABLE = False
    nlp = None
    PhraseMatcher = None
    Matcher = None

# ============================================================================
# VADER Sentiment Analyzer (NLTK) - Pre-trained lexicon-based model
# ============================================================================
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    import nltk
    # Ensure VADER lexicon is available
    try:
        nltk.data.find('sentiment/vader_lexicon.zip')
    except LookupError:
        nltk.download('vader_lexicon', quiet=True)
    vader_analyzer = SentimentIntensityAnalyzer()
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    vader_analyzer = None
    print("[MisinformationDetector] NLTK/VADER not available - sentiment analysis disabled")

# ============================================================================
# text2emotion - Pre-trained emotion detection model
# ============================================================================
try:
    import text2emotion as te
    TEXT2EMOTION_AVAILABLE = True
except ImportError:
    TEXT2EMOTION_AVAILABLE = False
    print("[MisinformationDetector] text2emotion not available - emotion profiling disabled")


# ============================================================================
# ANALYSIS CACHE - Avoids re-analyzing the same article content
# ============================================================================
_analysis_cache: Dict[str, Dict] = {}


class MisinformationDetector:
    """
    Hybrid Misinformation & Bias Detection System.
    
    Combines rule-based linguistic analysis (passive voice, unattributed claims,
    hedging, loaded language) with pre-trained models (VADER sentiment,
    text2emotion) to produce a composite reliability score.
    
    Usage:
        detector = MisinformationDetector()
        result = detector.analyze(title, content, source, category)
    """

    # ========================================================================
    # SCORING WEIGHTS (must sum to 1.0)
    # ========================================================================
    WEIGHTS = {
        'passive_voice':        0.15,   # 15% - Passive constructions hiding actors
        'unattributed_claims':  0.20,   # 20% - Claims without named sources
        'hedging':              0.10,   # 10% - Vague / uncertain language
        'emotional_language':   0.15,   # 15% - Fear, anger, urgency word density
        'sentiment':            0.10,   # 10% - Extreme VADER sentiment score
        'emotion_profile':      0.15,   # 15% - Fear+anger dominance (text2emotion)
        'missing_sources':      0.15,   # 15% - Quotes without named speakers
    }

    # ========================================================================
    # THRESHOLDS
    # ========================================================================
    PASSIVE_VOICE_THRESHOLD = 30        # % of sentences that are passive
    HEDGE_DENSITY_THRESHOLD = 5         # hedges per 100 words
    EMOTIONAL_WORD_THRESHOLD = 3.0      # % of total words in any emotion category
    SUPERLATIVE_THRESHOLD = 2           # max superlatives before flagging
    EXTREME_SENTIMENT_THRESHOLD = 0.6   # |compound| > 0.6 is extreme
    FEAR_ANGER_THRESHOLD = 50           # fear+anger combined > 50%

    # Short article word count - thresholds scale proportionally below this
    SHORT_ARTICLE_WORDS = 100

    # ========================================================================
    # TRIGGER PHRASES for unattributed claim detection
    # Uses spaCy PhraseMatcher for efficient multi-pattern matching
    # ========================================================================
    TRIGGER_PHRASES = [
        "experts say", "studies show", "people believe", "many claim",
        "critics argue", "analysts suggest", "sources report", "it is said",
        "some argue", "experts believe", "research shows", "reports indicate",
        "sources say", "officials say", "observers note", "insiders reveal",
        "experts warn", "analysts say", "many believe", "some experts",
        "according to sources", "it is believed", "it is reported",
        "widely reported", "some say", "many say"
    ]

    # ========================================================================
    # HEDGE WORDS & WEASEL PHRASES
    # ========================================================================
    HEDGE_WORDS = [
        "allegedly", "reportedly", "supposedly", "apparently", "seemingly",
        "perhaps", "maybe", "might", "could", "some say", "purportedly",
        "ostensibly", "conceivably", "presumedly", "questionably"
    ]

    WEASEL_PHRASES = [
        "many people", "some experts", "widely believed", "often considered",
        "generally thought", "it is thought", "commonly believed",
        "frequently cited", "widely assumed", "often said",
        "some observers", "certain analysts", "various sources",
        "unnamed sources", "anonymous officials"
    ]

    # ========================================================================
    # EMOTIONAL MANIPULATION WORD LISTS (by category)
    # ========================================================================
    FEAR_WORDS = [
        "devastating", "terrifying", "alarming", "crisis", "disaster",
        "nightmare", "catastrophic", "horrifying", "deadly", "fatal",
        "dangerous", "threat", "menace", "panic", "dread", "peril",
        "doom", "apocalyptic", "existential threat", "collapse",
        "destruction", "annihilation", "grave danger", "lethal",
        "chilling", "harrowing", "dire", "ominous", "sinister"
    ]

    ANGER_WORDS = [
        "outrageous", "disgusting", "shocking", "scandalous", "corrupt",
        "rigged", "infuriating", "shameful", "despicable", "treacherous",
        "betrayal", "atrocity", "abhorrent", "reprehensible", "heinous",
        "vile", "deplorable", "contemptible", "appalling", "grotesque",
        "unforgivable", "inexcusable"
    ]

    URGENCY_WORDS = [
        "immediately", "urgent", "critical", "emergency", "must act now",
        "before it's too late", "time is running out", "act now",
        "last chance", "breaking", "developing", "just in",
        "right now", "without delay", "at once", "dire need"
    ]

    SUPERLATIVE_PHRASES = [
        "worst ever", "greatest disaster", "biggest scandal",
        "most corrupt", "never before", "unprecedented crisis",
        "most dangerous", "largest ever", "best ever",
        "most horrific", "most devastating", "deadliest",
        "most shocking", "most outrageous", "most scandalous"
    ]

    # ========================================================================
    # LOADED LANGUAGE PAIRS: loaded_term -> neutral_alternative
    # Detects one-sided framing / bias in word choice
    # ========================================================================
    LOADED_NEGATIVE = {
        "mob": "protesters",
        "regime": "government",
        "propaganda": "information",
        "cronies": "associates",
        "scheme": "plan",
        "radical": "activist",
        "extremist": "advocate",
        "puppet": "ally",
        "thugs": "supporters",
        "tyranny": "authority",
        "dictator": "leader",
        "invasion": "intervention",
        "witch hunt": "investigation",
        "hoax": "claim",
        "brainwashing": "persuasion",
        "indoctrination": "education",
        "sham": "process",
        "fiasco": "situation",
        "debacle": "outcome",
    }

    LOADED_POSITIVE = {
        "landmark": "controversial",
        "reform": "change",
        "patriotic": "nationalist",
        "freedom fighter": "militant",
        "visionary": "ambitious",
        "hero": "participant",
        "crusade": "campaign",
        "liberation": "takeover",
        "breakthrough": "development",
        "triumph": "result",
    }

    # ========================================================================
    # COMMUNICATION VERBS (for quote-source verification)
    # spaCy dependency parsing: PERSON + VERB_OF_COMMUNICATION pattern
    # ========================================================================
    COMMUNICATION_VERBS = {
        "said", "stated", "announced", "claimed", "argued", "suggested",
        "warned", "confirmed", "denied", "explained", "revealed",
        "testified", "declared", "asserted", "noted", "added",
        "commented", "remarked", "mentioned", "reported", "told",
        "insisted", "emphasized", "stressed", "acknowledged",
        "conceded", "admitted", "contended", "maintained", "responded"
    }

    def __init__(self):
        """Initialize matchers and NLP components."""
        # -----------------------------------------------------------
        # PhraseMatcher: efficient multi-pattern matching using spaCy
        # This is the NLP technique of Phrase/Pattern Matching
        # -----------------------------------------------------------
        self.trigger_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        trigger_patterns = [nlp.make_doc(phrase) for phrase in self.TRIGGER_PHRASES]
        self.trigger_matcher.add("TRIGGER", trigger_patterns)

        self.hedge_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        hedge_patterns = [nlp.make_doc(w) for w in self.HEDGE_WORDS + self.WEASEL_PHRASES]
        self.hedge_matcher.add("HEDGE", hedge_patterns)

        self.superlative_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        sup_patterns = [nlp.make_doc(p) for p in self.SUPERLATIVE_PHRASES]
        self.superlative_matcher.add("SUPERLATIVE", sup_patterns)

    # ====================================================================
    # PUBLIC API
    # ====================================================================

    def analyze(self, title: str, content: str, source: str = "",
                category: str = "") -> Dict:
        """
        Analyze an article for misinformation, bias, and manipulation.

        Parameters:
            title    - Article headline
            content  - Full article body text
            source   - Publisher name (optional)
            category - Article category like 'politics', 'health' (optional)

        Returns:
            dict with overall_score, rating, breakdown, specific_warnings,
            and recommendation.
        """
        # ---- Cache check (avoid re-analyzing identical content) ----
        cache_key = hashlib.md5((title + content).encode()).hexdigest()
        if cache_key in _analysis_cache:
            return _analysis_cache[cache_key]

        try:
            result = self._run_analysis(title, content, source, category)
        except Exception as e:
            print(f"[MisinformationDetector] Analysis error: {e}")
            result = self._fallback_result(str(e))

        # Cache the result
        _analysis_cache[cache_key] = result
        return result

    # ====================================================================
    # INTERNAL ANALYSIS PIPELINE
    # ====================================================================

    def _run_analysis(self, title: str, content: str, source: str,
                      category: str) -> Dict:
        """Execute all analysis passes and combine scores."""
        full_text = f"{title}. {content}" if title else content
        word_count = len(full_text.split())

        # Scale factor for short articles (<100 words)
        scale = min(1.0, word_count / self.SHORT_ARTICLE_WORDS)

        # -----------------------------------------------------------
        # spaCy NLP Pipeline: Tokenization → POS Tagging →
        #   Dependency Parsing → NER  (all in one call)
        # -----------------------------------------------------------
        doc = nlp(full_text[:100000])  # limit to 100K chars for speed

        # ---- 1. Rule-Based Analyses ----
        passive_result = self._detect_passive_voice(doc)
        claims_result = self._detect_unattributed_claims(doc)
        hedge_result = self._detect_hedging(doc, word_count)
        emotion_rule_result = self._detect_emotional_language(doc, word_count)
        loaded_result = self._detect_loaded_language(doc)
        source_result = self._detect_missing_sources(doc)

        # ---- 2. Pre-Trained Model Analyses ----
        sentiment_result = self._analyze_sentiment(full_text)
        emotion_model_result = self._analyze_emotions(full_text[:5000])

        # ---- 3. Compute Component Scores (0-100 each) ----
        scores = {}

        # Passive voice score
        pv_pct = passive_result['percentage']
        scores['passive_voice'] = min(100, (pv_pct / max(self.PASSIVE_VOICE_THRESHOLD * scale, 1)) * 100) if pv_pct > 0 else 0

        # Unattributed claims score
        claim_ratio = claims_result['count'] / max(1, claims_result['total_triggers'])
        scores['unattributed_claims'] = min(100, claim_ratio * 100) if claims_result['count'] > 0 else 0

        # Hedging score
        hedge_density = hedge_result['density']
        scores['hedging'] = min(100, (hedge_density / max(self.HEDGE_DENSITY_THRESHOLD * scale, 0.1)) * 100) if hedge_density > 0 else 0

        # Emotional language score (rule-based)
        em_score = 0
        for cat_key in ['fear', 'anger', 'urgency']:
            cat_pct = emotion_rule_result.get(f'{cat_key}_pct', 0)
            threshold = self.EMOTIONAL_WORD_THRESHOLD * scale
            if cat_pct > threshold:
                em_score += min(33, (cat_pct / max(threshold, 0.01)) * 33)
        sup_count = emotion_rule_result.get('superlative_count', 0)
        if sup_count > self.SUPERLATIVE_THRESHOLD:
            em_score += min(34, (sup_count / max(self.SUPERLATIVE_THRESHOLD, 1)) * 17)
        scores['emotional_language'] = min(100, em_score)

        # Sentiment score (VADER)
        compound = sentiment_result.get('compound', 0)
        if abs(compound) > self.EXTREME_SENTIMENT_THRESHOLD:
            scores['sentiment'] = min(100, (abs(compound) / 1.0) * 100)
        else:
            scores['sentiment'] = (abs(compound) / self.EXTREME_SENTIMENT_THRESHOLD) * 50

        # Emotion profile score (text2emotion)
        fear_val = emotion_model_result.get('fear', 0)
        anger_val = emotion_model_result.get('anger', 0)
        combined_fa = (fear_val + anger_val) * 100
        if combined_fa > self.FEAR_ANGER_THRESHOLD:
            scores['emotion_profile'] = min(100, (combined_fa / 100) * 100)
        else:
            scores['emotion_profile'] = (combined_fa / max(self.FEAR_ANGER_THRESHOLD, 1)) * 50

        # Missing sources score
        ms_ratio = source_result['unattributed'] / max(1, source_result['total_quotes'])
        scores['missing_sources'] = min(100, ms_ratio * 100) if source_result['unattributed'] > 0 else 0

        # ---- 4. Weighted Overall Score ----
        overall = 0
        for key, weight in self.WEIGHTS.items():
            overall += scores.get(key, 0) * weight
        overall = round(min(100, max(0, overall)))

        # ---- 5. Adjust for category context ----
        # Opinion pieces naturally have higher subjectivity
        if category and category.lower() in ('opinion', 'editorial', 'commentary'):
            overall = max(0, overall - 15)
        # Breaking news may have fewer sources
        if source and 'breaking' in source.lower():
            overall = max(0, overall - 10)

        # ---- 6. Determine Rating ----
        if overall <= 30:
            rating = "green"
            recommendation = "Article appears reliable - standard journalistic practices observed"
        elif overall <= 60:
            rating = "yellow"
            recommendation = "Read critically - check original sources and verify key claims"
        else:
            rating = "red"
            recommendation = "High manipulation risk - cross-reference with trusted sources before sharing"

        # ---- 7. Build Specific Warnings ----
        warnings = self._build_warnings(
            passive_result, claims_result, hedge_result,
            emotion_rule_result, sentiment_result, emotion_model_result,
            loaded_result, source_result, scale
        )

        # ---- 8. Assemble Final Result ----
        result = {
            "overall_score": overall,
            "rating": rating,
            "breakdown": {
                "passive_voice": {
                    "percentage": round(passive_result['percentage'], 1),
                    "score": round(scores['passive_voice'], 1),
                    "examples": passive_result['examples'][:3]
                },
                "unattributed_claims": {
                    "count": claims_result['count'],
                    "score": round(scores['unattributed_claims'], 1),
                    "examples": claims_result['examples'][:3]
                },
                "hedging": {
                    "density": round(hedge_result['density'], 1),
                    "score": round(scores['hedging'], 1),
                    "examples": hedge_result['examples'][:5]
                },
                "emotional_language": {
                    "fear_words": emotion_rule_result.get('fear_count', 0),
                    "anger_words": emotion_rule_result.get('anger_count', 0),
                    "urgency_words": emotion_rule_result.get('urgency_count', 0),
                    "superlatives": emotion_rule_result.get('superlative_count', 0),
                    "score": round(scores['emotional_language'], 1),
                },
                "loaded_language": {
                    "negative_terms": loaded_result['negative_count'],
                    "positive_terms": loaded_result['positive_count'],
                    "one_sided": loaded_result['one_sided'],
                    "examples": loaded_result['examples'][:5]
                },
                "sentiment": {
                    "compound": round(sentiment_result.get('compound', 0), 3),
                    "positive": round(sentiment_result.get('pos', 0), 3),
                    "negative": round(sentiment_result.get('neg', 0), 3),
                    "neutral": round(sentiment_result.get('neu', 0), 3),
                    "extreme": abs(sentiment_result.get('compound', 0)) > self.EXTREME_SENTIMENT_THRESHOLD,
                    "score": round(scores['sentiment'], 1)
                },
                "emotion_profile": {
                    "fear": round(emotion_model_result.get('fear', 0), 3),
                    "anger": round(emotion_model_result.get('anger', 0), 3),
                    "joy": round(emotion_model_result.get('joy', 0), 3),
                    "sadness": round(emotion_model_result.get('sadness', 0), 3),
                    "surprise": round(emotion_model_result.get('surprise', 0), 3),
                    "score": round(scores['emotion_profile'], 1)
                },
                "missing_sources": {
                    "unattributed_quotes": source_result['unattributed'],
                    "total_quotes": source_result['total_quotes'],
                    "score": round(scores['missing_sources'], 1),
                    "examples": source_result['examples'][:3]
                }
            },
            "specific_warnings": warnings,
            "recommendation": recommendation
        }

        return result

    # ====================================================================
    # RULE-BASED ANALYSIS METHODS
    # ====================================================================

    def _detect_passive_voice(self, doc) -> Dict:
        """
        Detect passive voice constructions using spaCy dependency parsing.

        NLP Technique: Dependency Parsing
        ----------------------------------
        spaCy assigns dependency labels to each token. Passive voice is
        identified by the presence of:
          - nsubjpass : passive nominal subject
          - csubjpass : passive clausal subject  
          - auxpass   : passive auxiliary (was, were, been, being, got)

        Algorithm:
        1. For each sentence in doc.sents
        2. Check if any token has dep_ in ['nsubjpass', 'csubjpass']
        3. Verify auxpass auxiliary exists
        4. Collect the sentence as a passive example
        5. Calculate percentage of passive sentences
        """
        total_sentences = 0
        passive_sentences = 0
        examples = []

        for sent in doc.sents:
            total_sentences += 1
            has_passive_subject = False
            has_aux_pass = False

            for token in sent:
                # Check for passive subject (dependency parsing label)
                if token.dep_ in ("nsubjpass", "csubjpass"):
                    has_passive_subject = True
                # Check for passive auxiliary
                if token.dep_ == "auxpass":
                    has_aux_pass = True

            # True passive = passive subject + passive auxiliary
            if has_passive_subject and has_aux_pass:
                passive_sentences += 1
                sent_text = sent.text.strip()
                if len(sent_text) < 200:  # skip very long sentences
                    examples.append(sent_text)

        percentage = (passive_sentences / max(total_sentences, 1)) * 100

        return {
            'percentage': percentage,
            'passive_count': passive_sentences,
            'total_sentences': total_sentences,
            'examples': examples
        }

    def _detect_unattributed_claims(self, doc) -> Dict:
        """
        Detect claims that reference experts/studies without naming them.

        NLP Techniques: PhraseMatcher + Named Entity Recognition (NER)
        ---------------------------------------------------------------
        1. PhraseMatcher finds trigger phrases like "Experts say"
        2. NER checks if a PERSON, ORG, or GPE entity appears nearby
        3. A claim is unattributed if no named entity is found within
           a 3-sentence window after the trigger phrase.

        Also accepts attribution patterns like:
          - "according to Dr. Sharma"
          - "the WHO stated"
          - "researchers at MIT found"
        """
        matches = self.trigger_matcher(doc)
        unattributed = []
        total_triggers = len(matches)

        # Build sentence lookup: token index → sentence index
        sentences = list(doc.sents)
        token_to_sent = {}
        for i, sent in enumerate(sentences):
            for token in sent:
                token_to_sent[token.i] = i

        # Build entity lookup: sentence index → set of entity labels
        sent_entities = {}
        for ent in doc.ents:
            ent_sent_idx = token_to_sent.get(ent.start, -1)
            if ent_sent_idx >= 0:
                if ent_sent_idx not in sent_entities:
                    sent_entities[ent_sent_idx] = set()
                sent_entities[ent_sent_idx].add(ent.label_)

        valid_labels = {"PERSON", "ORG", "GPE"}

        for match_id, start, end in matches:
            trigger_sent_idx = token_to_sent.get(start, -1)
            if trigger_sent_idx < 0:
                continue

            # Check current sentence and next 2 sentences for named entities
            found_source = False
            for offset in range(3):  # window of 3 sentences
                check_idx = trigger_sent_idx + offset
                if check_idx in sent_entities:
                    if sent_entities[check_idx] & valid_labels:
                        found_source = True
                        break

            # Also check for "according to" pattern in same sentence
            if not found_source:
                sent_text = sentences[trigger_sent_idx].text.lower()
                if "according to" in sent_text:
                    found_source = True

            if not found_source:
                trigger_text = doc[start:end].text
                sent_text = sentences[trigger_sent_idx].text.strip()
                example = sent_text if len(sent_text) < 150 else sent_text[:150] + "..."
                unattributed.append(example)

        return {
            'count': len(unattributed),
            'total_triggers': total_triggers,
            'examples': unattributed
        }

    def _detect_hedging(self, doc, word_count: int) -> Dict:
        """
        Detect hedging and weasel words using PhraseMatcher.

        NLP Technique: Pattern Matching + POS Tagging
        -----------------------------------------------
        Hedge words like "allegedly", "reportedly" indicate uncertainty.
        Weasel phrases like "many people", "some experts" obscure specifics.
        
        Density is calculated as hedges per 100 words.
        Hedging inside direct quotes is excluded (quoted speech allows it).
        """
        matches = self.hedge_matcher(doc)
        hedge_examples = []

        # Detect quote boundaries (rough heuristic: text between quotes)
        text = doc.text
        in_quote_ranges = []
        quote_chars = ['"', '\u201c', '\u201d', "'"]
        i = 0
        while i < len(text):
            if text[i] in quote_chars:
                start = i
                # Find closing quote
                j = i + 1
                while j < len(text) and text[j] not in quote_chars:
                    j += 1
                if j < len(text):
                    in_quote_ranges.append((start, j))
                i = j + 1
            else:
                i += 1

        def is_in_quote(char_start, char_end):
            """Check if a span falls inside a quoted region."""
            for qs, qe in in_quote_ranges:
                if char_start >= qs and char_end <= qe:
                    return True
            return False

        filtered_count = 0
        for match_id, start, end in matches:
            span = doc[start:end]
            # Skip hedges inside direct quotes
            if is_in_quote(span.start_char, span.end_char):
                continue
            filtered_count += 1
            hedge_examples.append(span.text)

        density = (filtered_count / max(word_count, 1)) * 100

        return {
            'count': filtered_count,
            'density': density,
            'examples': list(set(hedge_examples))  # deduplicate
        }

    def _detect_emotional_language(self, doc, word_count: int) -> Dict:
        """
        Detect emotionally manipulative language using word lists.

        NLP Technique: Lexicon-Based Analysis + POS Tagging
        ----------------------------------------------------
        Maintains category-specific emotion word lists (fear, anger, urgency).
        Counts frequency of each category and flags if any category exceeds
        the threshold percentage of total words.
        Also detects excessive superlatives.
        """
        text_lower = doc.text.lower()
        tokens_lower = [t.text.lower() for t in doc]

        # Count emotion words per category
        fear_found = [w for w in self.FEAR_WORDS if w in text_lower]
        anger_found = [w for w in self.ANGER_WORDS if w in text_lower]
        urgency_found = [w for w in self.URGENCY_WORDS if w in text_lower]

        # Count actual occurrences (not just presence)
        fear_count = sum(text_lower.count(w) for w in fear_found)
        anger_count = sum(text_lower.count(w) for w in anger_found)
        urgency_count = sum(text_lower.count(w) for w in urgency_found)

        # Superlative detection using PhraseMatcher + POS tag check
        sup_matches = self.superlative_matcher(doc)
        superlative_count = len(sup_matches)

        # Also count POS-tagged superlatives (JJS = superlative adjective,
        # RBS = superlative adverb) - this uses spaCy POS Tagging
        for token in doc:
            if token.tag_ in ("JJS", "RBS"):
                superlative_count += 1

        return {
            'fear_count': fear_count,
            'anger_count': anger_count,
            'urgency_count': urgency_count,
            'superlative_count': superlative_count,
            'fear_pct': (fear_count / max(word_count, 1)) * 100,
            'anger_pct': (anger_count / max(word_count, 1)) * 100,
            'urgency_pct': (urgency_count / max(word_count, 1)) * 100,
            'fear_examples': fear_found[:5],
            'anger_examples': anger_found[:5],
            'urgency_examples': urgency_found[:5]
        }

    def _detect_loaded_language(self, doc) -> Dict:
        """
        Detect loaded/biased word choices using neutral-vs-loaded pairs.

        NLP Technique: Lexicon-Based Semantic Analysis
        ------------------------------------------------
        Compares article word choices against a dictionary of loaded vs
        neutral term pairs. If an article consistently uses loaded terms
        for one side (e.g., only negative-loaded or only positive-loaded),
        a one-sided bias flag is raised.
        """
        text_lower = doc.text.lower()
        negative_found = []
        positive_found = []

        for loaded, neutral in self.LOADED_NEGATIVE.items():
            count = text_lower.count(loaded)
            if count > 0:
                negative_found.append(f'"{loaded}" (instead of "{neutral}") x{count}')

        for loaded, neutral in self.LOADED_POSITIVE.items():
            count = text_lower.count(loaded)
            if count > 0:
                positive_found.append(f'"{loaded}" (instead of "{neutral}") x{count}')

        neg_count = len(negative_found)
        pos_count = len(positive_found)

        # One-sided: only negative-loaded OR only positive-loaded terms
        one_sided = False
        if (neg_count >= 2 and pos_count == 0) or (pos_count >= 2 and neg_count == 0):
            one_sided = True

        return {
            'negative_count': neg_count,
            'positive_count': pos_count,
            'one_sided': one_sided,
            'examples': negative_found + positive_found
        }

    def _detect_missing_sources(self, doc) -> Dict:
        """
        Detect quotes and speech acts without identified speakers.

        NLP Technique: Dependency Parsing + NER
        -----------------------------------------
        Looks for verbs of communication (said, stated, claimed...) and
        checks whether a PERSON entity is connected as the subject (nsubj).
        Also finds quoted text and verifies a named speaker exists nearby.
        """
        total_quotes = 0
        unattributed = 0
        examples = []

        # Build entity set for quick lookup
        person_entities = {ent.text for ent in doc.ents if ent.label_ == "PERSON"}

        # Method 1: Find communication verbs and check for PERSON subject
        for token in doc:
            if token.lemma_.lower() in self.COMMUNICATION_VERBS and token.pos_ == "VERB":
                total_quotes += 1
                # Check if subject is a named person
                has_person_subject = False
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        # Check if the subject text matches a PERSON entity
                        if child.text in person_entities:
                            has_person_subject = True
                            break
                        # Check if subject span overlaps with any PERSON entity
                        for ent in doc.ents:
                            if ent.label_ == "PERSON" and ent.start <= child.i < ent.end:
                                has_person_subject = True
                                break
                    if has_person_subject:
                        break

                if not has_person_subject:
                    unattributed += 1
                    sent = token.sent.text.strip()
                    if len(sent) < 150:
                        examples.append(sent)

        # Method 2: Find text in quotation marks without nearby PERSON entity
        text = doc.text
        quote_pattern = re.compile(r'["\u201c](.+?)["\u201d]')
        for match in quote_pattern.finditer(text):
            total_quotes += 1
            # Get surrounding context (50 chars before and after)
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]

            # Check if any PERSON entity name appears in context
            found_person = False
            for person in person_entities:
                if person in context:
                    found_person = True
                    break

            if not found_person and len(match.group(1)) > 10:
                unattributed += 1
                quote_preview = match.group(1)[:80] + "..." if len(match.group(1)) > 80 else match.group(1)
                examples.append(f'Unattributed quote: "{quote_preview}"')

        return {
            'total_quotes': total_quotes,
            'unattributed': unattributed,
            'examples': examples
        }

    # ====================================================================
    # PRE-TRAINED MODEL ANALYSES
    # ====================================================================

    def _analyze_sentiment(self, text: str) -> Dict:
        """
        VADER Sentiment Analysis (NLTK pre-trained model).

        NLP Technique: Lexicon + Rule-Based Sentiment Analysis
        --------------------------------------------------------
        VADER (Valence Aware Dictionary and sEntiment Reasoner) uses a
        curated lexicon of sentiment-related words with intensity scores.
        The compound score ranges from -1 (most negative) to +1 (most positive).
        
        Extreme compound scores (|compound| > 0.6) indicate potential bias,
        as objective news reporting should be closer to neutral.
        """
        if not VADER_AVAILABLE:
            return {'compound': 0, 'pos': 0, 'neg': 0, 'neu': 1.0}

        try:
            scores = vader_analyzer.polarity_scores(text[:5000])
            return scores
        except Exception as e:
            print(f"[MisinformationDetector] VADER error: {e}")
            return {'compound': 0, 'pos': 0, 'neg': 0, 'neu': 1.0}

    def _analyze_emotions(self, text: str) -> Dict:
        """
        text2emotion: Pre-trained emotion category detection.

        NLP Technique: Emotion Classification
        ----------------------------------------
        text2emotion classifies text into 5 emotion categories:
          - Happy, Angry, Surprise, Sad, Fear
        Each category gets a percentage (0-1).
        
        High fear+anger (>50% combined) in news suggests emotional
        manipulation rather than objective reporting.
        """
        if not TEXT2EMOTION_AVAILABLE:
            return {'fear': 0, 'anger': 0, 'joy': 0, 'sadness': 0, 'surprise': 0}

        try:
            emotions = te.get_emotion(text)
            return {
                'fear': emotions.get('Fear', 0),
                'anger': emotions.get('Angry', 0),
                'joy': emotions.get('Happy', 0),
                'sadness': emotions.get('Sad', 0),
                'surprise': emotions.get('Surprise', 0)
            }
        except Exception as e:
            print(f"[MisinformationDetector] text2emotion error: {e}")
            return {'fear': 0, 'anger': 0, 'joy': 0, 'sadness': 0, 'surprise': 0}

    # ====================================================================
    # WARNING BUILDER
    # ====================================================================

    def _build_warnings(self, passive, claims, hedge, emotion_rule,
                        sentiment, emotion_model, loaded, sources,
                        scale: float) -> List[str]:
        """Build human-readable warning messages from analysis results."""
        warnings = []

        # Passive voice warning
        if passive['percentage'] > self.PASSIVE_VOICE_THRESHOLD * scale:
            warnings.append(
                f"High passive voice ({passive['percentage']:.0f}%) hides "
                f"who performed actions"
            )

        # Unattributed claims
        if claims['count'] > 0:
            warnings.append(
                f"{claims['count']} expert/study claim(s) without named sources"
            )

        # Hedging density
        if hedge['density'] > self.HEDGE_DENSITY_THRESHOLD * scale:
            warnings.append(
                f"High hedging density ({hedge['density']:.1f} per 100 words) "
                f"- uncertain language pattern"
            )

        # Emotional manipulation
        for cat, label in [('fear', 'fear'), ('anger', 'anger'), ('urgency', 'urgency')]:
            pct = emotion_rule.get(f'{cat}_pct', 0)
            if pct > self.EMOTIONAL_WORD_THRESHOLD * scale:
                warnings.append(
                    f"High {label} language detected ({pct:.1f}% of words)"
                )

        # Superlatives
        if emotion_rule.get('superlative_count', 0) > self.SUPERLATIVE_THRESHOLD:
            warnings.append(
                f"Excessive superlatives ({emotion_rule['superlative_count']} found) "
                f"- exaggeration pattern"
            )

        # Loaded language
        if loaded['one_sided']:
            side = "negative" if loaded['negative_count'] > loaded['positive_count'] else "positive"
            warnings.append(
                f"One-sided {side} loaded language detected - potential framing bias"
            )

        # Extreme sentiment (VADER)
        compound = sentiment.get('compound', 0)
        if abs(compound) > self.EXTREME_SENTIMENT_THRESHOLD:
            direction = "negative" if compound < 0 else "positive"
            warnings.append(
                f"Extreme {direction} sentiment (score: {compound:.2f}) may indicate bias"
            )

        # Fear/anger dominance (text2emotion)
        fear_val = emotion_model.get('fear', 0)
        anger_val = emotion_model.get('anger', 0)
        combined = (fear_val + anger_val) * 100
        if combined > self.FEAR_ANGER_THRESHOLD:
            warnings.append(
                f"Fear+anger emotion dominance ({combined:.0f}%) - "
                f"emotional manipulation pattern"
            )

        # Missing sources in quotes
        if sources['unattributed'] > 0:
            warnings.append(
                f"{sources['unattributed']} quote(s) without identified speakers"
            )

        return warnings if warnings else ["No significant manipulation patterns detected"]

    # ====================================================================
    # FALLBACK (Graceful degradation)
    # ====================================================================

    def _fallback_result(self, error_msg: str = "") -> Dict:
        """Return a safe fallback result when analysis fails."""
        return {
            "overall_score": -1,
            "rating": "unavailable",
            "breakdown": {},
            "specific_warnings": [
                "Analysis unavailable" + (f" - {error_msg}" if error_msg else "")
            ],
            "recommendation": "Analysis could not be completed. Read with standard caution."
        }


# ============================================================================
# MODULE-LEVEL SINGLETON for easy import
# ============================================================================
detector = MisinformationDetector()


def analyze_article(title: str, content: str, source: str = "",
                    category: str = "") -> Dict:
    """
    Convenience function - analyzes an article using the singleton detector.
    
    This is the primary entry point for integration with app.py.
    
    Parameters:
        title    - Article headline
        content  - Full article body text
        source   - Publisher name (optional)
        category - Article category (optional)
    
    Returns:
        Analysis result dict with scores, ratings, and warnings.
    """
    # Return safe default if spacy not available
    if not SPACY_AVAILABLE or nlp is None:
        return {
            "overall_score": -1,
            "rating": "unavailable",
            "breakdown": {},
            "specific_warnings": ["Analysis unavailable (NLP library not installed)"],
            "recommendation": "Install spacy to enable misinformation detection."
        }
    
    return detector.analyze(title, content, source, category)
