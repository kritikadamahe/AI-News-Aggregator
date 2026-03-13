"""
app.py - Main Flask Application
================================
AI News Summarizer with RAG chat, quiz generation, and multi-source fetching.
"""

from flask import Flask, render_template, request, jsonify, session
import requests
import os
import uuid
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from PyPDF2 import PdfReader
from docx import Document
import json
import re

# Import storage modules
from storage import (
    ArticleStorage, 
    ChatHistoryStorage, 
    QuizStorage,
    ChatSessionManager
)
from config import *

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize storage instances
articles_storage = ArticleStorage(ARTICLES_FILE, cache_enabled=ENABLE_CACHE)
chat_storage = ChatHistoryStorage(CHAT_HISTORY_FILE, cache_enabled=ENABLE_CACHE)
quiz_storage = QuizStorage(QUIZZES_FILE, cache_enabled=ENABLE_CACHE)

# Initialize chat session manager for RAG
chat_sessions = ChatSessionManager()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_text_from_file(file):
    """Extract text from uploaded PDF, DOCX, or TXT files."""
    text = ""
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        try:
            reader = PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return None

    elif filename.endswith(".docx"):
        try:
            doc = Document(file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return None
    
    elif filename.endswith(".txt"):
        try:
            text = file.read().decode('utf-8')
        except Exception as e:
            print(f"TXT extraction error: {e}")
            return None
    
    else:
        return None

    return text.strip()


def call_openrouter_api(prompt, temperature=0.25, max_tokens=4000, model=None):
    """Generic function to call OpenRouter API."""
    if not OPENROUTER_API_KEY:
        print("ERROR: OpenRouter API key not found")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model or SUMMARY_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        print(f"[API] Calling OpenRouter with model: {model or SUMMARY_MODEL}")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=60)
        print(f"[API] Response Status: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            print(f"[API] Error Response: {error_text}")
            return None
        
        result = response.json()
        print(f"[API] Response received successfully")
        return result["choices"][0]["message"]["content"]
    
    except requests.exceptions.Timeout:
        print("[ERROR] API request timed out (60s)")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection failed - {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] API request failed - {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"[ERROR] Unexpected API response format - {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error - {e}")
        return None


# ============================================================================
# ROUTES - BASIC PAGES
# ============================================================================

@app.route("/")
def home():
    """Render main application page."""
    return render_template("index.html")


@app.route("/history")
def get_history():
    """Get all saved articles (most recent first)."""
    articles = articles_storage.get_recent(limit=50)
    return jsonify({
        "success": True,
        "articles": articles,
        "count": len(articles)
    })


# ============================================================================
# ROUTES - SUMMARIZATION
# ============================================================================

@app.route("/summarize", methods=["POST"])
def summarize():
    """Generate exam-ready summary from text or uploaded file."""
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "API key not configured"}), 500

    # Get text from form or file
    text = request.form.get("text", "")
    source = request.form.get("source", "User Upload")
    title = request.form.get("title", "Untitled Article")

    # Extract text from uploaded file if present
    if "file" in request.files and request.files["file"].filename != "":
        uploaded_file = request.files["file"]
        extracted_text = extract_text_from_file(uploaded_file)
        
        if extracted_text:
            text = extracted_text
            title = uploaded_file.filename
        else:
            return jsonify({"error": "Failed to extract text from file"}), 400

    # Validate input
    if not text.strip():
        return jsonify({"error": "No input provided"}), 400
    
    word_count = len(text.split())
    if word_count < 10:
        return jsonify({"error": "Text too short. Minimum 10 words required."}), 400
    if word_count > 5000:
        return jsonify({"error": "Text too long. Maximum 5000 words allowed."}), 400

    # Create summarization prompt
    summary_prompt = f"""
Convert the following news content into exam-ready notes.

IMPORTANT RULES:
- Do NOT use asterisks (*)
- Do NOT use markdown symbols
- Use plain text only with clear formatting

FORMAT STRICTLY LIKE THIS:

Topic:
[Clear topic title in 1-2 sentences]

Key Points:
1. [First key point]
2. [Second key point]
3. [Third key point]
4. [Fourth key point]
5. [Fifth key point]

Conclusion:
[Concise 2-3 sentence conclusion]

ARTICLE CONTENT:
{text}

Generate the exam-ready notes now:
"""

    # Generate summary
    summary = call_openrouter_api(
        prompt=summary_prompt, 
        temperature=SUMMARY_TEMPERATURE,
        max_tokens=SUMMARY_MAX_TOKENS
    )
    
    if not summary:
        return jsonify({"error": "AI summarization failed. Please try again."}), 500

    # Save article to storage
    saved_article = articles_storage.add_article(
        title=title,
        content=text,
        source=source,
        summary=summary
    )

    # --- Smart Classification using POS Tagging & Chunking ---
    try:
        from services.article_classifier import classify_article
        classification = classify_article(title, text)
        articles_storage.update(saved_article['id'], {
            'category': classification['category'],
            'classification_confidence': classification['confidence'],
            'classification_patterns': classification['patterns_matched']
        })
        saved_article['category'] = classification['category']
        saved_article['classification_confidence'] = classification['confidence']
    except Exception as e:
        print(f"[Classifier] Error classifying summarized article: {e}")

    # Generate quiz automatically
    quiz_data = generate_quiz_for_article(text, saved_article['id'])

    return jsonify({
        "success": True,
        "summary": summary,
        "article_id": saved_article['id'],
        "category": saved_article.get('category', 'general'),
        "classification_confidence": saved_article.get('classification_confidence', 0),
        "quiz": quiz_data
    })


# ============================================================================
# ROUTES - QUIZ GENERATION
# ============================================================================

def generate_quiz_for_article(article_text, article_id):
    """Internal function to generate MCQs and flashcards for an article."""
    truncated_text = article_text[:2500] if len(article_text) > 2500 else article_text
    
    # Generate MCQs
    mcq_prompt = f"""
Based on the following article, generate EXACTLY 5 multiple choice questions.

STRICT RESPONSE FORMAT (valid JSON only):
{{
  "questions": [
    {{
      "question": "What is the main topic discussed?",
      "options": ["A) First option", "B) Second option", "C) Third option", "D) Fourth option"],
      "correct_answer": "B",
      "explanation": "Brief explanation why B is correct"
    }}
  ]
}}

REQUIREMENTS:
- Exactly 5 questions
- Each question has 4 options labeled A, B, C, D
- Mark the correct answer (A, B, C, or D)
- Provide brief explanation
- Test important facts and concepts
- Questions should be clear and unambiguous

ARTICLE:
{truncated_text}

Generate the JSON now (no additional text):
"""

    mcq_response = call_openrouter_api(
        prompt=mcq_prompt, 
        temperature=QUIZ_TEMPERATURE,
        max_tokens=QUIZ_MAX_TOKENS,
        model=QUIZ_MODEL
    )
    
    # Generate Flashcards
    flashcard_prompt = f"""
Based on the following article, generate EXACTLY 5 flashcards for studying.

STRICT RESPONSE FORMAT (valid JSON only):
{{
  "flashcards": [
    {{
      "front": "What is [key term/concept]?",
      "back": "Clear, concise answer or definition"
    }}
  ]
}}

REQUIREMENTS:
- Exactly 5 flashcards
- Front: Question or term
- Back: Answer or definition (2-3 sentences max)
- Focus on important terminology and concepts
- Make them useful for studying

ARTICLE:
{truncated_text}

Generate the JSON now (no additional text):
"""

    flashcard_response = call_openrouter_api(
        prompt=flashcard_prompt, 
        temperature=QUIZ_TEMPERATURE,
        max_tokens=QUIZ_MAX_TOKENS,
        model=QUIZ_MODEL
    )
    
    def extract_json(text):
        """Extract JSON from response (handles cases where AI adds extra text)."""
        if not text:
            return None
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None
    
    mcq_data = extract_json(mcq_response)
    flashcard_data = extract_json(flashcard_response)
    
    mcqs = mcq_data.get("questions", []) if mcq_data else []
    flashcards = flashcard_data.get("flashcards", []) if flashcard_data else []
    
    # If AI failed to generate valid quiz, create empty arrays
    if not mcqs:
        mcqs = []
    if not flashcards:
        flashcards = []
    
    # Save quiz to storage
    quiz = quiz_storage.add_quiz(
        article_id=article_id,
        mcqs=mcqs,
        flashcards=flashcards
    )
    
    return {
        "mcqs": mcqs,
        "flashcards": flashcards,
        "quiz_id": quiz['id']
    }


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    """Generate quiz for an existing article."""
    data = request.get_json()
    article_id = data.get('article_id')
    
    if not article_id:
        return jsonify({"error": "article_id required"}), 400
    
    article = articles_storage.get_by_id(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    existing_quiz = quiz_storage.get_quiz_by_article(article_id)
    if existing_quiz:
        return jsonify({
            "success": True,
            "mcqs": existing_quiz['mcqs'],
            "flashcards": existing_quiz['flashcards'],
            "quiz_id": existing_quiz['id'],
            "cached": True
        })
    
    quiz_data = generate_quiz_for_article(article['content'], article_id)
    
    return jsonify({
        "success": True,
        **quiz_data,
        "cached": False
    })


@app.route("/quiz/<int:quiz_id>", methods=["GET"])
def get_quiz(quiz_id):
    """Retrieve a saved quiz by ID."""
    quiz = quiz_storage.get_by_id(quiz_id)
    
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    
    return jsonify({
        "success": True,
        "quiz": quiz
    })


@app.route("/quiz/<int:quiz_id>/submit", methods=["POST"])
def submit_quiz(quiz_id):
    """Submit quiz answers and calculate score."""
    data = request.get_json()
    answers = data.get('answers', [])
    
    quiz = quiz_storage.get_by_id(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404
    
    mcqs = quiz.get('mcqs', [])
    
    correct = 0
    results = []
    
    for i, user_answer in enumerate(answers):
        if i < len(mcqs):
            question = mcqs[i]
            correct_answer = question.get('correct_answer', '')
            is_correct = (user_answer == correct_answer)
            
            if is_correct:
                correct += 1
            
            results.append({
                "question_number": i + 1,
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "explanation": question.get('explanation', '')
            })
    
    total = len(mcqs)
    percentage = round((correct / total * 100), 1) if total > 0 else 0
    
    return jsonify({
        "success": True,
        "score": correct,
        "total": total,
        "percentage": percentage,
        "results": results
    })


# ============================================================================
# ROUTES - RAG CHAT SYSTEM
# ============================================================================

@app.route("/chat/start", methods=["POST"])
def start_chat():
    """Initialize a chat session for an article."""
    data = request.get_json()
    article_id = data.get('article_id')
    
    if not article_id:
        return jsonify({"error": "article_id required"}), 400
    
    article = articles_storage.get_by_id(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    session_id = str(uuid.uuid4())
    
    chat_sessions.create_session(
        session_id=session_id,
        article_id=article_id,
        article_content=article['content']
    )
    
    suggestion_prompt = f"""
Based on this article, suggest 3 interesting questions a reader might ask.

ARTICLE TITLE: {article['title']}

ARTICLE EXCERPT (first 500 characters):
{article['content'][:500]}...

RESPONSE FORMAT (strict JSON array):
["Question 1?", "Question 2?", "Question 3?"]

Generate the questions now (no additional text):
"""
    
    suggestions_response = call_openrouter_api(
        prompt=suggestion_prompt, 
        temperature=0.4,
        max_tokens=300
    )
    
    try:
        json_match = re.search(r'\[.*\]', suggestions_response, re.DOTALL)
        if json_match:
            suggestions = json.loads(json_match.group())
        else:
            suggestions = []
    except:
        suggestions = []
    
    if not suggestions or len(suggestions) < 3:
        suggestions = [
            "What is the main topic of this article?",
            "Who are the key people or organizations mentioned?",
            "What are the most important takeaways?"
        ]
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "article_title": article['title'],
        "suggested_questions": suggestions[:5]
    })


@app.route("/chat/message", methods=["POST"])
def chat_message():
    """Send a message in an active chat session."""
    data = request.get_json()
    session_id = data.get('session_id')
    message = data.get('message', '').strip()
    
    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400
    
    if len(message) > 500:
        return jsonify({"error": "Message too long. Maximum 500 characters."}), 400
    
    context = chat_sessions.get_context(session_id, max_messages=MAX_CHAT_HISTORY)
    
    if not context:
        return jsonify({"error": "Session not found or expired. Please start a new chat."}), 404
    
    conversation_history = ""
    for msg in context['messages']:
        role = "User" if msg['role'] == 'user' else "Assistant"
        conversation_history += f"{role}: {msg['content']}\n\n"
    
    chat_prompt = f"""
You are a helpful assistant answering questions about a news article.

ARTICLE CONTENT:
{context['article_content']}

CONVERSATION HISTORY:
{conversation_history if conversation_history else "[No previous messages]"}

CURRENT USER QUESTION:
{message}

INSTRUCTIONS:
- Answer based ONLY on the article content above
- If the answer is not in the article, clearly state: "This information is not mentioned in the article."
- Be concise and accurate (2-4 sentences maximum)
- Quote relevant parts of the article when helpful
- Maintain context from the conversation history
- Do not make up information

YOUR ANSWER:
"""
    
    ai_response = call_openrouter_api(
        prompt=chat_prompt, 
        temperature=CHAT_TEMPERATURE, 
        max_tokens=CHAT_MAX_TOKENS,
        model=CHAT_MODEL
    )
    
    if not ai_response:
        return jsonify({"error": "AI chat failed. Please try again."}), 500
    
    chat_sessions.add_message(session_id, 'user', message)
    chat_sessions.add_message(session_id, 'assistant', ai_response)
    
    session_data = chat_sessions.get_session(session_id)
    chat_storage.add_message(
        article_id=session_data['article_id'],
        user_message=message,
        ai_response=ai_response,
        session_id=session_id
    )
    
    return jsonify({
        "success": True,
        "response": ai_response
    })


@app.route("/chat/history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    """Get conversation history for a session."""
    context = chat_sessions.get_context(session_id)
    
    if not context:
        return jsonify({"error": "Session not found"}), 404
    
    return jsonify({
        "success": True,
        "messages": context['messages']
    })


@app.route("/chat/clear/<session_id>", methods=["POST"])
def clear_chat(session_id):
    """Clear a chat session."""
    chat_sessions.clear_session(session_id)
    
    return jsonify({
        "success": True,
        "message": "Chat session cleared"
    })


# ============================================================================
# ROUTES - ARTICLE MANAGEMENT
# ============================================================================

@app.route("/article/<int:article_id>", methods=["GET"])
def get_article(article_id):
    """Get full article details including associated quiz."""
    article = articles_storage.get_by_id(article_id)
    
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    quiz = quiz_storage.get_quiz_by_article(article_id)
    
    return jsonify({
        "success": True,
        "article": article,
        "has_quiz": quiz is not None,
        "quiz_id": quiz['id'] if quiz else None
    })


@app.route("/article/<int:article_id>", methods=["DELETE"])
def delete_article(article_id):
    """Delete an article and all associated data."""
    success = articles_storage.delete(article_id)
    
    if not success:
        return jsonify({"error": "Article not found"}), 404
    
    quiz = quiz_storage.get_quiz_by_article(article_id)
    if quiz:
        quiz_storage.delete(quiz['id'])
    
    chat_storage.clear_conversation(article_id)
    
    return jsonify({
        "success": True,
        "message": "Article and associated data deleted"
    })


@app.route("/search", methods=["GET"])
def search_articles():
    """Search articles by keywords."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({"error": "Query parameter 'q' required"}), 400
    
    keywords = query.split()
    results = articles_storage.search_by_keywords(keywords)
    
    return jsonify({
        "success": True,
        "results": results,
        "count": len(results),
        "query": query
    })


# ============================================================================
# ROUTES - NEWS FETCHING (Feature 1)
# ============================================================================

from services.fetch_news import NewsAPIFetcher, URLScraper, YouTubeTranscriptExtractor, fetch_news_comprehensive
from services.article_classifier import classify_article
from services.misinformation_detector import analyze_article as detect_misinformation

@app.route("/fetch-news", methods=["POST"])
def fetch_news():
    """Fetch news from various sources."""
    try:
        data = request.get_json(force=True, silent=False)
    except Exception as e:
        print(f"[ERROR] Invalid JSON in request: {e}")
        return jsonify({"error": "Invalid JSON in request body"}), 400
    
    if data is None:
        return jsonify({"error": "No JSON data provided"}), 400
    
    source_type = data.get('source_type')
    
    if not source_type:
        return jsonify({"error": "source_type required (api, url, or youtube)"}), 400
    
    # NEWS API
    if source_type == 'api':
        fetcher = NewsAPIFetcher()
        
        query = data.get('query')
        if query:
            articles = fetcher.search_articles(
                query=query,
                page_size=data.get('limit', 10)
            )
        else:
            articles = fetcher.fetch_top_headlines(
                category=data.get('category'),
                country=data.get('country', 'us'),
                page_size=data.get('limit', 10)
            )
        
        if not articles:
            return jsonify({"error": "No articles found or API error"}), 404
        
        saved_articles = []
        for article in articles:
            saved = articles_storage.add_article(
                title=article['title'],
                content=article['content'],
                source=article['source'],
                url=article.get('url'),
                category=article.get('category')
            )
            # --- Smart Classification using POS Tagging & Chunking ---
            try:
                classification = classify_article(saved.get('title', ''), saved.get('content', ''))
                articles_storage.update(saved['id'], {
                    'category': classification['category'],
                    'classification_confidence': classification['confidence'],
                    'classification_patterns': classification['patterns_matched']
                })
                saved['category'] = classification['category']
                saved['classification_confidence'] = classification['confidence']
                saved['classification_patterns'] = classification['patterns_matched']
            except Exception as e:
                print(f"[Classifier] Error classifying article {saved.get('id')}: {e}")
                saved['category'] = saved.get('category') or 'general'
            saved_articles.append(saved)
        
        return jsonify({
            "success": True,
            "articles": saved_articles,
            "count": len(saved_articles),
            "source": "NewsAPI"
        })
    
    # URL SCRAPING
    elif source_type == 'url':
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "url required"}), 400
        
        scraper = URLScraper()
        article = scraper.scrape_article(url)
        
        if not article:
            return jsonify({"error": "Failed to scrape article from URL"}), 400
        
        saved = articles_storage.add_article(
            title=article['title'],
            content=article['content'],
            source=article.get('source', 'Web'),
            url=article['url']
        )
        # --- Smart Classification using POS Tagging & Chunking ---
        try:
            classification = classify_article(saved.get('title', ''), saved.get('content', ''))
            articles_storage.update(saved['id'], {
                'category': classification['category'],
                'classification_confidence': classification['confidence'],
                'classification_patterns': classification['patterns_matched']
            })
            saved['category'] = classification['category']
            saved['classification_confidence'] = classification['confidence']
            saved['classification_patterns'] = classification['patterns_matched']
        except Exception as e:
            print(f"[Classifier] Error classifying URL article: {e}")
            saved['category'] = saved.get('category') or 'general'
        
        return jsonify({
            "success": True,
            "article": saved,
            "source": "URL Scraper"
        })
    
    # YOUTUBE TRANSCRIPT
    elif source_type == 'youtube':
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "url required"}), 400
        
        extractor = YouTubeTranscriptExtractor()
        transcript = extractor.get_transcript(url)
        
        if not transcript:
            return jsonify({"error": "Failed to get YouTube transcript. Video may not have captions."}), 400
        
        saved = articles_storage.add_article(
            title=transcript['title'],
            content=transcript['content'],
            source='YouTube',
            url=transcript['url']
        )
        # --- Smart Classification using POS Tagging & Chunking ---
        try:
            classification = classify_article(saved.get('title', ''), saved.get('content', ''))
            articles_storage.update(saved['id'], {
                'category': classification['category'],
                'classification_confidence': classification['confidence'],
                'classification_patterns': classification['patterns_matched']
            })
            saved['category'] = classification['category']
            saved['classification_confidence'] = classification['confidence']
            saved['classification_patterns'] = classification['patterns_matched']
        except Exception as e:
            print(f"[Classifier] Error classifying YouTube article: {e}")
            saved['category'] = saved.get('category') or 'general'
        
        return jsonify({
            "success": True,
            "article": saved,
            "source": "YouTube"
        })
    
    else:
        return jsonify({"error": "Invalid source_type. Must be 'api', 'url', or 'youtube'"}), 400


# ============================================================================
# ROUTES - COMPREHENSIVE NEWS FETCHING (NewsAPI + RSS)
# ============================================================================

@app.route("/fetch-comprehensive", methods=["POST"])
def fetch_comprehensive():
    """
    Fetch news from both NewsAPI and RSS feeds for comprehensive coverage.
    Enables comparative analysis of same topic across multiple sources.
    """
    try:
        data = request.get_json(force=True, silent=False)
    except Exception as e:
        print(f"[Comprehensive] Invalid JSON in request: {e}")
        return jsonify({"error": "Invalid JSON in request body"}), 400
    
    if data is None:
        return jsonify({"error": "No JSON data provided"}), 400
    
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({"error": "topic field is required"}), 400
    
    use_rss = data.get('use_rss', True)
    use_api = data.get('use_api', True)
    
    if not use_rss and not use_api:
        return jsonify({"error": "At least one source (RSS or API) must be enabled"}), 400
    
    print(f"[Comprehensive] Request: topic='{topic}', use_rss={use_rss}, use_api={use_api}")
    
    try:
        # Fetch articles from both sources
        articles = fetch_news_comprehensive(topic, use_rss=use_rss, use_api=use_api)
        
        if not articles:
            return jsonify({
                "success": False,
                "error": "No articles found from any source"
            }), 404
        
        # Save articles and apply classifications
        saved_articles = []
        api_count = 0
        rss_count = 0
        
        for article in articles:
            try:
                # Save article to storage
                saved = articles_storage.add_article(
                    title=article.get('title', ''),
                    content=article.get('content', ''),
                    source=article.get('source', 'Unknown'),
                    url=article.get('url', ''),
                    category=article.get('category', 'general'),
                    summary=None
                )
                
                # Apply smart classification
                try:
                    classification = classify_article(
                        saved.get('title', ''),
                        saved.get('content', '')
                    )
                    articles_storage.update(saved['id'], {
                        'category': classification['category'],
                        'classification_confidence': classification['confidence'],
                        'classification_patterns': classification['patterns_matched']
                    })
                    saved['category'] = classification['category']
                    saved['classification_confidence'] = classification['confidence']
                    saved['classification_patterns'] = classification['patterns_matched']
                except Exception as e:
                    print(f"[Comprehensive] Classifier error for article {saved.get('id')}: {e}")
                    saved['category'] = 'general'
                
                # Track source
                saved['fetched_via'] = article.get('fetched_via', 'unknown')
                saved_articles.append(saved)
                
                if article.get('fetched_via') == 'api':
                    api_count += 1
                elif article.get('fetched_via') == 'rss':
                    rss_count += 1
            
            except Exception as e:
                print(f"[Comprehensive] Error saving article: {e}")
                continue
        
        # Get source breakdown
        sources_breakdown = {}
        for article in saved_articles:
            source = article.get('source', 'Unknown')
            if source not in sources_breakdown:
                sources_breakdown[source] = 0
            sources_breakdown[source] += 1
        
        print(f"[Comprehensive] Response: {len(saved_articles)} articles, API: {api_count}, RSS: {rss_count}")
        
        return jsonify({
            "success": True,
            "count": len(saved_articles),
            "articles": saved_articles,
            "sources_breakdown": {
                "newsapi": api_count,
                "rss": rss_count,
                "by_source": sources_breakdown
            },
            "unique_sources": len(sources_breakdown),
            "topic": topic
        })
    
    except Exception as e:
        print(f"[Comprehensive] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


# ============================================================================
# ROUTES - MISINFORMATION & BIAS ANALYSIS
# ============================================================================

@app.route("/analyze/<int:article_id>", methods=["GET"])
def analyze_article_route(article_id):
    """
    Analyze an article for misinformation, bias, and manipulation.
    Uses hybrid rule-based + pre-trained model approach.
    Results are cached in the article object to avoid re-analysis.
    """
    article = articles_storage.get_by_id(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404

    # Return cached results if available
    if article.get('analysis_results') and article['analysis_results'].get('overall_score', -1) >= 0:
        return jsonify({
            "success": True,
            "article_id": article_id,
            "analysis": article['analysis_results'],
            "cached": True
        })

    # Run analysis
    try:
        analysis = detect_misinformation(
            title=article.get('title', ''),
            content=article.get('content', ''),
            source=article.get('source', ''),
            category=article.get('category', '')
        )

        # Store results in article
        articles_storage.update_analysis(article_id, analysis)

        return jsonify({
            "success": True,
            "article_id": article_id,
            "analysis": analysis,
            "cached": False
        })
    except Exception as e:
        print(f"[Analyzer] Error analyzing article {article_id}: {e}")
        return jsonify({
            "success": True,
            "article_id": article_id,
            "analysis": {
                "overall_score": -1,
                "rating": "unavailable",
                "breakdown": {},
                "specific_warnings": ["Analysis unavailable"],
                "recommendation": "Analysis could not be completed."
            },
            "cached": False
        })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(413)
def request_entity_too_large(e):
    """Handle file too large errors."""
    return jsonify({"error": "File too large. Maximum 10MB allowed."}), 413


# ============================================================================
# STARTUP & CLEANUP
# ============================================================================

@app.before_request
def startup():
    """Run before each request (ensures cleanup happens)."""
    if not hasattr(app, '_startup_done'):
        removed = chat_sessions.cleanup_old_sessions(max_age_hours=SESSION_MAX_AGE_HOURS)
        print(f"Startup: Cleaned up {removed} old chat sessions")
        app._startup_done = True


# ============================================================================
# MAIN
# ============================================================================
# DIAGNOSTIC ENDPOINTS
# ============================================================================

@app.route("/debug-config")
def debug_config():
    """Show loaded configuration (masked for security)."""
    def mask_key(key):
        if not key:
            return "NOT SET"
        if len(key) <= 10:
            return key
        return key[:10] + "..." + key[-5:]
    
    return jsonify({
        "openrouter_key": mask_key(OPENROUTER_API_KEY),
        "newsapi_key": mask_key(NEWSAPI_KEY),
        "openrouter_url": OPENROUTER_API_URL,
        "newsapi_url": NEWSAPI_BASE_URL,
        "summary_model": SUMMARY_MODEL
    })


@app.route("/demo")
def demo():
    """Demo endpoint with sample data (no API keys needed)."""
    return jsonify({
        "success": True,
        "message": "Demo mode - This works without API keys!",
        "sample_article": {
            "title": "Sample News Article",
            "summary": "This is a demonstration of the AI News Aggregator. To use summarization and news fetching, please add valid API keys to your .env file.",
            "steps": [
                "1. Get OpenRouter API key from https://openrouter.ai/",
                "2. Get NewsAPI key from https://newsapi.org/",
                "3. Update your .env file with these keys",
                "4. Restart the Flask app"
            ]
        }
    })


@app.route("/test-url-scrape", methods=["POST"])
def test_url_scrape():
    """Test scraping a specific URL."""
    data = request.get_json()
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "url parameter required"}), 400
    
    scraper = URLScraper()
    result = scraper.scrape_article(url)
    
    if result:
        return jsonify({
            "success": True,
            "title": result.get("title"),
            "content_length": len(result.get("content", "")),
            "source": result.get("source"),
            "preview": result.get("content", "")[:200] + "..."
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to scrape URL"
        }), 400


@app.route("/test-api")
def test_api():
    """Test if APIs are working."""
    results = {
        "openrouter": None,
        "newsapi": None,
        "openrouter_details": {},
        "newsapi_details": {},
        "errors": []
    }
    
    # Test OpenRouter
    try:
        print("[TEST-API] Testing OpenRouter...")
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": SUMMARY_MODEL,
            "messages": [{"role": "user", "content": "Say 'hello world'"}],
            "temperature": 0.5,
            "max_tokens": 100
        }
        print(f"[TEST-API] URL: {OPENROUTER_API_URL}")
        print(f"[TEST-API] Model: {SUMMARY_MODEL}")
        
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=15)
        print(f"[TEST-API] Status: {response.status_code}")
        
        results["openrouter_details"]["status_code"] = response.status_code
        results["openrouter_details"]["response_preview"] = response.text[:300]
        
        if response.status_code == 200:
            results["openrouter"] = "✓ Working"
        else:
            results["openrouter"] = f"✗ Error {response.status_code}"
            results["errors"].append(f"OpenRouter: Status {response.status_code} - {response.text[:200]}")
    except Exception as e:
        results["openrouter"] = f"✗ {str(e)}"
        results["openrouter_details"]["error"] = str(e)
        results["errors"].append(f"OpenRouter: {str(e)}")
    
    # Test NewsAPI
    try:
        print("[TEST-API] Testing NewsAPI...")
        if not NEWSAPI_KEY or NEWSAPI_KEY == "your_newsapi_key_here":
            results["newsapi"] = "✗ Key not configured"
            results["errors"].append("NewsAPI key is not set")
        else:
            params = {'country': 'us', 'pageSize': 1, 'apiKey': NEWSAPI_KEY}
            response = requests.get(f"{NEWSAPI_BASE_URL}/top-headlines", params=params, timeout=10)
            
            results["newsapi_details"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                results["newsapi"] = "✓ Working"
            else:
                results["newsapi"] = f"✗ Error {response.status_code}"
                results["newsapi_details"]["error_preview"] = response.text[:200]
                results["errors"].append(f"NewsAPI: Status {response.status_code}")
    except Exception as e:
        results["newsapi"] = f"✗ {str(e)}"
        results["newsapi_details"]["error"] = str(e)
        results["errors"].append(f"NewsAPI: {str(e)}")
    
    return jsonify(results)


# ============================================================================

if __name__ == "__main__":
    # Configure max file upload size
    app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
