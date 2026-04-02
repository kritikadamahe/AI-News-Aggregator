
# 📰 AI News Aggregator

An AI-powered web application that fetches, summarizes, analyzes, and translates news articles and YouTube videos. It offers context-aware follow-up chat, quiz generation, bias detection, entity relationship mapping, and multilingual translation — all in one single-page application.

---

## 🚀 Features

### 1. 📰 News Article Summarization
- Paste any news article URL to generate a concise AI-powered summary
- Supports direct text input and file uploads (PDF, DOCX, TXT)
- Intelligent content extraction using BeautifulSoup and newspaper3k
- Powered by **Meta Llama 3.1 8B** via OpenRouter API

### 2. 🎬 YouTube Video Summarization
- Paste a YouTube URL to extract the video transcript automatically
- Generate structured summaries with key points and timestamps
- Uses the YouTube Transcript API (no YouTube Data API key required)

### 3. 📡 Multi-Source News Fetching
- **NewsAPI Integration**: Fetch top headlines by category (business, entertainment, health, science, sports, technology) and country (US, UK, India, Canada, Australia)
- **RSS Feed Aggregation**: Pulls live articles from 6 major Indian news sources:
  - The Hindu, Times of India, Indian Express, NDTV, The Wire, Scroll.in
- Concurrent article processing for fast fetching

### 4. 💬 Context-Aware RAG Chat
- Ask follow-up questions about any summarized article
- Retrieval-Augmented Generation (RAG): the article's summary acts as context for the AI
- Session-based conversation management with automatic cleanup
- Up to 20 messages stored per session; sessions expire after 24 hours

### 5. 🎓 Quiz & Flashcard Generation
- Automatically generate **Multiple-Choice Questions (MCQs)** from any article summary
- Generate **Flashcards** for quick study and review
- Submit quiz answers and receive an instant score
- Configurable number of questions (default: 5)

### 6. 🌐 Multilingual Translation
Translate article summaries to four Indian languages with advanced NLP protection:

| Language | Script | Code |
|---|---|---|
| 🇮🇳 Hindi (हिंदी) | Devanagari | `hi` |
| 🇮🇳 Marathi (मराठी) | Devanagari | `mr` |
| 🇮🇳 Tamil (தமிழ்) | Tamil | `ta` |
| 🇮🇳 Telugu (తెలుగు) | Telugu | `te` |

- **Translation Model**: Facebook M2M100 (418M parameters) — runs offline after first download
- **Entity Protection**: Named entities (people, organizations, locations) are shielded from mistranslation via spaCy NER + placeholder mapping
- **Entity Transliteration**: Entities are converted to the target language script automatically (e.g., "Modi" → "मोदी")
- **Smart Chunking**: Long summaries (>512 tokens) are split at sentence boundaries and translated in chunks
- **LRU Caching**: Up to 1,000 translations cached; same content in same language loads instantly
- **Side-by-Side Mode**: Toggle to compare original and translated text simultaneously
- **Post-Processing**: Automatic danda (।) insertion for Hindi/Marathi in place of periods

### 7. ⚠️ Misinformation & Bias Detection
Analyze any article for potential bias or misinformation signals:
- **Passive voice detection** — signals that agency is being obscured
- **Unattributed claim identification** — finds unsourced assertions
- **Loaded/emotional language detection** — highlights charged vocabulary
- **VADER sentiment analysis** — measures emotional polarity of the text
- **Emotion categorization** — uses text2emotion to label: Happy, Sad, Angry, Fear, Surprise
- **Bias scoring** — produces an overall bias score with detailed flags

### 8. 🔗 Article Relationship Mapping
Discover how articles are connected using multi-dimensional similarity:

| Dimension | Weight | Description |
|---|---|---|
| Entity Overlap | 40% | Shared people, organizations, locations |
| Key Phrase Similarity | 25% | Common topics and terminology |
| Sentiment Alignment | 15% | Similar emotional tone |
| Temporal Proximity | 10% | Published around the same time |
| Category Match | 10% | Same news category |

- **Related Articles Sidebar**: Slide-in panel shows top related articles with match score and explanation
- **Interactive Relationship Graph**: Force-directed canvas visualization of the full article network; click any node to open that article
- **Entity-Based Search**: Click a shared entity to find all articles mentioning that person, organization, or location

### 9. 🤖 Smart Article Classification
Automatic NLP-based categorization of articles into: business, entertainment, general, health, science, sports, or technology using:
- POS tagging and dependency parsing (Subject-Verb-Object extraction)
- Named Entity Recognition (NER) with spaCy
- N-gram context windows
- Domain-specific vocabulary matching

### 10. 🧩 Entity Extraction & Normalization
- Extracts entities of types: PERSON, ORG, GPE (location), EVENT, PRODUCT
- Normalizes name variants: "PM Modi" = "Narendra Modi" = "Modi" → same canonical entity
- Removes honorifics (Mr., Dr., Prof.) for consistent matching
- Generates MD5-based canonical IDs for deduplication

### 11. 📁 File Upload & Processing
- Upload **PDF**, **DOCX**, or **TXT** files directly in the browser
- File content is automatically extracted and summarized
- Maximum file size: 10 MB (enforced server-side via Flask's `MAX_CONTENT_LENGTH` setting)

### 12. 💾 Local Data Persistence
- All data stored as JSON files — no database required
- **In-memory caching** layer for fast repeated reads
- Stored data: articles with metadata, quizzes and results, chat history, translation cache
- Articles persist across sessions; old sessions cleaned up automatically

---

## 🛠 Tech Stack

### Backend
| Component | Technology |
|---|---|
| Web Framework | Flask 3.0 (Python) |
| LLM Inference | OpenRouter API → Meta Llama 3.1 8B Instruct |
| NLP & NER | spaCy 3.7+ (`en_core_web_sm`) |
| NLP Toolkit | NLTK 3.8+ |
| Translation | Facebook M2M100 418M (Hugging Face Transformers) |
| Sentiment Analysis | VADER (NLTK) |
| Emotion Detection | text2emotion |
| Transliteration | indic-transliteration |
| Article Extraction | newspaper3k, BeautifulSoup4 |
| PDF Processing | PyPDF2 |
| DOCX Processing | python-docx |
| RSS Parsing | feedparser |
| YouTube Transcripts | youtube-transcript-api |
| News Headlines | NewsAPI (newsapi-python) |
| Deep Learning Backend | PyTorch 2.0+ |

### Frontend
| Component | Technology |
|---|---|
| UI | Single-Page Application (SPA) |
| Languages | HTML5, CSS3, Vanilla JavaScript |
| Graph Visualization | HTML5 Canvas (force-directed, no external library) |
| Design | Responsive, mobile-friendly |

### Storage
| Data | File |
|---|---|
| Articles & summaries | `data/articles.json` |
| Quizzes & results | `data/quizzes.json` |
| Chat history | `data/chat_history.json` |
| Translation cache | `data/translation_cache.json` |

---

## 📂 Repository Structure

```
AI-News-Aggregator/
│
├── app.py                              # Main Flask application (26 API routes)
├── config.py                           # Configuration & environment settings
├── storage.py                          # Hybrid JSON + in-memory caching
├── requirements.txt                    # Python dependencies
├── run_app.bat                         # Windows quick-start script
│
├── services/
│   ├── fetch_news.py                   # NewsAPI + web scraping
│   ├── rss_fetcher.py                  # RSS feed parsing (6 Indian sources)
│   ├── article_classifier.py           # NLP-based category classification
│   ├── entity_extractor.py             # NER & entity normalization
│   ├── relationship_mapper.py          # Article similarity & graph building
│   ├── misinformation_detector.py      # Bias & misinformation detection
│   ├── translator_service.py           # Translation caching wrapper
│   └── translator_m2m100.py            # M2M100 translation pipeline
│
├── templates/
│   └── index.html                      # Single-page app HTML
│
├── static/
│   ├── script.js                       # Frontend JavaScript (~84 KB)
│   └── style.css                       # Responsive CSS styles (~68 KB)
│
└── data/                               # Local JSON storage (auto-created)
    ├── articles.json
    ├── quizzes.json
    ├── chat_history.json
    └── translation_cache.json
```

---

## ⚙️ Setup Instructions

### Prerequisites
- Python 3.9 or higher
- An [OpenRouter](https://openrouter.ai/) account (free tier available) for LLM features
- A [NewsAPI](https://newsapi.org/) key (free tier available) for headline fetching

### Step-by-Step Installation

**1. Clone the repository**
```bash
git clone https://github.com/kritikadamahe/AI-News-Aggregator.git
cd AI-News-Aggregator
```

**2. Create and activate a virtual environment**
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Download the spaCy language model** (required for NER, translation entity protection, and relationship mapping)
```bash
python -m spacy download en_core_web_sm
```

**5. Create a `.env` file** in the project root with your API keys:
```
OPENROUTER_API_KEY=your_openrouter_api_key_here
NEWSAPI_KEY=your_newsapi_key_here
SECRET_KEY=your_secret_key_here
```

> **Generating a secure SECRET_KEY:** Run the following command and paste the output as the value for `SECRET_KEY`:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

**6. Run the application**
```bash
python app.py
```

**7. Open your browser** and navigate to: [http://localhost:5000](http://localhost:5000)

> **Note on Translation (First Use):** The first time you use the translation feature, the system automatically downloads the Facebook M2M100 model (~2 GB). This takes 2–3 minutes and happens once. All subsequent translations run fully offline.

---

## 🎓 Faculty Demonstration Guide

Use this guide to walk through all the key features during a demo session.

### Demo Flow

#### Step 1 — Summarize a News Article
1. Open [http://localhost:5000](http://localhost:5000)
2. Paste any news article URL (e.g., from The Hindu or BBC News) into the input box
3. Click **Summarize** → the AI generates a concise summary in seconds
4. Observe the article title, source, category, and publish date displayed alongside the summary

#### Step 2 — Summarize a YouTube Video
1. Paste a YouTube video URL (news-related works best) into the input box
2. Click **Summarize** → the transcript is extracted and summarized automatically

#### Step 3 — Upload a File
1. Click the upload/attachment icon
2. Upload a PDF, DOCX, or TXT news article
3. The content is automatically extracted and summarized

#### Step 4 — Fetch Live News Headlines
1. Click **Fetch News** in the navigation
2. Select a category (e.g., Technology) and country (e.g., India)
3. Multiple articles appear; click any to view its summary

#### Step 5 — Fetch RSS News from Indian Sources
1. Click **Fetch Comprehensive** to pull from RSS feeds (The Hindu, NDTV, etc.)
2. Articles from multiple sources are aggregated and displayed

#### Step 6 — Ask Follow-Up Questions (RAG Chat)
1. After viewing a summarized article, click **Ask AI**
2. Type a question related to the article (e.g., "What is the main impact of this event?")
3. The AI responds using the article as context — demonstrating Retrieval-Augmented Generation

#### Step 7 — Generate a Quiz
1. On any summarized article, click **Quiz**
2. 5 multiple-choice questions are generated from the summary
3. Answer the questions and submit to receive your score

#### Step 8 — Generate Flashcards
1. On any summarized article, click **Flashcards**
2. A set of flashcards is generated for study and revision

#### Step 9 — Translate the Summary
1. On any summarized article, use the language dropdown (top of summary panel)
2. Select **Hindi**, **Marathi**, **Tamil**, or **Telugu**
3. The summary is translated; named entities are preserved and transliterated correctly
4. Enable **Side-by-Side** toggle to compare original and translated text

#### Step 10 — Detect Bias & Misinformation
1. On any summarized article, click **Analyze**
2. View the bias score, sentiment analysis, emotion breakdown, and specific flags such as passive voice, unattributed claims, and loaded language

#### Step 11 — Find Related Articles
1. Summarize 3–5 articles on the same topic
2. On any article, click the **Related** (🔗) button
3. A sidebar slides in showing related articles with match percentage and explanation (shared entities, common phrases)

#### Step 12 — Explore the Relationship Graph
1. After summarizing several articles, click the **Graph** (📊) button
2. An interactive force-directed graph appears showing all articles as nodes
3. Connected articles are linked by edges (thicker = stronger relationship)
4. Click any node to navigate to that article

---

## 📡 API Reference (Key Endpoints)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Home page |
| `POST` | `/summarize` | Summarize article from URL or text |
| `POST` | `/fetch-news` | Fetch top headlines from NewsAPI |
| `POST` | `/fetch-comprehensive` | Fetch from RSS feeds + NewsAPI |
| `POST` | `/generate-quiz` | Generate quiz from article |
| `GET` | `/quiz/<id>` | Get quiz questions |
| `POST` | `/quiz/<id>/submit` | Submit quiz answers and get score |
| `POST` | `/chat/start` | Start new chat session |
| `POST` | `/chat/message` | Send a message in a chat session |
| `GET` | `/chat/history/<session_id>` | Retrieve chat history |
| `GET` | `/article/<id>` | Get article details |
| `DELETE` | `/article/<id>` | Delete an article |
| `GET` | `/search` | Search stored articles |
| `GET` | `/analyze/<id>` | Analyze article for bias/misinformation |
| `GET` | `/related/<id>` | Find related articles |
| `GET` | `/relationship-graph` | Get full article relationship graph |
| `GET` | `/entity/<entity_id>` | Get all articles mentioning an entity |
| `POST` | `/api/translate-summary` | Translate article summary |

---

## 🎯 Learning Outcomes

This project demonstrates the following computer science and software engineering concepts:

- **AI/ML Integration**: LLM inference via REST APIs, offline neural machine translation, NLP pipelines
- **Natural Language Processing**: Named Entity Recognition, POS tagging, dependency parsing, sentiment analysis
- **Backend Architecture**: RESTful API design with Flask, modular service-oriented architecture
- **Frontend Development**: Single-Page Application design, dynamic DOM manipulation, canvas-based data visualization
- **Data Engineering**: Hybrid in-memory + file-based caching, LRU eviction, JSON-based persistence
- **Security**: Environment variable management, session handling, input sanitization (XSS prevention)
- **API Integration**: OpenRouter (LLM), NewsAPI, YouTube Transcript API, RSS feeds
- **Version Control**: Git and GitHub workflow

---
