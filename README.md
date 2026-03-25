
# 📰 AI News Aggregator

An AI-powered web application that summarizes news articles and YouTube videos using AI.
It supports contextual follow-up questions and stores user interaction data locally.

---

## 🚀 Features

- **News Article Summarization** – Paste any news URL and generate a concise AI-powered summary.
- **YouTube Video Summarization** – Extract video transcripts and generate structured summaries.
- **Context-Aware Follow-Up Chat** – Ask questions based on the generated summary.
- **Quiz Generation** – Automatically create quiz questions from summarized content.
- **Multilingual Translation** – Translate article summaries to Hindi, Marathi, Tamil, and Telugu with entity protection via NER and transliteration.
- **Local Data Storage** – Articles, quizzes, chat history, and translations stored using JSON files with intelligent caching.
  
---

## 🌐 Multilingual Translation System

The translation system provides enterprise-grade multilingual support for article summaries with advanced NLP features:

### Supported Languages
- 🇮🇳 **Hindi** (हिंदी) - Devanagari script
- 🇮🇳 **Marathi** (मराठी) - Devanagari script  
- 🇮🇳 **Tamil** (தமிழ்) - Tamil script
- 🇮🇳 **Telugu** (తెలుగు) - Telugu script

### Key Features
- **Entity Protection**: Names, organizations, and locations are protected via spaCy NER + placeholder mapping to prevent model rewrites
- **Entity Transliteration**: Automatic conversion of named entities to target language script using indic-transliteration
- **Smart Chunking**: Long summaries (>512 tokens) are intelligently split at sentence boundaries 
- **Translation Model**: Facebook M2M100 (418M parameters) for high-quality many-to-many translation
- **Translation Caching**: LRU-based JSON cache stores up to 1000 translations with automatic eviction by last access time
- **Post-Processing**: Automatic whitespace normalization and danda (।) conversion for Hindi/Marathi

### Installation (First-Time Setup)

The translation system requires additional dependencies:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

**First Translation Note**: On first use, the system downloads the M2M100 model (~2GB). This happens automatically on the first translation request and may take 2-3 minutes. Translations run offline thereafter.

### Usage

1. Generate a summary for any article using the summarization feature
2. In the Summary panel, select a target language from the dropdown (English default)
3. Optional: Enable "Side-by-side" toggle to compare original and translated text
4. The system automatically caches results—repeated translations of the same content load instantly
5. Your language preference is saved to localStorage

### API Endpoint

```
POST /api/translate-summary

Request:
{
  "article_id": 1,
  "target_lang": "hi"  // "hi", "mr", "ta", "te"
}

Response:
{
  "success": true,
  "article_id": 1,
  "target_lang": "hi",
  "translated_summary": "अनुवादित पाठ...",
  "cached": false,
  "entity_count": 5,
  "chunks": 1,
  "provider": "m2m100"
}
```

### Caching Behavior

- **Cache Location**: `data/translation_cache.json`
- **Max Entries**: 1,000 translations (configurable)
- **Eviction Policy**: LRU (Least Recently Used) - oldest by `last_accessed_at`
- **Hit Rate**: Identical summaries translated to same language reuse cache instantly
- **Cache Info**: API response includes `"cached": true/false` flag

### Examples

**Example 1: "Narendra Modi meets Joe Biden in Washington"**
- Source entities: Modi→मोदी, Biden→बिडेन, Washington→वाशिंगटन
- Protected via placeholders during translation
- Restored with Devanagari transliteration for Hindi

**Example 2: Long summary (1000+ tokens)**
- Split into ~450-token chunks at sentence boundaries
- Each chunk translated independently
- Response includes `"chunks": 3` (example)

---



## 🛠 Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **AI Integration**: OpenAI API
- **YouTube Integration**: YouTube Data API
-**Storage**: JSON files
-**Version Control**: Git & GitHub

---

## Repository Structure:

```
AI-News-Aggregator/
│
├── app.py              # Main Flask application
├── config.py           # Environment variable configuration
├── storage.py          # JSON data handling
├── requirements.txt    # Project dependencies
│
├── services/           # Core logic (scraping, summarization, filtering)
├── templates/          # HTML templates
├── static/             # CSS & JavaScript files
├── data/               # Stored articles, quizzes, chat history
```

---

## Setup Instructions:
1. Clone the Repository: 

git clone https://github.com/kritikadamahe/AI-News-Aggregator.git 

cd AI-News-Aggregator

3. Create Virtual Environment:  

    python -m venv .venv

4. Activate Environment (Windows): 

   .venv\Scripts\activate

5. Install Dependencies: 

   pip install -r requirements.txt

6. Create .env File

   Add:

    OPENAI_API_KEY=your_openai_api_key

    YOUTUBE_API_KEY=your_youtube_api_key

7. Run the Application: 

python app.py

---

## Learning Outcomes:

- API integration with external services
- Flask backend architecture design
- Secure environment variable handling
- Modular project structuring
- Git and GitHub workflow management

---
