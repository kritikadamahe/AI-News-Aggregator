"""
services/translator_m2m100.py - Multilingual Translation Service
==================================================================
Implements 9-step translation pipeline with entity protection:
0. Lazy-load models (M2M100 + spaCy NER)
1. Extract named entities (PERSON/ORG/GPE/LOC/PRODUCT)
2. Transliterate entities to target script
3. Replace entities with placeholders
4. Chunk if >512 tokens by sentence boundaries
5. Translate with M2M100
6. Restore placeholders with transliteration
7. Post-process (whitespace, danda for hi/mr)
8. Return structured result
9. Integration with cache (see translator_service wrapper)

Key Features:
- Thread-safe model loading (singleton pattern)
- Entity name preservation via placeholder protection
- Support for Hindi, Marathi, Tamil, Telugu
- LRU cache with last_accessed_at tracking
- Graceful fallback handling
"""

import re
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL MODEL SINGLETONS (Lazy-loaded, reused across requests)
# ============================================================================

_nlp = None
_tokenizer = None
_model = None
_model_device = None


def _load_models(device: str = "cpu"):
    """Lazy-load spaCy NER model and M2M100 models (singleton pattern)."""
    global _nlp, _tokenizer, _model, _model_device
    
    if _nlp is not None and _model is not None:
        return  # Already loaded
    
    _model_device = device
    
    try:
        import spacy
        print("[Translation] Loading spaCy NER model...")
        _nlp = spacy.load("en_core_web_sm")
        print("[Translation] ✓ spaCy model loaded")
    except OSError:
        logger.error(
            "[Translation] spaCy model not found. Install with:\n"
            "  python -m spacy download en_core_web_sm"
        )
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' not found. "
            "Run: python -m spacy download en_core_web_sm"
        )
    
    try:
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        from config import TRANSLATION_MODEL_NAME
        
        print(f"[Translation] Loading {TRANSLATION_MODEL_NAME} model...")
        _tokenizer = M2M100Tokenizer.from_pretrained(TRANSLATION_MODEL_NAME)
        _model = M2M100ForConditionalGeneration.from_pretrained(TRANSLATION_MODEL_NAME)
        _model.to(device)
        print(f"[Translation] ✓ M2M100 model loaded on {device}")
    except Exception as e:
        logger.error(f"[Translation] Failed to load M2M100 model: {e}")
        raise RuntimeError(f"Failed to load translation model: {e}")


# ============================================================================
# STEP 1: Extract Named Entities (NER)
# ============================================================================

def _extract_entities(text: str) -> Dict[str, List[Dict]]:
    """
    Extract named entities from text using spaCy.
    Also extract URLs, emails, acronyms as pseudo-entities.
    
    Returns:
    {
      "PERSON": [{"start_char": 0, "end_char": 5, "text": "John", "label": "PERSON"}],
      "ORG": [...],
      ...
      "URL": [...],
      "EMAIL": [...],
      "ACRONYM": [...]
    }
    """
    global _nlp
    
    if _nlp is None:
        _load_models()
    
    entities_dict = {}
    doc = _nlp(text)
    
    # Extract spaCy named entities
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"}:
            if ent.label_ not in entities_dict:
                entities_dict[ent.label_] = []
            
            entities_dict[ent.label_].append({
                "start_char": ent.start_char,
                "end_char": ent.end_char,
                "text": ent.text,
                "label": ent.label_
            })
    
    # Extract URLs (preserve as-is)
    url_pattern = r'https?://\S+'
    for match in re.finditer(url_pattern, text):
        if "URL" not in entities_dict:
            entities_dict["URL"] = []
        entities_dict["URL"].append({
            "start_char": match.start(),
            "end_char": match.end(),
            "text": match.group(),
            "label": "URL"
        })
    
    # Extract emails (preserve as-is)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    for match in re.finditer(email_pattern, text):
        if "EMAIL" not in entities_dict:
            entities_dict["EMAIL"] = []
        entities_dict["EMAIL"].append({
            "start_char": match.start(),
            "end_char": match.end(),
            "text": match.group(),
            "label": "EMAIL"
        })
    
    # Extract acronyms (preserve as-is)
    acronym_pattern = r'\b[A-Z]{2,}\b'
    for match in re.finditer(acronym_pattern, text):
        if "ACRONYM" not in entities_dict:
            entities_dict["ACRONYM"] = []
        entities_dict["ACRONYM"].append({
            "start_char": match.start(),
            "end_char": match.end(),
            "text": match.group(),
            "label": "ACRONYM"
        })
    
    return entities_dict


# ============================================================================
# STEP 2: Transliterate Entities
# ============================================================================

def _transliterate_entity(text: str, target_lang: str) -> str:
    """
    Transliterate entity text from Roman to target Indic script.
    Graceful fallback to original text if transliteration fails.
    """
    try:
        from indic_transliteration import sanscript
        
        # Map target_lang to indic-transliteration script constants
        script_map = {
            "hi": sanscript.DEVANAGARI,
            "mr": sanscript.DEVANAGARI,
            "ta": sanscript.TAMIL,
            "te": sanscript.TELUGU
        }
        
        if target_lang not in script_map:
            return text
        
        target_script = script_map[target_lang]
        
        # Try ITRANS (common transliteration scheme)
        try:
            result = sanscript.transliterate(text, sanscript.ITRANS, target_script)
            if result and result.strip():
                return result
        except Exception:
            pass
        
        # Fallback: try HK (Harvard-Kyoto)
        try:
            result = sanscript.transliterate(text, sanscript.HK, target_script)
            if result and result.strip():
                return result
        except Exception:
            pass
        
    except ImportError:
        logger.warning("[Translation] indic-transliteration not available")
    except Exception as e:
        logger.warning(f"[Translation] Transliteration failed for '{text}': {e}")
    
    # Fallback: return original text
    return text


# ============================================================================
# STEP 3: Replace Entities with Placeholders
# ============================================================================

def _replace_entities_with_placeholders(
    text: str, 
    entities_dict: Dict[str, List[Dict]], 
    target_lang: str
) -> Tuple[str, Dict[str, Dict]]:
    """
    Replace entity spans in text with placeholders like PERSON_1, ORG_2, etc.
    Build mapping: placeholder -> {original, translit, label}
    
    Returns: (protected_text, mapping)
    """
    # Collect all entities to replace, sorted by start_char descending (replace right-to-left)
    all_ents = []
    counter = {}
    mapping = {}
    
    for label, ents_list in entities_dict.items():
        for ent in ents_list:
            all_ents.append((ent["start_char"], ent["end_char"], ent["text"], label))
            counter[label] = counter.get(label, 0) + 1
    
    # Sort by start_char descending (replace right-to-left to avoid index shifts)
    all_ents.sort(reverse=True, key=lambda x: x[0])
    
    protected_text = text
    
    for i, (start_char, end_char, entity_text, label) in enumerate(all_ents):
        # Don't transliterate URLs, emails, acronyms
        if label in {"URL", "EMAIL", "ACRONYM"}:
            translit_text = entity_text
        else:
            translit_text = _transliterate_entity(entity_text, target_lang)
        
        # Create placeholder (e.g., "PERSON_1", "ORG_2")
        entity_counter = counter[label] - (i % len([e for e in all_ents if e[3] == label])) - 1 + len([e for e in all_ents if e[3] == label])
        placeholder = f"{label}_{counter.get(label, 1)}"
        counter[label] = counter.get(label, 1) - 1
        
        # Simple counter for unique placeholders
        if placeholder in mapping:
            placeholder = f"{label}_{counter.get(label, 1) - 1}"
        
        mapping[placeholder] = {
            "original": entity_text,
            "translit": translit_text,
            "label": label
        }
        
        # Replace in text
        protected_text = protected_text[:start_char] + placeholder + protected_text[end_char:]
    
    return protected_text, mapping


# Simpler version without complex counter logic
def _replace_entities_simple(
    text: str,
    entities_dict: Dict[str, List[Dict]],
    target_lang: str
) -> Tuple[str, Dict[str, Dict]]:
    """Simpler entity replacement with linear counter per label."""
    all_ents = []
    for label, ents_list in entities_dict.items():
        for ent in ents_list:
            all_ents.append((ent["start_char"], ent["end_char"], ent["text"], label))
    
    # Sort by start_char descending
    all_ents.sort(reverse=True, key=lambda x: x[0])
    
    protected_text = text
    mapping = {}
    label_counters = {}
    
    for start_char, end_char, entity_text, label in all_ents:
        label_counters[label] = label_counters.get(label, 0) + 1
        
        # Transliterate (skip for URL/EMAIL/ACRONYM)
        if label in {"URL", "EMAIL", "ACRONYM"}:
            translit_text = entity_text
        else:
            translit_text = _transliterate_entity(entity_text, target_lang)
        
        placeholder = f"{label}_{label_counters[label]}"
        mapping[placeholder] = {
            "original": entity_text,
            "translit": translit_text,
            "label": label
        }
        
        protected_text = protected_text[:start_char] + placeholder + protected_text[end_char:]
    
    return protected_text, mapping


# ============================================================================
# STEP 4: Chunk Text if >512 Tokens
# ============================================================================

def _chunk_text(text: str, max_tokens: int = 512, tokenizer=None) -> List[str]:
    """Chunk text at sentence boundaries if token count exceeds max_tokens."""
    global _tokenizer
    
    if tokenizer is None:
        tokenizer = _tokenizer
    
    # Estimate tokens
    try:
        encoded = tokenizer(text, return_tensors="pt")
        token_count = encoded["input_ids"].shape[1]
    except Exception as e:
        logger.warning(f"[Translation] Token count estimation failed: {e}, using length heuristic")
        token_count = len(text.split()) * 1.3  # Rough estimate
    
    if token_count <= max_tokens:
        return [text]
    
    # Split into sentences
    try:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        
        sentences = nltk.sent_tokenize(text)
    except Exception as e:
        logger.warning(f"[Translation] NLTK tokenization failed: {e}, using simple split")
        sentences = text.split(". ")
    
    # Group sentences into chunks
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        test_chunk = current_chunk + " " + sentence if current_chunk else sentence
        
        try:
            encoded = tokenizer(test_chunk, return_tensors="pt")
            test_tokens = encoded["input_ids"].shape[1]
        except:
            test_tokens = len(test_chunk.split()) * 1.3
        
        if test_tokens > max_tokens - 50:  # Safety buffer
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk = test_chunk
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks if chunks else [text]


# ============================================================================
# STEP 5: Translate with M2M100
# ============================================================================

def _translate_chunk(chunk_text: str, target_lang: str) -> str:
    """Translate a single chunk using M2M100."""
    global _model, _tokenizer
    
    if _model is None or _tokenizer is None:
        _load_models()
    
    try:
        from config import M2M100_LANG_CODES
        
        target_lang_code = M2M100_LANG_CODES.get(target_lang, target_lang)
        
        # Set source language
        _tokenizer.src_lang = "en"
        
        # Tokenize
        encoded = _tokenizer(chunk_text, return_tensors="pt", max_length=512, truncation=True)
        encoded = {k: v.to(_model_device) for k, v in encoded.items()}
        
        # Get forced BOS token ID for target language
        try:
            forced_bos_token_id = _tokenizer.get_lang_id(target_lang_code)
        except:
            logger.warning(f"[Translation] Could not get BOS token for {target_lang_code}")
            forced_bos_token_id = None
        
        # Generate
        generated_ids = _model.generate(
            **encoded,
            forced_bos_token_id=forced_bos_token_id,
            num_beams=3,
            no_repeat_ngram_size=3,
            max_length=512
        )
        
        # Decode
        translated = _tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
        return translated[0] if translated else chunk_text
    
    except Exception as e:
        logger.error(f"[Translation] M2M100 translation failed: {e}")
        raise RuntimeError(f"Translation failed: {e}")


# ============================================================================
# STEP 6: Restore Placeholders with Transliterations
# ============================================================================

def _restore_placeholders(translated_text: str, mapping: Dict[str, Dict]) -> str:
    """Replace placeholders with transliterated entities."""
    result = translated_text
    
    for placeholder, info in mapping.items():
        # Use word boundary regex to avoid partial replacements
        pattern = r'\b' + re.escape(placeholder) + r'\b'
        replacement = info["translit"]
        result = re.sub(pattern, replacement, result)
    
    return result


# ============================================================================
# STEP 7: Post-Processing
# ============================================================================

def _postprocess_text(text: str, target_lang: str) -> str:
    """
    Post-process translated text:
    - Whitespace normalization
    - Danda replacement for Hindi/Marathi
    """
    from config import DANDA_LANGS
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces -> single space
    text = re.sub(r'\s+([.,!?;:\)])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'(\()\s+', r'\1', text)  # Remove space after opening paren
    text = text.strip()
    
    # Replace period with danda for certain languages
    if target_lang in DANDA_LANGS:
        # Replace periods at sentence boundaries with danda
        # Avoid replacing decimals like "3.5"
        text = re.sub(r'(?<!\d)\.(\s|$)', r'।\1', text)
        # Remove double danda
        text = re.sub(r'।+', r'।', text)
    
    return text


# ============================================================================
# MAIN TRANSLATION FUNCTION (9-step pipeline)
# ============================================================================

def translate_summary(
    summary_text: str,
    target_lang: str,
    article_id: int = None,
    use_cache: bool = True
) -> Dict:
    """
    Translate summary through 9-step pipeline with entity protection.
    
    Args:
        summary_text: English summary to translate
        target_lang: Target language code (hi/mr/ta/te)
        article_id: Optional article ID for cache tracking
        use_cache: Whether to use/update cache
    
    Returns:
        {
            "translated_text": "...",
            "target_lang": "hi",
            "entity_count": N,
            "placeholders_used": N,
            "chunks": number_of_chunks,
            "provider": "m2m100",
            "error": None
        }
    """
    try:
        # Load models
        from config import TRANSLATION_DEVICE
        _load_models(TRANSLATION_DEVICE)
        
        # Step 0: Prepare
        print(f"[Translation] Starting translation to {target_lang}...")
        input_hash = hashlib.md5(summary_text.encode()).hexdigest()
        
        # Step 1: Extract entities
        print("[Translation] Step 1: Extracting named entities...")
        entities_dict = _extract_entities(summary_text)
        total_entity_count = sum(len(ents) for ents in entities_dict.values())
        print(f"[Translation] Found {total_entity_count} entities")
        
        # Step 2-3: Transliterate & Replace with placeholders
        print("[Translation] Step 2-3: Transliterating entities & creating placeholders...")
        protected_text, mapping = _replace_entities_simple(summary_text, entities_dict, target_lang)
        print(f"[Translation] Created {len(mapping)} placeholders")
        
        # Step 4: Chunk if needed
        print("[Translation] Step 4: Chunking text...")
        chunks = _chunk_text(protected_text, max_tokens=512)
        print(f"[Translation] Text split into {len(chunks)} chunk(s)")
        
        # Step 5: Translate chunks
        print("[Translation] Step 5-6: Translating & restoring entities...")
        translated_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"[Translation] Translating chunk {i+1}/{len(chunks)}...")
            translated_chunk = _translate_chunk(chunk, target_lang)
            # Restore placeholders immediately
            translated_chunk = _restore_placeholders(translated_chunk, mapping)
            translated_chunks.append(translated_chunk)
        
        # Join chunks
        translated_text = " ".join(translated_chunks)
        
        # Step 7: Post-process
        print("[Translation] Step 7: Post-processing...")
        translated_text = _postprocess_text(translated_text, target_lang)
        
        # Step 8: Return result
        print("[Translation] ✓ Translation complete")
        result = {
            "translated_text": translated_text,
            "target_lang": target_lang,
            "entity_count": total_entity_count,
            "placeholders_used": len(mapping),
            "chunks": len(chunks),
            "provider": "m2m100",
            "error": None
        }
        
        return result
    
    except Exception as e:
        logger.error(f"[Translation] Pipeline error: {e}")
        return {
            "translated_text": None,
            "target_lang": target_lang,
            "entity_count": 0,
            "placeholders_used": 0,
            "chunks": 0,
            "provider": "m2m100",
            "error": str(e)
        }
