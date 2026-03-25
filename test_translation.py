#!/usr/bin/env python3
"""
Simple test script to diagnose translation system issues.
Run this to verify all translation dependencies are installed.
"""

import sys

print("=" * 60)
print("TRANSLATION SYSTEM DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Check if config is loadable
print("\n1. Testing config imports...")
try:
    from config import (
        TRANSLATION_ENABLED, 
        SUPPORTED_TRANSLATION_LANGS,
        TRANSLATION_MODEL_NAME
    )
    print(f"   ✓ Config loaded")
    print(f"   - TRANSLATION_ENABLED: {TRANSLATION_ENABLED}")
    print(f"   - Supported languages: {list(SUPPORTED_TRANSLATION_LANGS.keys())}")
    print(f"   - Model: {TRANSLATION_MODEL_NAME}")
except Exception as e:
    print(f"   ✗ Config import failed: {e}")
    sys.exit(1)

# Test 2: Check if spacy is installed
print("\n2. Testing spacy installation...")
try:
    import spacy
    print(f"   ✓ spacy is installed (version {spacy.__version__})")
    try:
        nlp = spacy.load("en_core_web_sm")
        print(f"   ✓ en_core_web_sm model loaded")
    except:
        print(f"   ✗ en_core_web_sm model not found. Run: python -m spacy download en_core_web_sm")
except ImportError as e:
    print(f"   ✗ spacy not installed: {e}")

# Test 3: Check if transformers is installed
print("\n3. Testing transformers installation...")
try:
    import transformers
    print(f"   ✓ transformers is installed (version {transformers.__version__})")
except ImportError as e:
    print(f"   ✗ transformers not installed: {e}")

# Test 4: Check if torch is installed
print("\n4. Testing torch installation...")
try:
    import torch
    print(f"   ✓ torch is installed (version {torch.__version__})")
    print(f"   - CUDA available: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"   ✗ torch not installed: {e}")

# Test 5: Check if indic-transliteration is installed
print("\n5. Testing indic-transliteration installation...")
try:
    import indic_transliteration
    print(f"   ✓ indic-transliteration is installed")
except ImportError as e:
    print(f"   ✗ indic-transliteration not installed: {e}")

# Test 6: Check if storage classes are loadable
print("\n6. Testing storage classes...")
try:
    from storage import TranslationCacheStorage
    print(f"   ✓ TranslationCacheStorage loaded")
except ImportError as e:
    print(f"   ✗ TranslationCacheStorage import failed: {e}")

# Test 7: Try to import translator_m2m100
print("\n7. Testing translator_m2m100 module...")
try:
    from services import translator_m2m100
    print(f"   ✓ translator_m2m100 module loaded")
except Exception as e:
    print(f"   ✗ translator_m2m100 import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Try to import translator_service
print("\n8. Testing translator_service module...")
try:
    from services import translator_service
    print(f"   ✓ translator_service module loaded")
except Exception as e:
    print(f"   ✗ translator_service import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
print("\nIf all tests pass, translation system should work.")
print("If any fail, install missing packages with: pip install -r requirements.txt")
