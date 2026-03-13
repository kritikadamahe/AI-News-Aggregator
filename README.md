
# 📰 AI News Aggregator

An AI-powered web application that summarizes news articles and YouTube videos using AI.
It supports contextual follow-up questions and stores user interaction data locally.

---

## 🚀 Features

- **News Article Summarization** – Paste any news URL and generate a concise AI-powered summary.
- **YouTube Video Summarization** – Extract video transcripts and generate structured summaries.
- **Context-Aware Follow-Up Chat** – Ask questions based on the generated summary.
- **Quiz Generation** – Automatically create quiz questions from summarized content.
- **Local Data Storage** – Articles, quizzes, and chat history stored using JSON files.
  
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
