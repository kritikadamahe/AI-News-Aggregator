#!/usr/bin/env python
"""Download spaCy English model for NER extraction."""

import subprocess
import sys
import os

# Use the virtual environment's Python explicitly
venv_python = os.path.join(
    os.path.dirname(__file__),
    ".venv", "Scripts", "python.exe"
)

if not os.path.exists(venv_python):
    venv_python = sys.executable

print(f"[Setup] Using Python: {venv_python}")
print("[Setup] Downloading spaCy English model...")
try:
    subprocess.check_call([venv_python, "-m", "spacy", "download", "en_core_web_sm"])
    print("[Setup] ✓ spaCy model downloaded successfully")
except Exception as e:
    print(f"[Setup] ✗ Error downloading model: {e}")
    sys.exit(1)
