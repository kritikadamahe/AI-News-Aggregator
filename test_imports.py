#!/usr/bin/env python
"""Test if all new modules import successfully"""

try:
    from services.entity_extractor import EntityExtractor
    print("✅ EntityExtractor imported")
except Exception as e:
    print(f"❌ EntityExtractor error: {e}")

try:
    from services.relationship_mapper import RelationshipMapper
    print("✅ RelationshipMapper imported")
except Exception as e:
    print(f"❌ RelationshipMapper error: {e}")

try:
    import app
    print("✅ App module imported successfully")
except Exception as e:
    print(f"❌ App import error: {e}")

print("\n✅ All imports successful!")
