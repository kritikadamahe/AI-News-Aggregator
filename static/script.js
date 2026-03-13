// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

let currentArticleId = null;
let currentQuizId = null;
let currentFlashcards = [];
let currentCardIndex = 0;
let currentChatSessionId = null;
let quizAnswers = [];

// Initialize page
document.addEventListener("DOMContentLoaded", () => {
    // Ensure loading overlay is hidden on page load
    const loadingOverlay = document.getElementById("loading-overlay");
    if (loadingOverlay) {
        loadingOverlay.style.display = "none";
    }
});

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function showLoading(message = "Processing...") {
    document.getElementById("loading-overlay").style.display = "flex";
    document.getElementById("loading-text").textContent = message;
}

function hideLoading() {
    document.getElementById("loading-overlay").style.display = "none";
}

function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ============================================================================
// TAB SWITCHING - UPDATED FOR NEW STRUCTURE
// ============================================================================

function switchTab(tabName) {
    // Hide all tab panels
    const panels = document.querySelectorAll(".tab-panel");
    panels.forEach(panel => panel.classList.remove("active"));
    
    // Remove active class from all tab buttons
    const buttons = document.querySelectorAll(".tab-btn");
    buttons.forEach(btn => btn.classList.remove("active"));
    
    // Show selected tab panel and activate button
    const selectedPanel = document.getElementById(`${tabName}-content`);
    if (selectedPanel) {
        selectedPanel.classList.add("active");
    }
    
    // Activate clicked button
    const clickedBtn = document.querySelector(`[data-tab="${tabName}"]`);
    if (clickedBtn) {
        clickedBtn.classList.add("active");
    }
}

// ============================================================================
// PASTE TEXT TAB
// ============================================================================

function clearText() {
    document.getElementById("paste-text").value = "";
}

function summarizeText() {
    const text = document.getElementById("paste-text").value.trim();
    
    if (!text) {
        showToast("Please paste some text", "error");
        return;
    }
    
    const formData = new FormData();
    formData.append("text", text);
    formData.append("source", "Pasted Text");
    
    showLoading("Summarizing your article...");
    
    fetch("/summarize", {
        method: "POST",
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                throw new Error(errData.error || "Server error (" + response.status + ")");
            }).catch(e => {
                if (e.message) throw e;
                throw new Error("Server error (" + response.status + ")");
            });
        }
        return response.json();
    })
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentArticleId = data.article_id;
            currentQuizId = data.quiz.quiz_id;
            
            displaySummary(data.summary, data.category);
            document.getElementById("paste-text").value = "";
            showToast("Article summarized successfully!", "success");
        } else {
            showToast(data.error || "Failed to summarize", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

// ============================================================================
// FILE UPLOAD TAB
// ============================================================================

function handleFileSelect() {
    const fileInput = document.getElementById("file-input");
    const file = fileInput.files[0];
    
    if (file) {
        document.getElementById("file-name").textContent = file.name;
        document.getElementById("file-info").style.display = "block";
    }
}

function summarizeFile() {
    const fileInput = document.getElementById("file-input");
    const file = fileInput.files[0];
    
    if (!file) {
        showToast("Please select a file", "error");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("source", "File Upload");
    
    showLoading("Extracting and summarizing file...");
    
    fetch("/summarize", {
        method: "POST",
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                throw new Error(errData.error || "Server error (" + response.status + ")");
            }).catch(e => {
                if (e.message) throw e;
                throw new Error("Server error (" + response.status + ")");
            });
        }
        return response.json();
    })
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentArticleId = data.article_id;
            currentQuizId = data.quiz.quiz_id;
            
            displaySummary(data.summary, data.category);
            fileInput.value = "";
            document.getElementById("file-info").style.display = "none";
            showToast("File processed successfully!", "success");
        } else {
            showToast(data.error || "Failed to process file", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

// ============================================================================
// FETCH NEWS TAB
// ============================================================================

function updateFetchOptions() {
    const sourceType = document.getElementById("source-type").value;
    
    // Hide all fetch options
    const allOptions = document.querySelectorAll(".fetch-options");
    allOptions.forEach(opt => {
        opt.classList.remove("visible");
        opt.style.display = "none";
    });
    
    // Update button text
    const btnText = document.getElementById("fetch-btn-text");
    
    // Show selected fetch options
    if (sourceType === "api-headlines") {
        const elem = document.getElementById("api-headlines-options");
        if (elem) {
            elem.classList.add("visible");
            elem.style.display = "block";
        }
        if (btnText) btnText.textContent = "Fetch & Summarize";
    } else if (sourceType === "api-search") {
        const elem = document.getElementById("api-search-options");
        if (elem) {
            elem.classList.add("visible");
            elem.style.display = "block";
        }
        if (btnText) btnText.textContent = "Fetch & Summarize";
    } else if (sourceType === "comprehensive") {
        const elem = document.getElementById("comprehensive-options");
        if (elem) {
            elem.classList.add("visible");
            elem.style.display = "block";
        }
        if (btnText) btnText.textContent = "Fetch from Multiple Sources";
    } else if (sourceType === "url") {
        const elem = document.getElementById("url-options");
        if (elem) {
            elem.classList.add("visible");
            elem.style.display = "block";
        }
        if (btnText) btnText.textContent = "Fetch & Summarize";
    } else if (sourceType === "youtube") {
        const elem = document.getElementById("youtube-options");
        if (elem) {
            elem.classList.add("visible");
            elem.style.display = "block";
        }
        if (btnText) btnText.textContent = "Fetch & Summarize";
    }
}

function fetchNews() {
    const sourceType = document.getElementById("source-type").value;
    let payload = {};
    
    if (sourceType === "api-headlines") {
        payload = {
            source_type: "api",
            category: document.getElementById("category").value,
            country: document.getElementById("country").value,
            limit: 5
        };
    } else if (sourceType === "api-search") {
        payload = {
            source_type: "api",
            query: document.getElementById("search-query").value,
            limit: 5
        };
        
        if (!payload.query) {
            showToast("Please enter search keywords", "error");
            return;
        }
    } else if (sourceType === "url") {
        payload = {
            source_type: "url",
            url: document.getElementById("article-url").value
        };
        
        if (!payload.url) {
            showToast("Please enter an article URL", "error");
            return;
        }
    } else if (sourceType === "youtube") {
        payload = {
            source_type: "youtube",
            url: document.getElementById("youtube-url").value
        };
        
        if (!payload.url) {
            showToast("Please enter a YouTube URL", "error");
            return;
        }
    }
    
    showLoading("Fetching articles...");
    
    fetch("/fetch-news", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            if (sourceType === "url" || sourceType === "youtube") {
                currentArticleId = data.article.id;
                displaySummaryForFetched(data.article);
            } else {
                displayFetchedArticles(data.articles);
            }
            showToast(`Articles fetched from ${data.source}!`, "success");
        } else {
            showToast(data.error || "Failed to fetch articles", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

// ============================================================================
// COMPREHENSIVE NEWS FETCHING (NewsAPI + RSS)
// ============================================================================

function updateComprehensiveOptions() {
    // This function can be expanded later for dynamic UI updates
    console.log("Comprehensive fetch options updated");
}

function fetchComprehensiveNews() {
    const topic = document.getElementById("comprehensive-topic").value.trim();
    
    if (!topic) {
        showToast("Please enter a topic to search for", "error");
        return;
    }
    
    const useRss = document.getElementById("comprehensive-use-rss").checked;
    const useApi = document.getElementById("comprehensive-use-api").checked;
    
    if (!useRss && !useApi) {
        showToast("Please select at least one source (RSS or NewsAPI)", "error");
        return;
    }
    
    const payload = {
        topic: topic,
        use_rss: useRss,
        use_api: useApi
    };
    
    showLoading(`Fetching "${topic}" from multiple sources...`);
    
    fetch("/fetch-comprehensive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            // Display source breakdown
            const sourceBreakdown = data.sources_breakdown || {};
            let breakdownMsg = `Found ${data.count} articles`;
            
            if (sourceBreakdown.newsapi > 0) {
                breakdownMsg += ` (${sourceBreakdown.newsapi} from NewsAPI`;
                if (sourceBreakdown.rss > 0) {
                    breakdownMsg += `, ${sourceBreakdown.rss} from RSS feeds)`;
                } else {
                    breakdownMsg += ")";
                }
            } else if (sourceBreakdown.rss > 0) {
                breakdownMsg += ` (${sourceBreakdown.rss} from RSS feeds)`;
            }
            
            showToast(breakdownMsg, "success");
            
            // Display articles with source tracking
            displayComprehensiveArticles(data.articles, data.sources_breakdown);
        } else {
            showToast(data.error || "Failed to fetch articles", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function displayComprehensiveArticles(articles, sourcesBreakdown) {
    const grid = document.getElementById("articles-grid");
    grid.innerHTML = "";
    
    // Add source breakdown info
    const breakdownDiv = document.createElement("div");
    breakdownDiv.className = "comprehensive-breakdown";
    breakdownDiv.innerHTML = `
        <div class="breakdown-info">
            <div class="breakdown-stat">
                <span class="stat-label">Total Articles:</span>
                <span class="stat-value">${articles.length}</span>
            </div>
            ${sourcesBreakdown.newsapi > 0 ? `
                <div class="breakdown-stat">
                    <span class="stat-label">From NewsAPI:</span>
                    <span class="stat-value">${sourcesBreakdown.newsapi}</span>
                </div>
            ` : ''}
            ${sourcesBreakdown.rss > 0 ? `
                <div class="breakdown-stat">
                    <span class="stat-label">From RSS:</span>
                    <span class="stat-value">${sourcesBreakdown.rss}</span>
                </div>
            ` : ''}
            ${sourcesBreakdown.by_source ? `
                <div class="breakdown-stat">
                    <span class="stat-label">Unique Sources:</span>
                    <span class="stat-value">${Object.keys(sourcesBreakdown.by_source).length}</span>
                </div>
            ` : ''}
        </div>
    `;
    grid.appendChild(breakdownDiv);
    
    // Group articles by source
    const sourceGroups = {};
    articles.forEach(article => {
        const source = article.source || "Unknown";
        if (!sourceGroups[source]) {
            sourceGroups[source] = [];
        }
        sourceGroups[source].push(article);
    });
    
    // Display articles grouped by source
    Object.entries(sourceGroups).forEach(([source, sourceArticles]) => {
        const sourceHeaderDiv = document.createElement("div");
        sourceHeaderDiv.className = "source-group-header";
        sourceHeaderDiv.innerHTML = `
            <div class="source-badge">${source}</div>
            <span class="source-count">${sourceArticles.length} articles</span>
        `;
        grid.appendChild(sourceHeaderDiv);
        
        sourceArticles.forEach(article => {
            const card = document.createElement("div");
            card.className = "article-card comprehensive-article-card";
            const category = article.category || "general";
            const categoryBadge = `<span class="category-badge category-${category}">${category}</span>`;
            const fetchedVia = article.fetched_via === 'rss' ? '📡 RSS' : '🌐 API';
            
            card.innerHTML = `
                <div class="article-card-header">
                    <h3>${article.title}</h3>
                    <div class="article-badges">
                        ${categoryBadge}
                        <span class="source-type-badge">${fetchedVia}</span>
                    </div>
                </div>
                <p>${article.content.substring(0, 120)}...</p>
                <div class="article-card-footer">
                    <span class="article-source">${article.source}</span>
                    <a href="${article.url}" target="_blank" class="article-link">Read →</a>
                </div>
                <button class="btn btn-primary" style="margin-top: 10px; width: 100%;" onclick="summarizeArticle(${article.id})">
                    Summarize
                </button>
            `;
            grid.appendChild(card);
        });
    });
}

function displayFetchedArticles(articles) {
    const grid = document.getElementById("articles-grid");
    grid.innerHTML = "";
    
    articles.forEach(article => {
        const card = document.createElement("div");
        card.className = "article-card";
        const category = article.category || "general";
        const categoryBadge = `<span class="category-badge category-${category}">${category}</span>`;
        card.innerHTML = `
            <div class="article-card-header">
                <h3>${article.title}</h3>
                ${categoryBadge}
            </div>
            <p>${article.content.substring(0, 100)}...</p>
            <div class="article-card-footer">
                <span class="article-source">${article.source}</span>
            </div>
            <button class="btn btn-primary" style="margin-top: 10px; width: 100%;" onclick="summarizeArticle(${article.id})">
                Summarize
            </button>
        `;
        grid.appendChild(card);
    });
}

function displaySummaryForFetched(article) {
    currentArticleId = article.id;
    showLoading("Generating summary...");
    
    const formData = new FormData();
    formData.append("text", article.content);
    formData.append("source", article.source);
    formData.append("title", article.title);
    
    fetch("/summarize", {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentArticleId = data.article_id;
            currentQuizId = data.quiz.quiz_id;
            displaySummary(data.summary, data.category);
            showToast("Article summarized!", "success");
        } else {
            showToast("Failed to summarize article", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function summarizeArticle(articleId) {
    fetch(`/article/${articleId}`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const article = data.article;
            currentArticleId = articleId;
            
            if (data.has_quiz) {
                currentQuizId = data.quiz_id;
            }
            
            const formData = new FormData();
            formData.append("text", article.content);
            formData.append("source", article.source);
            
            showLoading("Summarizing...");
            
            return fetch("/summarize", {
                method: "POST",
                body: formData
            });
        }
        throw new Error("Failed to get article");
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentArticleId = data.article_id;
            currentQuizId = data.quiz.quiz_id;
            displaySummary(data.summary, data.category);
            showToast("Summary ready!", "success");
        } else {
            showToast("Failed to summarize", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

// ============================================================================
// DISPLAY SUMMARY
// ============================================================================

function displaySummary(summary, category) {
    // Cancel any ongoing speech from a previous summary
    if (typeof cancelSpeech === 'function') cancelSpeech();
    if (typeof hideTTSControls === 'function') hideTTSControls();

    const outputElement = document.getElementById("output");
    const outputSection = document.getElementById("output-section");
    
    console.log("displaySummary called", {summary, category, currentArticleId});
    
    // Show relationship tools in navbar
    const navTools = document.getElementById("navbar-relationship-tools");
    if (navTools && currentArticleId) {
        navTools.style.display = "flex";
        console.log("Navbar relationship tools shown");
    }
    
    // ---- CLEAR OLD ANALYSIS BANNER IMMEDIATELY ----
    // Each article must get its own fresh analysis, remove any previous one
    const oldBanner = document.getElementById("analysis-banner");
    if (oldBanner) oldBanner.remove();

    const cat = category || "general";
    const categoryBadgeHtml = `<div class="summary-category-wrapper"><span class="category-badge category-${cat}">${cat.charAt(0).toUpperCase() + cat.slice(1)}</span></div>`;
    
    if (outputElement) {
        outputElement.innerHTML = categoryBadgeHtml + `<p>${summary.replace(/\n/g, '<br>')}</p>`;
    }
    
    if (outputSection) {
        outputSection.style.display = "block";
        console.log("Output section made visible");
        setTimeout(() => {
            const exploreSection = outputSection.querySelector('[style*="Explore Relationships"]');
            if (exploreSection) {
                console.log("Found Explore Relationships section");
            }
            outputSection.scrollIntoView({ behavior: "smooth" });
        }, 100);
    }

    // Trigger misinformation analysis for THIS specific article
    if (currentArticleId) {
        fetchMisinformationAnalysis(currentArticleId);
    }
}

// ============================================================================
// MISINFORMATION & BIAS ANALYSIS
// ============================================================================

// Track the article ID we are currently analyzing so stale responses are ignored
let _pendingAnalysisArticleId = null;

function fetchMisinformationAnalysis(articleId) {
    // Mark which article we're analyzing — if user switches articles before
    // the response arrives, the stale response will be discarded
    _pendingAnalysisArticleId = articleId;

    // Show a small loading placeholder while analysis runs
    showAnalysisLoading();

    fetch(`/analyze/${articleId}`)
    .then(response => response.json())
    .then(data => {
        // GUARD: if user already moved to a different article, discard
        if (_pendingAnalysisArticleId !== articleId) {
            return;
        }

        // Remove the loading placeholder
        removeAnalysisLoading();

        if (data.success && data.analysis && data.analysis.overall_score >= 0) {
            displayAnalysisBanner(data.analysis, articleId);
        }
    })
    .catch(error => {
        if (_pendingAnalysisArticleId === articleId) {
            removeAnalysisLoading();
        }
        console.log("Analysis unavailable:", error.message);
    });
}

function showAnalysisLoading() {
    // Remove any existing banner or placeholder
    const old = document.getElementById("analysis-banner");
    if (old) old.remove();
    const oldPlaceholder = document.getElementById("analysis-loading");
    if (oldPlaceholder) oldPlaceholder.remove();

    const placeholder = document.createElement("div");
    placeholder.id = "analysis-loading";
    placeholder.className = "analysis-banner analysis-loading-state";
    placeholder.innerHTML = `
        <div class="analysis-header">
            <div class="analysis-summary">
                <span class="analysis-icon">🔍</span>
                <span class="analysis-label">Analyzing article for bias & misinformation...</span>
            </div>
            <span class="analysis-loading-spinner"></span>
        </div>
    `;

    const outputSection = document.getElementById("output-section");
    if (outputSection) {
        const summaryPanel = outputSection.querySelector('.result-panel, .output-box, .result-content');
        if (summaryPanel) {
            summaryPanel.parentNode.insertBefore(placeholder, summaryPanel);
        } else {
            outputSection.insertBefore(placeholder, outputSection.firstChild);
        }
    }
}

function removeAnalysisLoading() {
    const placeholder = document.getElementById("analysis-loading");
    if (placeholder) placeholder.remove();
}

function displayAnalysisBanner(analysis, articleId) {
    // Remove any existing banner and loading placeholder
    const existingBanner = document.getElementById("analysis-banner");
    if (existingBanner) existingBanner.remove();
    removeAnalysisLoading();

    // GUARD: only display if this analysis is still for the current article
    if (articleId !== undefined && articleId !== currentArticleId) {
        return;
    }

    const rating = analysis.rating;
    const score = analysis.overall_score;
    const warnings = analysis.specific_warnings || [];
    const breakdown = analysis.breakdown || {};
    const recommendation = analysis.recommendation || "";

    // Determine icon, color class, and label
    let icon, label, bannerClass;
    if (rating === "green") {
        icon = "✅";
        label = "Reliable";
        bannerClass = "analysis-green";
    } else if (rating === "yellow") {
        icon = "⚠️";
        label = "Read Critically";
        bannerClass = "analysis-yellow";
    } else if (rating === "red") {
        icon = "🛑";
        label = "High Manipulation Risk";
        bannerClass = "analysis-red";
    } else {
        return; // unavailable, don't show banner
    }

    // Build breakdown details HTML
    let detailsHtml = '<div class="analysis-details">';
    
    // Passive voice
    if (breakdown.passive_voice) {
        const pv = breakdown.passive_voice;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Passive Voice</span>
            <span class="detail-value">${pv.percentage}%</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(pv.score, 100)}%"></div></div>
            ${pv.examples.length > 0 ? `<div class="detail-examples">${pv.examples.map(e => `<span class="example-chip">"${truncateText(e, 60)}"</span>`).join('')}</div>` : ''}
        </div>`;
    }

    // Unattributed claims
    if (breakdown.unattributed_claims) {
        const uc = breakdown.unattributed_claims;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Unattributed Claims</span>
            <span class="detail-value">${uc.count} found</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(uc.score, 100)}%"></div></div>
            ${uc.examples.length > 0 ? `<div class="detail-examples">${uc.examples.map(e => `<span class="example-chip">"${truncateText(e, 60)}"</span>`).join('')}</div>` : ''}
        </div>`;
    }

    // Hedging
    if (breakdown.hedging) {
        const hd = breakdown.hedging;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Hedging Density</span>
            <span class="detail-value">${hd.density} per 100 words</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(hd.score, 100)}%"></div></div>
            ${hd.examples.length > 0 ? `<div class="detail-examples">${hd.examples.map(e => `<span class="example-chip">${e}</span>`).join('')}</div>` : ''}
        </div>`;
    }

    // Emotional Language
    if (breakdown.emotional_language) {
        const el = breakdown.emotional_language;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Emotional Language</span>
            <span class="detail-value">Fear: ${el.fear_words} | Anger: ${el.anger_words} | Urgency: ${el.urgency_words}</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(el.score, 100)}%"></div></div>
        </div>`;
    }

    // Loaded Language
    if (breakdown.loaded_language && (breakdown.loaded_language.negative_terms > 0 || breakdown.loaded_language.positive_terms > 0)) {
        const ll = breakdown.loaded_language;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Loaded Language</span>
            <span class="detail-value">${ll.one_sided ? 'One-sided bias detected' : `Neg: ${ll.negative_terms} | Pos: ${ll.positive_terms}`}</span>
            ${ll.examples.length > 0 ? `<div class="detail-examples">${ll.examples.map(e => `<span class="example-chip">${e}</span>`).join('')}</div>` : ''}
        </div>`;
    }

    // Sentiment (VADER)
    if (breakdown.sentiment) {
        const st = breakdown.sentiment;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Sentiment (VADER)</span>
            <span class="detail-value">Compound: ${st.compound} ${st.extreme ? '⚠️ Extreme' : ''}</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(st.score, 100)}%"></div></div>
        </div>`;
    }

    // Emotion Profile
    if (breakdown.emotion_profile) {
        const ep = breakdown.emotion_profile;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Emotion Profile</span>
            <span class="detail-value">Fear: ${(ep.fear * 100).toFixed(0)}% | Anger: ${(ep.anger * 100).toFixed(0)}% | Joy: ${(ep.joy * 100).toFixed(0)}%</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(ep.score, 100)}%"></div></div>
        </div>`;
    }

    // Missing Sources
    if (breakdown.missing_sources) {
        const ms = breakdown.missing_sources;
        detailsHtml += `<div class="analysis-detail-item">
            <span class="detail-label">Source Verification</span>
            <span class="detail-value">${ms.unattributed_quotes} unattributed / ${ms.total_quotes} total quotes</span>
            <div class="detail-bar"><div class="detail-bar-fill" style="width: ${Math.min(ms.score, 100)}%"></div></div>
        </div>`;
    }

    detailsHtml += '</div>';

    // Build warnings list
    let warningsHtml = '';
    if (warnings.length > 0) {
        warningsHtml = '<div class="analysis-warnings"><strong>Specific Warnings:</strong><ul>' +
            warnings.map(w => `<li>${w}</li>`).join('') +
            '</ul></div>';
    }

    // Create the banner
    const banner = document.createElement("div");
    banner.id = "analysis-banner";
    banner.className = `analysis-banner ${bannerClass}`;
    banner.innerHTML = `
        <div class="analysis-header" onclick="toggleAnalysisDetails()">
            <div class="analysis-summary">
                <span class="analysis-icon">${icon}</span>
                <span class="analysis-label">${label}</span>
                <span class="analysis-score">Score: ${score}/100</span>
            </div>
            <span class="analysis-toggle" id="analysis-toggle-icon">▼ Why this rating?</span>
        </div>
        <div class="analysis-body" id="analysis-body" style="display: none;">
            ${warningsHtml}
            ${detailsHtml}
            <div class="analysis-recommendation">
                <strong>Recommendation:</strong> ${recommendation}
            </div>
        </div>
    `;

    // Insert banner before the summary output
    const outputSection = document.getElementById("output-section");
    if (outputSection) {
        // For the results-area layout (first output-section)
        const summaryPanel = outputSection.querySelector('.result-panel, .output-box, .result-content');
        if (summaryPanel) {
            summaryPanel.parentNode.insertBefore(banner, summaryPanel);
        } else {
            outputSection.insertBefore(banner, outputSection.firstChild);
        }
    }
}

function toggleAnalysisDetails() {
    const body = document.getElementById("analysis-body");
    const toggleIcon = document.getElementById("analysis-toggle-icon");
    if (body.style.display === "none") {
        body.style.display = "block";
        toggleIcon.textContent = "▲ Hide details";
    } else {
        body.style.display = "none";
        toggleIcon.textContent = "▼ Why this rating?";
    }
}

function truncateText(text, maxLen) {
    if (text.length <= maxLen) return text;
    return text.substring(0, maxLen) + "...";
}

// ============================================================================
// QUIZ FUNCTIONALITY
// ============================================================================

function openQuiz() {
    cancelSpeech(); // Stop speech when opening quiz
    if (!currentQuizId) {
        showToast("No quiz available for this article", "error");
        return;
    }
    
    showLoading("Loading quiz...");
    
    fetch(`/quiz/${currentQuizId}`)
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            const quiz = data.quiz;
            displayQuiz(quiz.mcqs);
        } else {
            showToast("Failed to load quiz", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function displayQuiz(questions) {
    quizAnswers = new Array(questions.length).fill(null);
    
    const modal = document.getElementById("quiz-modal");
    const content = document.getElementById("quiz-content");
    const results = document.getElementById("quiz-results");
    
    results.style.display = "none";
    content.style.display = "block";
    content.innerHTML = "";
    
    document.getElementById("total-q").textContent = questions.length;
    
    questions.forEach((q, idx) => {
        const qDiv = document.createElement("div");
        qDiv.className = "quiz-question";
        
        qDiv.innerHTML = `
            <h3>Q${idx + 1}: ${q.question}</h3>
            ${q.options.map((opt, optIdx) => `
                <label class="quiz-option">
                    <input type="radio" name="q${idx}" value="${String.fromCharCode(65 + optIdx)}" 
                        onchange="quizAnswers[${idx}] = this.value; updateProgress()">
                    ${opt}
                </label>
            `).join("")}
        `;
        
        content.appendChild(qDiv);
    });
    
    const submitBtn = document.createElement("button");
    submitBtn.className = "submit-quiz-btn";
    submitBtn.textContent = "Submit Quiz";
    submitBtn.onclick = () => submitQuiz(questions);
    content.appendChild(submitBtn);
    
    modal.classList.add("active");
    updateProgress();
}

function updateProgress() {
    const answered = quizAnswers.filter(a => a !== null).length;
    const total = quizAnswers.length;
    const percentage = (answered / total) * 100;
    
    document.getElementById("progress-fill").style.width = percentage + "%";
    document.getElementById("current-q").textContent = answered + 1;
}

function submitQuiz(questions) {
    if (quizAnswers.some(a => a === null)) {
        showToast("Please answer all questions", "error");
        return;
    }
    
    showLoading("Calculating results...");
    
    fetch(`/quiz/${currentQuizId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers: quizAnswers })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            displayQuizResults(data);
        } else {
            showToast("Failed to submit quiz", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function displayQuizResults(data) {
    const content = document.getElementById("quiz-content");
    const results = document.getElementById("quiz-results");
    
    content.style.display = "none";
    results.style.display = "block";
    results.innerHTML = "";
    
    const scoreDiv = document.createElement("div");
    scoreDiv.className = "score-display";
    scoreDiv.innerHTML = `
        <div class="score-number">${data.score}/${data.total}</div>
        <div class="score-text">${data.percentage}%</div>
    `;
    results.appendChild(scoreDiv);
    
    data.results.forEach(result => {
        const resultDiv = document.createElement("div");
        resultDiv.className = `result-item ${result.is_correct ? "correct" : "incorrect"}`;
        resultDiv.innerHTML = `
            <strong>Q${result.question_number}</strong>
            <p>Your answer: <strong>${result.user_answer}</strong></p>
            <p>Correct answer: <strong>${result.correct_answer}</strong></p>
            <p><em>${result.explanation}</em></p>
        `;
        results.appendChild(resultDiv);
    });
    
    const closeBtn = document.createElement("button");
    closeBtn.className = "btn btn-primary";
    closeBtn.textContent = "Close Quiz";
    closeBtn.style.width = "100%";
    closeBtn.onclick = closeQuiz;
    results.appendChild(closeBtn);
}

function closeQuiz() {
    document.getElementById("quiz-modal").classList.remove("active");
}

// ============================================================================
// FLASHCARD FUNCTIONALITY
// ============================================================================

function openFlashcards() {
    cancelSpeech(); // Stop speech when opening flashcards
    if (!currentQuizId) {
        showToast("No flashcards available", "error");
        return;
    }
    
    showLoading("Loading flashcards...");
    
    fetch(`/quiz/${currentQuizId}`)
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentFlashcards = data.quiz.flashcards;
            currentCardIndex = 0;
            displayFlashcard();
            document.getElementById("flashcard-modal").classList.add("active");
        } else {
            showToast("Failed to load flashcards", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function displayFlashcard() {
    if (currentFlashcards.length === 0) return;
    
    const card = currentFlashcards[currentCardIndex];
    document.getElementById("card-front").textContent = card.front;
    document.getElementById("card-back").textContent = card.back;
    document.getElementById("current-card").textContent = currentCardIndex + 1;
    document.getElementById("total-cards").textContent = currentFlashcards.length;
    
    const flashcard = document.getElementById("flashcard-inner");
    flashcard.classList.remove("flipped");
    document.getElementById("flashcard").classList.remove("flipped");
    
    updateFlashcardButtons();
}

function flipCard() {
    document.getElementById("flashcard").classList.toggle("flipped");
}

function nextCard() {
    if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        displayFlashcard();
    }
}

function previousCard() {
    if (currentCardIndex > 0) {
        currentCardIndex--;
        displayFlashcard();
    }
}

function shuffleCards() {
    for (let i = currentFlashcards.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentFlashcards[i], currentFlashcards[j]] = [currentFlashcards[j], currentFlashcards[i]];
    }
    currentCardIndex = 0;
    displayFlashcard();
    showToast("Cards shuffled!", "info");
}

function updateFlashcardButtons() {
    document.getElementById("prev-card-btn").disabled = currentCardIndex === 0;
    document.getElementById("next-card-btn").disabled = currentCardIndex === currentFlashcards.length - 1;
}

function closeFlashcards() {
    document.getElementById("flashcard-modal").classList.remove("active");
}

// ============================================================================
// CHAT FUNCTIONALITY
// ============================================================================

function openChat() {
    cancelSpeech(); // Stop speech when opening chat
    if (!currentArticleId) {
        showToast("Please summarize an article first", "error");
        return;
    }
    
    showLoading("Starting chat session...");
    
    fetch("/chat/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ article_id: currentArticleId })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentChatSessionId = data.session_id;
            document.getElementById("chat-article-title").textContent = data.article_title;
            
            const suggestedDiv = document.getElementById("suggested-questions");
            suggestedDiv.innerHTML = "";
            
            data.suggested_questions.forEach(q => {
                const chip = document.createElement("button");
                chip.className = "question-chip";
                chip.textContent = q;
                chip.onclick = () => {
                    document.getElementById("chat-input").value = q;
                    sendChatMessage();
                };
                suggestedDiv.appendChild(chip);
            });
            
            document.getElementById("chat-panel").classList.add("active");
        } else {
            showToast(data.error || "Failed to start chat", "error");
        }
    })
    .catch(error => {
        hideLoading();
        showToast("Error: " + error.message, "error");
    });
}

function sendChatMessage() {
    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    
    if (!message) return;
    
    if (!currentChatSessionId) {
        showToast("Chat session expired", "error");
        return;
    }
    
    addChatMessage("user", message);
    input.value = "";
    
    showLoading("Thinking...");
    
    fetch("/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: currentChatSessionId,
            message: message
        })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            addChatMessage("ai", data.response);
        } else {
            addChatMessage("ai", "Error: " + (data.error || "Failed to get response"));
        }
    })
    .catch(error => {
        hideLoading();
        addChatMessage("ai", "Error: " + error.message);
    });
}

function addChatMessage(role, content) {
    const messagesDiv = document.getElementById("chat-messages");
    const messageDiv = document.createElement("div");
    messageDiv.className = `chat-message ${role}-message`;
    messageDiv.innerHTML = `<div class="message-bubble">${content}</div>`;
    messagesDiv.appendChild(messageDiv);
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function handleChatEnter(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

function clearChatHistory() {
    if (currentChatSessionId) {
        fetch(`/chat/clear/${currentChatSessionId}`, { method: "POST" })
        .then(() => {
            document.getElementById("chat-messages").innerHTML = `
                <div class="chat-welcome">
                    <p>👋 Hi! Ask me anything about this article.</p>
                    <p class="chat-hint">I'll answer based only on the article content.</p>
                </div>
            `;
            showToast("Chat cleared", "info");
        });
    }
}

function closeChat() {
    document.getElementById("chat-panel").classList.remove("active");
    cancelSpeech(); // Stop any ongoing speech when chat opens
}

// ============================================================================
// TEXT-TO-SPEECH (TTS) FUNCTIONALITY
// Uses the browser's built-in Web Speech API (speechSynthesis).
// No external services or libraries required — works offline.
//
// Key APIs:
//   - window.speechSynthesis        : controller for speech playback
//   - SpeechSynthesisUtterance      : represents a speech request
//   - speechSynthesis.getVoices()   : list of available voices
//   - speechSynthesis.speak(utt)    : start speaking
//   - speechSynthesis.pause()       : pause
//   - speechSynthesis.resume()      : resume
//   - speechSynthesis.cancel()      : stop immediately
// ============================================================================

// ---- Global TTS state ----
let currentUtterance = null;   // Active SpeechSynthesisUtterance
let isSpeaking = false;        // True while speech is in progress
let isPaused = false;           // True while speech is paused
let availableVoices = [];       // Populated from speechSynthesis.getVoices()
let selectedVoice = null;       // Currently chosen voice object
let ttsRate = 1;                // Speech speed (0.5 – 2)
let ttsPitch = 1;               // Speech pitch (0.5 – 2)
let ttsChunks = [];             // Chunks for long texts
let ttsChunkIndex = 0;          // Current chunk being spoken
let ttsSupportChecked = false;  // Whether we already checked browser support

// ---- Initialisation ----

/**
 * Initialise TTS on page load.
 * Loads available voices (they may arrive asynchronously via the
 * voiceschanged event) and hides the Listen button if the browser
 * does not support the Web Speech API.
 */
function initTTS() {
    // Feature detection
    if (!('speechSynthesis' in window)) {
        console.warn('TTS: speechSynthesis not supported in this browser.');
        hideAllListenButtons();
        ttsSupportChecked = true;
        return;
    }

    ttsSupportChecked = true;

    // Load voices — they may already be available or may load async
    loadVoices();

    // Chrome (and other Chromium browsers) fire voiceschanged when the
    // voice list becomes available.
    speechSynthesis.onvoiceschanged = loadVoices;

    // Register keyboard shortcuts
    document.addEventListener('keydown', handleTTSKeyboard);
}

/**
 * Populate the availableVoices array and voice-selector dropdowns.
 * Prefers English voices; selects the best default automatically.
 */
function loadVoices() {
    const voices = speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return;

    availableVoices = voices;

    // Try to pick a good default English voice
    const englishVoices = voices.filter(v => v.lang && v.lang.startsWith('en'));

    // Priority list — first match wins
    const preferred = [
        'Google US English',
        'Microsoft David',
        'Microsoft Zira',
        'Google UK English Female',
        'Samantha',          // macOS
        'Alex'               // macOS
    ];

    selectedVoice = null;
    for (const name of preferred) {
        const match = englishVoices.find(v => v.name.includes(name));
        if (match) { selectedVoice = match; break; }
    }
    // Fallback: first English voice, or first voice of any language
    if (!selectedVoice) {
        selectedVoice = englishVoices[0] || voices[0];
    }

    // Populate every voice-select dropdown on the page
    populateVoiceSelectors();
}

/**
 * Fill all <select> elements that act as voice selectors with the
 * available voices, grouped by language.
 */
function populateVoiceSelectors() {
    const selectors = document.querySelectorAll('.tts-select');
    selectors.forEach(sel => {
        const previousValue = sel.value;
        sel.innerHTML = '';

        availableVoices.forEach((voice, idx) => {
            const option = document.createElement('option');
            option.value = idx;
            option.textContent = voice.name + ' (' + voice.lang + ')' + (voice.default ? ' -- DEFAULT' : '');
            if (voice === selectedVoice) option.selected = true;
            sel.appendChild(option);
        });

        // Restore previous selection if still valid
        if (previousValue && sel.querySelector('option[value="' + previousValue + '"]')) {
            sel.value = previousValue;
        }
    });
}

// ---- Text pre-processing ----

/**
 * Clean summary text so that it sounds natural when spoken aloud.
 * Replaces abbreviations, strips markdown, and normalises whitespace.
 */
function preprocessTextForSpeech(text) {
    if (!text) return '';

    let processed = text;

    // Replace common abbreviations with spoken equivalents
    processed = processed.replace(/\be\.g\./gi, 'for example');
    processed = processed.replace(/\bi\.e\./gi, 'that is');
    processed = processed.replace(/\betc\./gi, 'et cetera');
    processed = processed.replace(/\bDr\./g, 'Doctor');
    processed = processed.replace(/\bMr\./g, 'Mister');
    processed = processed.replace(/\bMrs\./g, 'Misses');
    processed = processed.replace(/\bMs\./g, 'Miss');
    processed = processed.replace(/\bProf\./g, 'Professor');
    processed = processed.replace(/\bvs\./gi, 'versus');

    // Remove markdown symbols
    processed = processed.replace(/#{1,6}\s*/g, '');      // headings
    processed = processed.replace(/\*{1,3}(.*?)\*{1,3}/g, '$1'); // bold/italic
    processed = processed.replace(/_{1,3}(.*?)_{1,3}/g, '$1');
    processed = processed.replace(/^[-*+]\s/gm, '');       // list bullets
    processed = processed.replace(/^>\s/gm, '');            // blockquote
    processed = processed.replace(/`{1,3}[^`]*`{1,3}/g, ''); // code

    // Replace URLs with the word "link"
    processed = processed.replace(/https?:\/\/[^\s)]+/g, 'link');

    // Replace HTML tags (in case summary contains <br> etc.)
    processed = processed.replace(/<br\s*\/?>/gi, '. ');
    processed = processed.replace(/<[^>]+>/g, '');

    // Normalise whitespace
    processed = processed.replace(/\s+/g, ' ').trim();

    return processed;
}

/**
 * Split long text into chunks of roughly maxLen characters, breaking
 * at sentence boundaries so speech sounds natural.
 */
function splitTextIntoChunks(text, maxLen) {
    maxLen = maxLen || 4000;
    if (text.length <= maxLen) return [text];

    const chunks = [];
    // Split on sentence-ending punctuation followed by space
    const sentences = text.match(/[^.!?]*[.!?]+[\s]*/g) || [text];
    let current = '';

    for (const sentence of sentences) {
        if ((current + sentence).length > maxLen && current.length > 0) {
            chunks.push(current.trim());
            current = '';
        }
        current += sentence;
    }
    if (current.trim().length > 0) {
        chunks.push(current.trim());
    }

    return chunks.length > 0 ? chunks : [text];
}

// ---- Core speech functions ----

/**
 * Speak the given text using the Web Speech API.
 *
 * @param {string} text    - The raw summary text to speak.
 * @param {object} options - Optional overrides: { voice, rate, pitch, volume }
 */
function speakSummary(text, options) {
    if (!('speechSynthesis' in window)) {
        showToast('Browser does not support audio playback.', 'error');
        return;
    }

    // Cancel any current speech first
    speechSynthesis.cancel();

    const processed = preprocessTextForSpeech(text);
    if (!processed) {
        showToast('No text to read.', 'error');
        return;
    }

    const opts = options || {};
    const voice = opts.voice || selectedVoice;
    const rate  = opts.rate  || ttsRate;
    const pitch = opts.pitch || ttsPitch;

    // Split into chunks for long texts
    ttsChunks = splitTextIntoChunks(processed, 4000);
    ttsChunkIndex = 0;

    speakChunk(voice, rate, pitch);
}

/**
 * Speak a single chunk from the ttsChunks array and queue the next
 * one via the onend callback.
 */
function speakChunk(voice, rate, pitch) {
    if (ttsChunkIndex >= ttsChunks.length) {
        onSpeechFinished();
        return;
    }

    const utterance = new SpeechSynthesisUtterance(ttsChunks[ttsChunkIndex]);

    if (voice)  utterance.voice  = voice;
    utterance.rate   = rate;
    utterance.pitch  = pitch;
    utterance.volume = 1;

    // ---- Event handlers ----

    utterance.onstart = function () {
        isSpeaking = true;
        isPaused = false;
        updateAllListenButtons('playing');
        updateTTSStatus('Reading' +
            (ttsChunks.length > 1
                ? ' (part ' + (ttsChunkIndex + 1) + ' of ' + ttsChunks.length + ')'
                : '') +
            '...');
    };

    utterance.onpause = function () {
        isPaused = true;
        updateAllListenButtons('paused');
        updateTTSStatus('Paused');
    };

    utterance.onresume = function () {
        isPaused = false;
        updateAllListenButtons('playing');
        updateTTSStatus('Reading...');
    };

    utterance.onend = function () {
        ttsChunkIndex++;
        if (ttsChunkIndex < ttsChunks.length) {
            // Speak next chunk
            speakChunk(voice, rate, pitch);
        } else {
            onSpeechFinished();
        }
    };

    utterance.onerror = function (event) {
        // 'interrupted' is normal when the user cancels
        if (event.error !== 'interrupted') {
            console.error('TTS error:', event.error);
            showToast('Speech error: ' + event.error, 'error');
        }
        onSpeechFinished();
    };

    currentUtterance = utterance;
    speechSynthesis.speak(utterance);
}

/** Reset all TTS state after speech ends (naturally or by cancellation). */
function onSpeechFinished() {
    isSpeaking = false;
    isPaused = false;
    currentUtterance = null;
    ttsChunks = [];
    ttsChunkIndex = 0;
    updateAllListenButtons('idle');
    updateTTSStatus('');
}

/** Pause the current speech. */
function pauseSpeech() {
    if ('speechSynthesis' in window && isSpeaking && !isPaused) {
        speechSynthesis.pause();
        isPaused = true;
        updateAllListenButtons('paused');
        updateTTSStatus('Paused');
    }
}

/** Resume paused speech. */
function resumeSpeech() {
    if ('speechSynthesis' in window && isPaused) {
        speechSynthesis.resume();
        isPaused = false;
        updateAllListenButtons('playing');
        updateTTSStatus('Reading...');
    }
}

/** Cancel / stop speech immediately. */
function cancelSpeech() {
    if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
    }
    onSpeechFinished();
}

// ---- Toggle (main entry-point from the Listen button) ----

/**
 * Toggle speech: start -> pause -> resume cycle.
 * Called by the Listen button's onclick handler.
 */
function toggleSpeech() {
    if (!('speechSynthesis' in window)) {
        showToast('Browser does not support audio playback.', 'error');
        return;
    }

    if (isSpeaking && !isPaused) {
        // Currently playing -> pause
        pauseSpeech();
        return;
    }

    if (isPaused) {
        // Currently paused -> resume
        resumeSpeech();
        return;
    }

    // Not speaking -> start fresh
    const summaryText = getSummaryText();
    if (!summaryText) {
        showToast('No summary to read.', 'error');
        return;
    }

    // Show TTS controls panel
    showTTSControls();

    speakSummary(summaryText);
}

/**
 * Extract the plain-text content of the current summary from the DOM.
 */
function getSummaryText() {
    // Try the main output div used in the results-area panel
    const outputEl = document.getElementById('output');
    if (outputEl && outputEl.textContent.trim()) {
        return outputEl.textContent.trim();
    }
    return '';
}

// ---- UI helpers ----

/** Hide all Listen buttons (when browser lacks support). */
function hideAllListenButtons() {
    document.querySelectorAll('.listen-btn').forEach(btn => {
        btn.style.display = 'none';
    });
}

/**
 * Update every Listen button on the page to reflect the given state.
 * @param {'idle'|'playing'|'paused'} state
 */
function updateAllListenButtons(state) {
    const buttons = document.querySelectorAll('.listen-btn');
    buttons.forEach(btn => {
        const icon  = btn.querySelector('.listen-icon');
        const label = btn.querySelector('.listen-label');

        btn.classList.remove('playing', 'paused');

        switch (state) {
            case 'playing':
                btn.classList.add('playing');
                if (icon)  icon.textContent = '\u23F8';   // pause symbol
                if (label) label.textContent = 'Pause';
                btn.setAttribute('aria-label', 'Pause speech');
                break;
            case 'paused':
                btn.classList.add('paused');
                if (icon)  icon.textContent = '\u25B6';   // play symbol
                if (label) label.textContent = 'Resume';
                btn.setAttribute('aria-label', 'Resume speech');
                break;
            default: // idle
                if (icon)  icon.textContent = '\uD83D\uDD0A'; // speaker icon
                if (label) label.textContent = 'Listen';
                btn.setAttribute('aria-label', 'Listen to summary');
                break;
        }
    });
}

/** Show the expandable TTS controls panel(s). */
function showTTSControls() {
    document.querySelectorAll('.tts-controls').forEach(panel => {
        panel.style.display = 'block';
    });
}

/** Hide TTS controls panels. */
function hideTTSControls() {
    document.querySelectorAll('.tts-controls').forEach(panel => {
        panel.style.display = 'none';
    });
}

/** Update all TTS status elements with a message. */
function updateTTSStatus(message) {
    document.querySelectorAll('.tts-status').forEach(el => {
        el.textContent = message;
    });
}

// ---- Settings callbacks ----

/** Called when the user picks a different voice from the dropdown. */
function onVoiceChange() {
    const selectors = document.querySelectorAll('.tts-select');
    let idx = null;
    selectors.forEach(sel => {
        if (sel.value !== '') idx = parseInt(sel.value, 10);
    });

    if (idx !== null && availableVoices[idx]) {
        selectedVoice = availableVoices[idx];

        // Sync all selectors
        selectors.forEach(sel => { sel.value = idx; });

        // If currently speaking, restart with new voice
        if (isSpeaking) {
            const text = getSummaryText();
            cancelSpeech();
            if (text) speakSummary(text);
        }
    }
}

/** Called when the speed slider changes. */
function onSpeedChange(value) {
    ttsRate = parseFloat(value);
    document.querySelectorAll('[id^="speed-value"]').forEach(el => {
        el.textContent = ttsRate.toFixed(1) + 'x';
    });
    // Sync all speed sliders
    document.querySelectorAll('[id^="speed-slider"]').forEach(sl => {
        sl.value = ttsRate;
    });
}

/** Called when the pitch slider changes. */
function onPitchChange(value) {
    ttsPitch = parseFloat(value);
    document.querySelectorAll('[id^="pitch-value"]').forEach(el => {
        el.textContent = ttsPitch.toFixed(1);
    });
    // Sync all pitch sliders
    document.querySelectorAll('[id^="pitch-slider"]').forEach(sl => {
        sl.value = ttsPitch;
    });
}

// ---- Keyboard shortcuts ----

/**
 * Handle keyboard shortcuts for TTS.
 *  Alt+L : toggle speech (start / pause / resume)
 *  Alt+P : pause or resume
 *  Escape: stop speech
 */
function handleTTSKeyboard(event) {
    // Don't intercept when user is typing in an input/textarea
    const tag = (event.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

    if (event.altKey && event.key.toLowerCase() === 'l') {
        event.preventDefault();
        toggleSpeech();
    } else if (event.altKey && event.key.toLowerCase() === 'p') {
        event.preventDefault();
        if (isSpeaking && !isPaused) pauseSpeech();
        else if (isPaused) resumeSpeech();
    } else if (event.key === 'Escape' && isSpeaking) {
        cancelSpeech();
    }
}

// ---- Integration: cancel speech when modals open ----

// Patch closeQuiz, closeFlashcards, closeChat to also cancel speech.
// (The actual cancel calls are added inline above for closeChat;
//  openQuiz and openFlashcards are patched here.)

const _originalOpenQuiz = typeof openQuiz === 'function' ? openQuiz : null;
const _originalOpenFlashcards = typeof openFlashcards === 'function' ? openFlashcards : null;
const _originalOpenChat = typeof openChat === 'function' ? openChat : null;

// We re-wrap these if they exist so that opening a modal cancels speech
if (_originalOpenQuiz) {
    // openQuiz is already defined above — we cancel in displaySummary flow instead
}

// ---- Page lifecycle ----

// Cancel speech when user navigates away or closes the tab
window.addEventListener('beforeunload', function () {
    cancelSpeech();
});

// Initialise TTS after the DOM is ready
document.addEventListener('DOMContentLoaded', initTTS);

// ============================================================================
// ARTICLE RELATIONSHIP MAP - RELATED ARTICLES & GRAPH VISUALIZATION
// ============================================================================

/**
 * Display related articles sidebar for the currently viewed article
 * Fetches related articles from /related/<article_id> endpoint
 * Toggles on/off when clicked
 */
function showRelatedArticles(articleId) {
    const relatedPanel = document.getElementById("related-articles-panel");
    if (!relatedPanel) {
        console.warn("Related articles panel not found in HTML");
        return;
    }

    // Toggle functionality
    if (relatedPanel.classList.contains("active")) {
        relatedPanel.classList.remove("active");
        return;
    }
    
    // Close graph panel when opening related articles
    const graphPanel = document.getElementById("graph-panel");
    if (graphPanel && graphPanel.classList.contains("active")) {
        graphPanel.classList.remove("active");
    }

    relatedPanel.classList.add("active");
    const relatedContent = document.getElementById("related-articles-content");
    relatedContent.innerHTML = '<div class="loading-spinner">Loading related articles...</div>';

    fetch(`/related/${articleId}`)
        .then(response => {
            if (!response.ok) throw new Error("Failed to fetch related articles");
            return response.json();
        })
        .then(data => {
            if (!data.success) {
                relatedContent.innerHTML = `<div class="error-message">Error: ${data.error}</div>`;
                return;
            }

            if (!data.related || data.related.length === 0) {
                relatedContent.innerHTML = '<div class="no-results">No related articles found</div>';
                return;
            }

            // Build HTML for related articles list
            let html = `<div class="related-articles-header">
                <h3>Related Articles (${data.related.length})</h3>
                <button class="close-btn" onclick="closeRelatedArticles()">✕</button>
            </div>
            <div class="related-articles-list">`;

            data.related.forEach(article => {
                const score = article.relationship.score.toFixed(0);
                const sources = (article.relationship.shared_entities || []).slice(0, 3).join(", ");
                
                html += `
                <div class="related-article-card" onclick="navigateToArticle(${article.article.id})">
                    <div class="article-match-score">
                        <span class="score-badge" style="background-color: hsl(${Math.max(0, score - 30)}, 70%, 50%)">
                            ${score}% Match
                        </span>
                    </div>
                    <div class="article-title">${sanitizeHTML(article.article.title.substring(0, 80))}</div>
                    <div class="article-source">${sanitizeHTML(article.article.source)}</div>
                    <div class="article-reason"><strong>Why related:</strong> ${sanitizeHTML(article.relationship.reason)}</div>
                    ${sources ? `<div class="shared-entities">Shared: ${sanitizeHTML(sources)}</div>` : ''}
                </div>`;
            });

            html += '</div>';
            relatedContent.innerHTML = html;
        })
        .catch(error => {
            console.error("Error fetching related articles:", error);
            relatedContent.innerHTML = `<div class="error-message">Failed to load related articles: ${error.message}</div>`;
        });
}

/**
 * Close the related articles sidebar
 */
function closeRelatedArticles() {
    const relatedPanel = document.getElementById("related-articles-panel");
    if (relatedPanel) {
        relatedPanel.classList.remove("active");
    }
}

/**
 * Navigate to an article by ID
 */
function navigateToArticle(articleId) {
    // Set the current article ID and trigger display
    currentArticleId = articleId;
    
    // Fetch and display the article details
    fetch(`/article/${articleId}`)
        .then(response => response.json())
        .then(data => {
            if (data && data.article) {
                // Close the related articles panel
                closeRelatedArticles();
                
                // Summarize the article
                const article = data.article;
                const formData = new FormData();
                formData.append("text", article.content);
                formData.append("source", article.source);
                formData.append("title", article.title);
                
                fetch("/summarize", {
                    method: "POST",
                    body: formData
                })
                .then(response => response.json())
                .then(summaryData => {
                    if (summaryData.success) {
                        currentArticleId = summaryData.article_id;
                        currentQuizId = summaryData.quiz.quiz_id;
                        displaySummary(summaryData.summary, summaryData.category);
                        showToast("Article loaded!", "success");
                    }
                })
                .catch(error => console.error("Error summarizing article:", error));
            }
        })
        .catch(error => console.error("Error loading article:", error));
}

/**
 * Render the full relationship graph visualization
 * Fetches graph data from /relationship-graph endpoint and displays using canvas/SVG
 * Toggles on/off when clicked
 */
function renderRelationshipGraph() {
    const graphPanel = document.getElementById("graph-panel");
    if (!graphPanel) {
        console.warn("Graph panel not found in HTML");
        return;
    }

    // Toggle functionality
    if (graphPanel.classList.contains("active")) {
        graphPanel.classList.remove("active");
        return;
    }
    
    // Close related articles panel when opening graph
    const relatedPanel = document.getElementById("related-articles-panel");
    if (relatedPanel && relatedPanel.classList.contains("active")) {
        relatedPanel.classList.remove("active");
    }

    graphPanel.classList.add("active");
    const graphContainer = document.getElementById("graph-visualization");
    graphContainer.innerHTML = '<div class="loading-spinner">Loading relationship graph...</div>';

    fetch('/relationship-graph')
        .then(response => {
            if (!response.ok) throw new Error("Failed to fetch relationship graph");
            return response.json();
        })
        .then(data => {
            if (!data.success) {
                graphContainer.innerHTML = `<div class="error-message">Error: ${data.error}</div>`;
                return;
            }

            // Create canvas-based force-directed graph visualization
            const canvas = document.createElement("canvas");
            canvas.width = graphContainer.clientWidth || 800;
            canvas.height = graphContainer.clientHeight || 600;
            graphContainer.innerHTML = "";
            graphContainer.appendChild(canvas);

            // Initialize graph data structures
            const nodes = data.nodes.map(n => ({
                id: n.id,
                label: n.title.substring(0, 30) + (n.title.length > 30 ? "..." : ""),
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: 0,
                vy: 0,
                source: n.source,
                category: n.category,
                published: n.published_at,
                mass: 5
            }));

            const edges = data.edges.map(e => ({
                source: data.nodes.findIndex(n => n.id === e.source),
                target: data.nodes.findIndex(n => n.id === e.target),
                weight: e.weight,
                reason: e.reason
            }));

            // Simple force-directed layout simulation
            let running = true;
            let iterations = 0;
            const maxIterations = 100;

            function simulate() {
                if (iterations++ >= maxIterations) {
                    running = false;
                }

                // Apply repulsive forces between all nodes
                for (let i = 0; i < nodes.length; i++) {
                    for (let j = i + 1; j < nodes.length; j++) {
                        const dx = nodes[j].x - nodes[i].x;
                        const dy = nodes[j].y - nodes[i].y;
                        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                        const repulsion = 50000 / (dist * dist);

                        nodes[i].vx -= (dx / dist) * repulsion;
                        nodes[i].vy -= (dy / dist) * repulsion;
                        nodes[j].vx += (dx / dist) * repulsion;
                        nodes[j].vy += (dy / dist) * repulsion;
                    }
                }

                // Apply attractive forces along edges
                edges.forEach(edge => {
                    const source = nodes[edge.source];
                    const target = nodes[edge.target];
                    const dx = target.x - source.x;
                    const dy = target.y - source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const attraction = (dist - 100) * 0.1 * edge.weight;

                    source.vx += (dx / dist) * attraction;
                    source.vy += (dy / dist) * attraction;
                    target.vx -= (dx / dist) * attraction;
                    target.vy -= (dy / dist) * attraction;
                });

                // Apply damping and update positions
                nodes.forEach(node => {
                    node.vx *= 0.95;
                    node.vy *= 0.95;
                    node.x += node.vx;
                    node.y += node.vy;

                    // Boundary collision
                    if (node.x < 20) node.x = 20;
                    if (node.x > canvas.width - 20) node.x = canvas.width - 20;
                    if (node.y < 20) node.y = 20;
                    if (node.y > canvas.height - 20) node.y = canvas.height - 20;
                });

                draw();

                if (running || iterations < maxIterations + 50) {
                    requestAnimationFrame(simulate);
                }
            }

            function draw() {
                const ctx = canvas.getContext("2d");
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // Draw edges
                ctx.strokeStyle = "rgba(100, 150, 200, 0.3)";
                edges.forEach(edge => {
                    const source = nodes[edge.source];
                    const target = nodes[edge.target];
                    ctx.lineWidth = 1 + edge.weight * 3;
                    ctx.beginPath();
                    ctx.moveTo(source.x, source.y);
                    ctx.lineTo(target.x, target.y);
                    ctx.stroke();
                });

                // Draw nodes
                nodes.forEach(node => {
                    // Node circle
                    const categoryColors = {
                        "Technology": "#FF6B6B",
                        "Business": "#4ECDC4",
                        "Politics": "#FFE66D",
                        "Science": "#95E1D3",
                        "Entertainment": "#C7B3E5",
                        "Sports": "#F38181",
                        "Health": "#A8D8EA",
                        "default": "#95A5A6"
                    };
                    const color = categoryColors[node.category] || categoryColors.default;

                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 8, 0, Math.PI * 2);
                    ctx.fill();

                    // Node border
                    ctx.strokeStyle = "#333";
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    // Node label
                    ctx.fillStyle = "#000";
                    ctx.font = "11px Arial";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(node.label, node.x, node.y + 18);
                });

                // Draw stats
                ctx.fillStyle = "#333";
                ctx.font = "12px Arial";
                ctx.textAlign = "left";
                ctx.fillText(`Nodes: ${nodes.length} | Edges: ${edges.length}`, 10, 20);
            }

            // Add mouse interaction
            let hoveredNode = null;
            canvas.addEventListener("mousemove", (e) => {
                const rect = canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;

                hoveredNode = null;
                nodes.forEach(node => {
                    const dx = node.x - mouseX;
                    const dy = node.y - mouseY;
                    if (Math.sqrt(dx * dx + dy * dy) < 15) {
                        hoveredNode = node;
                        canvas.style.cursor = "pointer";
                    }
                });

                if (!hoveredNode) {
                    canvas.style.cursor = "default";
                }
            });

            canvas.addEventListener("click", (e) => {
                if (hoveredNode) {
                    navigateToArticle(hoveredNode.id);
                }
            });

            // Start simulation
            simulate();

            // Add info panel below graph
            const infoPanel = document.createElement("div");
            infoPanel.className = "graph-info";
            infoPanel.innerHTML = `
                <div class="graph-stats">
                    <strong>Graph Statistics:</strong>
                    <ul>
                        <li>Articles (Nodes): ${data.node_count}</li>
                        <li>Relationships (Edges): ${data.edge_count}</li>
                        <li>Avg Connections: ${(data.edge_count / Math.max(1, data.node_count)).toFixed(1)}</li>
                    </ul>
                </div>
                <p class="graph-hint">Click on a node to view the article. Hover to see preview.</p>
            `;
            graphContainer.appendChild(infoPanel);
        })
        .catch(error => {
            console.error("Error rendering relationship graph:", error);
            graphContainer.innerHTML = `<div class="error-message">Failed to load graph: ${error.message}</div>`;
        });
}

/**
 * Close the graph visualization panel
 */
function closeGraphPanel() {
    const graphPanel = document.getElementById("graph-panel");
    if (graphPanel) {
        graphPanel.classList.remove("active");
    }
}

/**
 * Utility function to sanitize HTML and prevent XSS
 */
function sanitizeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
