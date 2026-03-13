"""
services/article_classifier.py - Smart Article Classification using POS Tagging & Chunking
============================================================================================
Uses spaCy NLP pipeline to classify news articles into categories by analyzing
grammatical structures (noun phrases, verb patterns, Actor-Action-Object triples)
rather than simple keyword matching.

NLP Concepts Used:
  1. POS Tagging   – Each token is labeled with its Part-of-Speech (NOUN, VERB, ADJ …).
                     We use POS tags to locate main verbs and their arguments.
  2. Noun Chunking – spaCy's noun_chunks yields base noun phrases (NP) such as
                     "the prime minister" or "a new algorithm".  We inspect the
                     head-words of these chunks for domain signals.
  3. Dependency Parsing – We walk the dependency tree to extract Subject-Verb-Object
                     (SVO) triples, producing "Actor-Action-Object" structures that
                     carry richer semantic cues than isolated keywords.
  4. Named-Entity Recognition (NER) – Entity labels (ORG, PERSON, GPE, EVENT …)
                     provide additional evidence for category assignment.
  5. N-gram Context Windows – We scan bigrams and trigrams in the text for
                     multi-word domain phrases ("machine learning", "stock market",
                     "world cup") that single-token matching would miss.
  6. Full-text Lexicon Scan – A large domain-specific vocabulary is matched
                     against every NOUN/PROPN/ADJ token for broad coverage.
"""

import spacy
import re
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter


# ---------------------------------------------------------------------------
# 1.  Load the spaCy model once at module level (fast subsequent calls)
# ---------------------------------------------------------------------------
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError(
        "spaCy model 'en_core_web_sm' not found. "
        "Install it with: python -m spacy download en_core_web_sm"
    )


# ---------------------------------------------------------------------------
# 2.  EXPANDED Category Definitions
#     Each category now has:
#       - subject_indicators : SUBJECT nouns in SVO triples
#       - verb_indicators    : lemmatised verbs for SVO matching
#       - object_indicators  : OBJECT nouns in SVO triples
#       - entity_labels      : spaCy NER labels that boost the category
#       - chunk_head_words   : noun-chunk root lemmas (strong signals)
#       - lexicon            : LARGE set of domain words matched on every token
#       - bigrams            : multi-word phrases matched on text n-grams
# ---------------------------------------------------------------------------

CATEGORY_PATTERNS: Dict[str, dict] = {

    "technology": {
        "subject_indicators": {
            "company", "startup", "firm", "google", "apple", "microsoft", "meta",
            "amazon", "tesla", "nvidia", "samsung", "researcher", "developer",
            "engineer", "scientist", "team", "openai", "ibm", "intel", "qualcomm",
            "oracle", "cisco", "adobe", "spotify", "uber", "airbnb", "bytedance",
            "tiktok", "snapchat", "twitter", "x", "linkedin", "github", "mozilla",
            "yahoo", "baidu", "alibaba", "tencent", "huawei", "xiaomi", "sony",
            "lg", "dell", "hp", "lenovo", "asus", "amd", "arm", "broadcom",
            "anthropic", "deepmind", "cohere", "stability", "midjourney",
            "programmer", "coder", "hacker", "architect", "designer",
        },
        "verb_indicators": {
            "launch", "develop", "release", "announce", "unveil", "build",
            "design", "integrate", "deploy", "patent", "code", "program",
            "hack", "upgrade", "update", "roll", "innovate", "automate",
            "encrypt", "decrypt", "debug", "compile", "install", "download",
            "upload", "stream", "render", "process", "compute", "optimize",
            "virtualize", "containerize", "scale", "refactor", "iterate",
            "prototype", "digitize", "migrate", "sync", "connect",
        },
        "object_indicators": {
            "app", "application", "software", "algorithm", "chip", "device",
            "platform", "robot", "drone", "ai", "model", "processor", "phone",
            "smartphone", "laptop", "gadget", "feature", "system", "network",
            "database", "api", "tool", "framework", "product", "technology",
            "update", "version", "innovation", "satellite", "server", "cloud",
            "browser", "website", "code", "interface", "protocol", "firmware",
            "operating", "pixel", "display", "sensor", "battery", "charger",
            "router", "modem", "antenna", "cable", "port", "widget",
            "plugin", "extension", "module", "library", "sdk", "runtime",
        },
        "entity_labels": {"ORG", "PRODUCT"},
        "chunk_head_words": {
            "technology", "software", "hardware", "algorithm", "ai",
            "machine", "learning", "data", "computing", "cyber", "digital",
            "internet", "app", "startup", "innovation", "robot", "chip",
            "processor", "server", "cloud", "blockchain", "crypto",
            "automation", "neural", "network", "code", "api", "platform",
            "database", "devops", "cybersecurity", "encryption", "firmware",
            "semiconductor", "transistor", "quantum", "metaverse", "vr",
            "ar", "iot", "5g", "6g", "bandwidth", "latency",
        },
        "lexicon": {
            "tech", "technology", "software", "hardware", "computer", "laptop",
            "smartphone", "phone", "tablet", "gadget", "device", "chip", "processor",
            "cpu", "gpu", "ram", "ssd", "motherboard", "semiconductor", "transistor",
            "algorithm", "code", "coding", "programming", "developer", "programmer",
            "api", "sdk", "framework", "library", "runtime", "compiler", "debugger",
            "ai", "artificial", "intelligence", "machinelearning", "deeplearning",
            "neural", "network", "model", "gpt", "llm", "chatbot", "nlp",
            "cloud", "aws", "azure", "gcp", "kubernetes", "docker", "devops",
            "server", "database", "sql", "nosql", "mongodb", "redis", "postgres",
            "blockchain", "crypto", "cryptocurrency", "bitcoin", "ethereum", "nft",
            "web", "website", "browser", "chrome", "firefox", "safari", "edge",
            "app", "application", "ios", "android", "mobile", "desktop", "wearable",
            "robot", "robotics", "drone", "automation", "iot", "sensor",
            "cybersecurity", "encryption", "hacking", "malware", "ransomware",
            "firewall", "vpn", "phishing", "breach", "vulnerability",
            "5g", "6g", "wifi", "bluetooth", "bandwidth", "latency", "fiber",
            "vr", "ar", "xr", "metaverse", "virtual", "augmented", "hologram",
            "startup", "silicon", "valley", "unicorn", "vc",
            "pixel", "display", "oled", "amoled", "retina", "touchscreen",
            "camera", "megapixel", "lidar", "radar",
            "tesla", "spacex", "google", "apple", "microsoft", "meta", "nvidia",
            "samsung", "amazon", "openai", "anthropic", "deepmind",
            "linux", "windows", "macos", "ubuntu", "kernel", "firmware",
            "python", "javascript", "java", "rust", "golang", "typescript",
            "github", "gitlab", "stackoverflow", "opensource",
            "quantum", "qubit", "supercomputer", "exascale",
            "iphone", "macbook", "ipad", "galaxy", "surface",
            "copilot", "gemini", "claude", "chatgpt", "siri", "alexa",
        },
        "bigrams": {
            "artificial intelligence", "machine learning", "deep learning",
            "neural network", "natural language", "computer vision",
            "self driving", "autonomous vehicle", "virtual reality",
            "augmented reality", "mixed reality", "internet of things",
            "cloud computing", "edge computing", "quantum computing",
            "cyber security", "data privacy", "open source", "tech company",
            "silicon valley", "generative ai", "large language",
            "language model", "operating system", "smart home",
            "smart device", "tech industry", "digital transformation",
            "apple intelligence", "google ai", "5g network",
        },
    },

    "sports": {
        "subject_indicators": {
            "team", "player", "athlete", "coach", "club", "squad", "captain",
            "batsman", "bowler", "striker", "goalkeeper", "champion", "side",
            "franchise", "opener", "batter", "fielder", "runner", "pitcher",
            "quarterback", "referee", "umpire", "manager", "skipper",
            "defender", "midfielder", "forward", "winger", "keeper",
            "sprinter", "swimmer", "gymnast", "boxer", "wrestler",
            "seamer", "spinner", "allrounder", "pacer", "wicketkeeper",
        },
        "verb_indicators": {
            "win", "lose", "defeat", "score", "play", "compete", "beat",
            "qualify", "race", "train", "draft", "sign", "trade", "bat",
            "bowl", "chase", "tackle", "kick", "shoot", "sprint", "host",
            "retire", "bench", "transfer", "clinch", "slam", "dunk",
            "volley", "serve", "pitch", "throw", "catch", "hit", "run",
            "swim", "dive", "jump", "lift", "wrestle", "box", "spar",
            "dribble", "pass", "foul", "substitute", "injure", "select",
            "drop", "retain", "auction", "bid", "unsold",
        },
        "object_indicators": {
            "match", "game", "goal", "point", "championship", "tournament",
            "trophy", "medal", "title", "league", "season", "cup", "wicket",
            "run", "inning", "over", "final", "semifinal", "stadium",
            "fixture", "series", "squad", "auction", "century", "fifty",
            "hat-trick", "boundary", "six", "four", "penalty", "corner",
            "freekick", "header", "try", "touchdown", "homerun", "slam",
            "set", "ace", "deuce", "bogey", "birdie", "eagle", "par",
            "podium", "lap", "qualifying", "race", "bout", "round",
        },
        "entity_labels": {"PERSON", "ORG", "EVENT", "CARDINAL"},
        "chunk_head_words": {
            "match", "game", "team", "player", "league", "championship",
            "season", "cricket", "football", "soccer", "tennis", "golf",
            "basketball", "baseball", "hockey", "rugby", "ipl", "fifa",
            "olympic", "tournament", "stadium", "coach", "cup",
            "innings", "wicket", "run", "score", "batting", "bowling",
            "fielding", "selection", "squad", "roster", "draft",
            "transfer", "auction", "playoff", "knockout", "group",
            "standings", "table", "points", "goal", "medal",
        },
        "lexicon": {
            "cricket", "football", "soccer", "tennis", "golf", "basketball",
            "baseball", "hockey", "rugby", "volleyball", "badminton",
            "swimming", "athletics", "boxing", "wrestling", "gymnastics",
            "cycling", "motorsport", "f1", "formula", "nascar", "motogp",
            "ipl", "bcci", "odi", "t20", "test", "ashes",
            "fifa", "uefa", "epl", "laliga", "bundesliga", "seriea",
            "nba", "nfl", "mlb", "nhl", "mls", "pga", "atp", "wta",
            "olympic", "olympics", "paralympic", "commonwealth", "asian",
            "worldcup", "champion", "championship", "trophy", "medal",
            "gold", "silver", "bronze", "podium", "finalist",
            "team", "player", "athlete", "coach", "captain", "squad",
            "batsman", "batter", "bowler", "fielder", "wicketkeeper",
            "striker", "goalkeeper", "defender", "midfielder", "forward",
            "quarterback", "pitcher", "catcher", "referee", "umpire",
            "match", "game", "fixture", "series", "tournament", "league",
            "season", "playoff", "knockout", "semifinal", "quarterfinal",
            "innings", "wicket", "boundary", "six", "four", "century",
            "fifty", "duck", "maiden", "hattrick",
            "goal", "penalty", "corner", "freekick", "offside", "foul",
            "touchdown", "homerun", "slam", "ace", "deuce", "set",
            "stadium", "ground", "pitch", "court", "arena", "track",
            "field", "pool", "ring", "rink", "course", "oval",
            "batting", "bowling", "fielding", "chasing", "defending",
            "scoreboard", "scorecard", "standings", "ranking",
            "auction", "bid", "retention", "purse", "trade", "transfer",
            "csk", "mi", "rcb", "kkr", "srh", "dc", "pbks", "rr", "gt", "lsg",
            "dhoni", "kohli", "rohit", "virat", "sachin", "sourav",
            "messi", "ronaldo", "neymar", "mbappe", "haaland",
            "federer", "nadal", "djokovic", "serena", "williams",
            "tendulkar", "warne", "bradman", "ponting",
            "sprint", "marathon", "relay", "hurdle", "javelin",
            "samson", "jadeja", "bumrah", "pant", "gill",
            "super", "kings", "royals", "indians", "challengers",
            "sunrisers", "capitals", "warriors", "titans", "giants",
            "powerplay", "death", "overs",
            "drs", "lbw", "runout", "stumping", "caught", "bowled",
            "chinnaswamy", "wankhede", "eden", "gardens",
            "gabba", "lords", "mcg", "scg",
            "anchor", "finisher", "opener",
            "selection", "selector", "outfield", "crease", "stump",
            "sport", "sporting", "sportsmanship", "athletic",
        },
        "bigrams": {
            "cricket match", "football match", "tennis match",
            "world cup", "premier league", "champions league",
            "la liga", "serie a", "grand slam", "grand prix",
            "home ground", "away match", "test match", "test series",
            "odi series", "t20 world",
            "ipl auction", "ipl season", "ipl 2026", "ipl 2025",
            "playing xi", "playing eleven", "match prediction",
            "super kings", "chennai super", "mumbai indians",
            "royal challengers", "kolkata knight", "knight riders",
            "rajasthan royals", "sunrisers hyderabad", "delhi capitals",
            "punjab kings", "lucknow super",
            "gujarat titans", "super giants",
            "strike rate", "batting average", "bowling average",
            "run rate", "net run", "points table",
            "penalty kick", "free kick", "corner kick",
            "slam dunk", "three pointer", "field goal",
            "impact player",
            "power play", "death overs", "middle overs",
            "fast bowler", "spin bowler", "pace attack",
            "wicket keeper", "opening batsman", "opening pair",
            "man of the match", "player of the match",
            "chinnaswamy stadium", "wankhede stadium",
            "narendra modi stadium", "eden gardens",
            "home matches", "home games",
        },
    },

    "politics": {
        "subject_indicators": {
            "president", "minister", "senator", "governor", "leader",
            "politician", "chancellor", "prime", "lawmaker", "legislator",
            "party", "government", "administration", "congress", "parliament",
            "opposition", "diplomat", "spokesperson", "chief", "mayor",
            "ambassador", "secretary", "commissioner", "delegate", "envoy",
            "dictator", "monarch", "king", "queen", "emperor", "sultan",
            "mp", "mla", "mep", "councillor", "alderman",
            "democrat", "republican", "conservative", "liberal", "labour",
            "bjp", "aap", "jdu",
        },
        "verb_indicators": {
            "announce", "pass", "veto", "vote", "elect", "campaign",
            "legislate", "sign", "sanction", "negotiate", "debate",
            "resign", "impeach", "govern", "ban", "regulate", "reform",
            "enact", "declare", "condemn", "endorse", "ratify",
            "overthrow", "protest", "rally", "march", "lobby",
            "filibuster", "gerrymander", "redistrict", "recount",
            "inaugurate", "appoint", "nominate", "confirm", "dismiss",
            "pardon", "extradite", "deport", "naturalize",
        },
        "object_indicators": {
            "policy", "bill", "law", "act", "election", "vote", "reform",
            "legislation", "sanction", "treaty", "mandate", "regulation",
            "constitution", "ballot", "campaign", "amendment", "summit",
            "resolution", "coalition", "cabinet", "referendum", "census",
            "budget", "tariff", "subsidy", "welfare", "immigration",
            "asylum", "visa", "citizenship", "sovereignty", "democracy",
            "dictatorship", "monarchy", "republic", "federation",
        },
        "entity_labels": {"GPE", "NORP", "ORG", "PERSON", "LAW"},
        "chunk_head_words": {
            "government", "election", "policy", "minister", "president",
            "party", "parliament", "democracy", "vote", "law", "political",
            "senator", "campaign", "congress", "legislation", "diplomacy",
            "opposition", "coalition", "sanction", "referendum", "summit",
            "geopolitics", "sovereignty", "constitution", "amendment",
            "cabinet", "bureaucracy", "administration", "judiciary",
        },
        "lexicon": {
            "politics", "political", "government", "governance", "election",
            "vote", "voting", "voter", "ballot", "poll", "polling",
            "president", "presidential", "minister", "ministerial", "prime",
            "senator", "senatorial", "governor", "mayor", "congressman",
            "parliament", "parliamentary", "congress", "congressional",
            "legislature", "legislative", "judiciary", "judicial",
            "executive", "cabinet", "bureaucracy", "administration",
            "democrat", "republican", "conservative", "liberal", "labour",
            "progressive", "moderate", "radical", "populist", "nationalist",
            "socialist", "communist", "fascist", "authoritarian",
            "party", "bipartisan", "partisan", "caucus", "faction",
            "campaign", "campaigning", "rally", "protest", "demonstration",
            "diplomacy", "diplomatic", "ambassador", "embassy", "consulate",
            "treaty", "accord", "pact", "agreement", "summit", "negotiation",
            "sanction", "embargo", "tariff",
            "policy", "legislation", "bill", "act", "law", "regulation",
            "reform", "amendment", "constitution", "constitutional",
            "impeach", "impeachment", "resign", "resignation",
            "democracy", "democratic", "republic", "monarchy",
            "sovereignty", "independence", "autonomy", "secession",
            "geopolitics", "geopolitical", "nato", "un", "eu",
            "referendum", "plebiscite", "mandate", "coalition",
            "opposition", "incumbent", "challenger", "frontrunner",
            "constituency", "electorate", "swing", "battleground",
            "bjp", "aap", "modi", "biden", "trump",
            "obama", "putin", "xi", "macron", "sunak", "starmer",
        },
        "bigrams": {
            "prime minister", "chief minister", "foreign minister",
            "home minister", "defense minister", "finance minister",
            "general election", "by election", "midterm election",
            "political party", "ruling party", "opposition party",
            "foreign policy", "domestic policy", "fiscal policy",
            "trade war", "cold war", "arms race", "nuclear deal",
            "peace talks", "ceasefire agreement", "border dispute",
            "human rights", "civil rights", "civil liberties",
            "supreme court", "high court", "district court",
            "executive order", "presidential decree",
            "national security", "homeland security",
            "un general", "security council", "general assembly",
            "state department", "white house", "downing street",
            "lok sabha", "rajya sabha", "legislative assembly",
        },
    },

    "business": {
        "subject_indicators": {
            "ceo", "executive", "company", "corporation", "investor",
            "shareholder", "analyst", "bank", "firm", "startup", "market",
            "trader", "fund", "venture", "entrepreneur", "founder",
            "chairman", "director", "manager", "conglomerate", "subsidiary",
            "broker", "lender", "borrower", "creditor", "debtor",
        },
        "verb_indicators": {
            "acquire", "merge", "invest", "profit", "revenue", "sell",
            "buy", "trade", "earn", "stock", "fund", "grow", "expand",
            "surge", "drop", "decline", "file", "report", "forecast",
            "hire", "lay", "outsource", "export", "import",
            "divest", "restructure", "downgrade", "upgrade",
            "bankrupt", "liquidate", "refinance", "leverage", "capitalize",
            "monetize", "diversify", "franchise", "license", "underwrite",
        },
        "object_indicators": {
            "share", "stock", "market", "revenue", "profit", "quarter",
            "deal", "merger", "acquisition", "investment", "economy",
            "gdp", "inflation", "index", "bond", "ipo", "dividend",
            "valuation", "earnings", "growth", "loss", "startup", "trade",
            "asset", "liability", "equity", "debt", "mortgage", "loan",
            "interest", "yield", "portfolio", "hedge", "commodity",
            "futures", "options", "derivatives", "forex", "currency",
        },
        "entity_labels": {"ORG", "MONEY", "PERCENT", "CARDINAL"},
        "chunk_head_words": {
            "market", "stock", "economy", "business", "revenue", "profit",
            "investment", "company", "trade", "finance", "bank", "industry",
            "gdp", "inflation", "startup", "valuation", "merger", "ipo",
            "shareholder", "billion", "million", "dollar", "growth",
            "recession", "boom", "bust", "bubble", "crash", "rally",
            "commodity", "futures", "portfolio", "hedge", "fund",
        },
        "lexicon": {
            "business", "commerce", "commercial", "corporate", "corporation",
            "company", "enterprise", "firm", "conglomerate", "subsidiary",
            "stock", "share", "equity", "bond", "treasury", "security",
            "market", "marketplace", "exchange", "nasdaq", "nyse", "dow",
            "sensex", "nifty", "ftse", "nikkei", "shanghai", "bse",
            "investor", "investment", "investing", "portfolio", "hedge",
            "revenue", "profit", "loss", "earnings", "income", "expense",
            "gdp", "inflation", "deflation", "recession", "depression",
            "economy", "economic", "economics", "fiscal", "monetary",
            "bank", "banking", "central", "reserve", "fed", "rbi", "ecb",
            "loan", "mortgage", "interest", "yield", "coupon",
            "merger", "acquisition", "takeover", "buyout", "divestiture",
            "ipo", "listing", "delisting", "valuation", "capitalization",
            "ceo", "cfo", "coo", "cto", "executive", "board", "director",
            "entrepreneur", "founder", "venture", "angel", "seed",
            "dividend", "buyback", "split", "dilution", "outstanding",
            "commodity", "futures", "derivatives", "forex",
            "tariff", "duty", "customs", "export",
            "import", "supply", "demand", "surplus", "deficit",
            "quarter", "quarterly", "annual", "financial",
            "unicorn", "decacorn", "bootstrapped",
            "bankruptcy", "insolvency", "liquidation", "restructuring",
            "retail", "wholesale", "ecommerce",
            "billion", "million", "trillion", "crore", "lakh",
        },
        "bigrams": {
            "stock market", "stock exchange", "share price",
            "wall street", "dow jones",
            "bull market", "bear market", "market crash", "market rally",
            "interest rate", "central bank", "federal reserve",
            "fiscal year", "fiscal quarter", "annual report",
            "initial public", "public offering", "venture capital",
            "private equity", "hedge fund", "mutual fund",
            "supply chain", "global trade", "trade deficit",
            "economic growth", "economic crisis", "financial crisis",
            "real estate", "housing market", "property market",
            "mergers and", "and acquisitions", "hostile takeover",
            "profit margin", "revenue growth", "earnings per",
            "per share", "market cap", "market capitalization",
            "balance sheet", "income statement", "cash flow",
            "gdp growth", "inflation rate", "unemployment rate",
        },
    },

    "entertainment": {
        "subject_indicators": {
            "actor", "actress", "singer", "director", "musician", "band",
            "studio", "celebrity", "star", "filmmaker", "artist",
            "comedian", "host", "producer", "rapper", "dj", "composer",
            "choreographer", "screenwriter", "playwright", "novelist",
            "influencer", "youtuber", "streamer", "performer",
        },
        "verb_indicators": {
            "release", "premiere", "stream", "star", "direct", "perform",
            "act", "sing", "film", "shoot", "produce", "cast", "debut",
            "award", "nominate", "feature", "entertain", "tour",
            "record", "compose", "choreograph", "write", "publish",
            "binge", "watch", "download", "trend", "viral",
        },
        "object_indicators": {
            "movie", "film", "song", "album", "show", "series", "concert",
            "award", "oscar", "grammy", "emmy", "festival", "trailer",
            "episode", "season", "role", "soundtrack",
            "celebrity", "performance", "ticket", "premiere", "screening",
            "blockbuster", "flop", "hit", "single", "ep", "lp",
            "playlist", "podcast", "stream", "download", "view",
            "script", "screenplay", "novel", "book", "comic",
        },
        "entity_labels": {"PERSON", "WORK_OF_ART", "ORG", "EVENT"},
        "chunk_head_words": {
            "movie", "film", "music", "song", "album", "show", "series",
            "actor", "actress", "celebrity", "entertainment", "hollywood",
            "bollywood", "netflix", "concert", "festival", "award",
            "oscar", "grammy", "emmy", "streaming",
            "premiere", "trailer", "blockbuster", "soundtrack",
            "comedy", "drama", "thriller", "horror", "romance", "action",
        },
        "lexicon": {
            "movie", "film", "cinema", "theater", "theatre", "screening",
            "bollywood", "hollywood", "tollywood", "kollywood", "nollywood",
            "actor", "actress", "star", "celebrity", "celeb", "fame",
            "director", "producer", "screenwriter", "cinematographer",
            "music", "musician", "singer", "songwriter", "composer",
            "rapper", "hiphop", "pop", "rock", "jazz", "blues", "country",
            "classical", "electronic", "edm", "reggae", "metal",
            "album", "single", "ep", "lp", "track", "song", "tune",
            "concert", "tour", "festival", "gig", "show", "performance",
            "netflix", "hulu", "disney", "hbo", "prime", "peacock",
            "paramount", "universal", "warner", "fox", "lionsgate",
            "oscar", "grammy", "emmy", "tony", "bafta", "golden",
            "cannes", "venice", "berlin", "sundance", "toronto",
            "animation", "anime", "cartoon", "manga", "comic",
            "comedy", "drama", "thriller", "horror", "romance", "action",
            "documentary", "biopic", "sequel", "prequel", "reboot",
            "franchise", "cinematic", "universe", "trilogy",
            "streaming", "binge", "bingewatch", "premiere", "debut",
            "blockbuster", "flop", "hit", "box", "office", "gross",
            "ticket", "trailer", "teaser", "poster", "casting", "audition",
            "podcast", "youtuber", "influencer", "viral", "trending",
            "entertainment", "showbiz", "gossip", "tabloid",
            "reality", "talent", "idol", "voice", "dance", "choreography",
            "standup", "improv", "sketch", "satire", "parody",
        },
        "bigrams": {
            "box office", "opening weekend", "release date",
            "movie trailer", "film festival", "award ceremony",
            "red carpet", "golden globe", "academy award",
            "best picture", "best director", "best actor", "best actress",
            "tv show", "tv series", "web series", "reality show",
            "music video", "album release", "world tour", "concert tour",
            "streaming service", "streaming platform",
            "netflix series", "disney plus", "amazon prime",
            "stand up", "standup comedy", "comedy special",
            "celebrity news", "entertainment news", "showbiz news",
        },
    },

    "science": {
        "subject_indicators": {
            "scientist", "researcher", "professor", "team", "study",
            "experiment", "lab", "laboratory", "institution", "university",
            "nasa", "esa", "isro", "jaxa", "agency", "observatory",
            "astronomer", "biologist", "physicist", "chemist", "geologist",
            "ecologist", "botanist", "zoologist", "neuroscientist",
            "astrophysicist", "cosmologist", "archaeologist", "paleontologist",
        },
        "verb_indicators": {
            "discover", "study", "research", "observe", "experiment",
            "prove", "hypothesize", "analyze", "detect", "measure",
            "simulate", "publish", "map", "explore", "classify", "sequence",
            "synthesize", "isolate", "extract", "culture", "incubate",
            "theorize", "model", "predict", "validate", "replicate",
            "catalogue", "excavate", "unearth",
        },
        "object_indicators": {
            "species", "cell", "gene", "molecule", "planet", "star",
            "galaxy", "particle", "fossil", "climate", "genome", "dna",
            "atom", "element", "orbit", "theory", "equation", "evidence",
            "phenomenon", "organism", "ecosystem", "comet", "asteroid",
            "nebula", "supernova", "exoplanet", "microbe", "bacteria",
            "virus", "protein", "enzyme", "catalyst", "isotope",
            "specimen", "crystal", "mineral", "compound", "alloy",
        },
        "entity_labels": {"ORG", "QUANTITY", "DATE"},
        "chunk_head_words": {
            "research", "science", "study", "experiment", "discovery",
            "species", "climate", "space", "planet", "nasa", "physics",
            "chemistry", "biology", "gene", "dna", "fossil", "universe",
            "quantum", "evolution", "cell", "molecule", "ecology",
            "astronomy", "geology", "paleontology", "neuroscience",
            "hypothesis", "theory", "theorem", "equation", "formula",
        },
        "lexicon": {
            "science", "scientific", "scientist", "research", "researcher",
            "study", "experiment", "experimental", "laboratory", "lab",
            "discovery", "discover", "breakthrough", "finding", "evidence",
            "hypothesis", "theory", "theorem", "proof", "equation",
            "physics", "physicist", "quantum", "relativity", "mechanics",
            "thermodynamics", "electromagnetism", "optics", "acoustics",
            "chemistry", "chemical", "chemist", "molecule", "molecular",
            "atom", "atomic", "element", "compound", "reaction", "catalyst",
            "biology", "biological", "biologist", "organism", "species",
            "cell", "cellular", "gene", "genetic", "genome", "genomic",
            "dna", "rna", "protein", "enzyme", "amino", "chromosome",
            "evolution", "evolutionary", "mutation", "adaptation", "selection",
            "ecology", "ecological", "ecosystem", "biodiversity", "habitat",
            "astronomy", "astronomer", "astrophysics", "cosmology",
            "planet", "planetary", "star", "stellar", "galaxy", "galactic",
            "universe", "cosmic", "nebula", "supernova", "quasar", "pulsar",
            "comet", "asteroid", "meteor", "meteorite", "exoplanet",
            "nasa", "esa", "isro", "jaxa", "spacex", "telescope", "hubble",
            "james", "webb", "rover", "probe", "satellite", "orbit",
            "geology", "geological", "geologist", "mineral", "rock", "fossil",
            "paleontology", "paleontologist", "dinosaur", "excavation",
            "neuroscience", "neuron", "brain", "cognitive", "consciousness",
            "climate", "atmosphere", "greenhouse", "carbon", "emission",
            "ozone", "renewable", "solar", "wind", "geothermal",
            "microscope", "spectroscopy", "chromatography", "centrifuge",
            "peer", "journal", "publication", "citation",
        },
        "bigrams": {
            "scientific study", "research paper", "peer review",
            "peer reviewed", "climate change", "global warming",
            "greenhouse gas", "carbon dioxide", "carbon emission",
            "space exploration", "space station", "international space",
            "solar system", "milky way", "black hole", "dark matter",
            "dark energy", "big bang", "string theory", "quantum mechanics",
            "genetic engineering", "gene editing", "crispr cas",
            "stem cell", "clinical trial", "double blind",
            "particle accelerator", "large hadron", "hadron collider",
            "periodic table", "chemical reaction", "chemical bond",
            "natural selection", "theory of", "of evolution",
            "james webb", "hubble telescope", "mars rover",
            "fossil fuel", "renewable energy", "nuclear fusion",
        },
    },

    "health": {
        "subject_indicators": {
            "doctor", "nurse", "surgeon", "patient", "hospital", "who",
            "cdc", "fda", "physician", "therapist", "health",
            "organization", "ministry", "specialist", "pharmacist",
            "dentist", "psychiatrist", "psychologist", "nutritionist",
            "dietitian", "paramedic", "midwife", "oncologist",
            "cardiologist", "neurologist", "pediatrician", "dermatologist",
        },
        "verb_indicators": {
            "treat", "diagnose", "prescribe", "cure", "vaccinate",
            "infect", "spread", "approve", "recommend", "prevent",
            "recover", "hospitalize", "test", "screen", "immunize",
            "operate", "transplant", "rehabilitate", "counsel",
            "medicate", "administer", "inject", "inoculate",
            "contaminate", "quarantine", "isolate", "intubate",
        },
        "object_indicators": {
            "vaccine", "drug", "treatment", "disease", "virus", "patient",
            "symptom", "therapy", "diagnosis", "outbreak", "pandemic",
            "health", "medicine", "hospital", "infection", "cancer",
            "pill", "dose", "surgery", "condition", "disorder",
            "antibody", "antigen", "immunity", "booster", "variant",
            "prescription", "supplement", "vitamin", "mineral",
            "organ", "tissue", "transplant", "prosthetic", "implant",
        },
        "entity_labels": {"ORG", "PERSON", "QUANTITY"},
        "chunk_head_words": {
            "health", "medicine", "vaccine", "disease", "virus", "patient",
            "hospital", "treatment", "doctor", "surgery", "drug", "therapy",
            "pandemic", "outbreak", "cancer", "mental", "wellness",
            "nutrition", "diet", "fitness", "symptom", "diagnosis",
            "clinical", "trial", "pharmaceutical", "prescription",
            "immunity", "antibody", "booster", "variant",
        },
        "lexicon": {
            "health", "healthy", "healthcare", "medical", "medicine",
            "doctor", "physician", "surgeon", "nurse", "nursing",
            "hospital", "clinic", "pharmacy", "pharmaceutical",
            "patient", "treatment", "therapy", "therapeutic",
            "disease", "illness", "sickness", "ailment", "condition",
            "symptom", "diagnosis", "prognosis", "pathology",
            "virus", "viral", "bacteria", "bacterial", "fungal", "parasite",
            "infection", "infectious", "contagious", "epidemic", "pandemic",
            "endemic", "outbreak", "surge", "wave", "strain", "variant",
            "vaccine", "vaccination", "immunization", "booster", "dose",
            "antibody", "antigen", "immunity", "immune", "autoimmune",
            "drug", "medication", "prescription", "otc", "generic",
            "surgery", "surgical", "operation", "procedure", "biopsy",
            "transplant", "prosthetic", "implant", "stent",
            "cancer", "tumor", "tumour", "oncology", "chemotherapy",
            "radiation", "malignant", "benign", "metastasis",
            "diabetes", "hypertension", "cholesterol", "obesity",
            "heart", "cardiac", "cardiovascular", "stroke", "infarction",
            "mental", "depression", "anxiety", "ptsd", "bipolar",
            "schizophrenia", "dementia", "alzheimer", "parkinson",
            "nutrition", "diet", "dietary", "calorie",
            "vitamin", "supplement", "probiotic",
            "fitness", "exercise", "workout", "yoga", "meditation",
            "wellness", "preventive", "preventative", "screening",
            "who", "cdc", "fda", "nih", "nhs", "icmr", "aiims",
            "clinical", "trial", "placebo", "efficacy", "dosage",
            "covid", "coronavirus", "sars", "mers", "influenza", "flu",
            "monkeypox", "ebola", "malaria", "tuberculosis", "hiv", "aids",
            "antibiotic", "antiviral", "antifungal", "antimicrobial",
        },
        "bigrams": {
            "public health", "mental health", "world health",
            "health organization", "health care", "healthcare system",
            "clinical trial", "drug trial", "vaccine trial",
            "side effect", "adverse reaction", "allergic reaction",
            "immune system", "immune response", "herd immunity",
            "medical research", "medical science", "medical device",
            "heart disease", "heart attack", "blood pressure",
            "blood sugar", "diabetes type",
            "cancer treatment", "cancer research", "breast cancer",
            "lung cancer", "skin cancer", "prostate cancer",
            "mental illness", "mental disorder", "eating disorder",
            "substance abuse", "drug abuse", "opioid crisis",
            "emergency room", "intensive care",
            "health insurance", "universal healthcare",
            "organ transplant", "organ donor", "bone marrow",
            "first aid", "life expectancy",
        },
    },
}

# All valid categories
VALID_CATEGORIES = list(CATEGORY_PATTERNS.keys())


# ---------------------------------------------------------------------------
# 3.  POS-Tag & Dependency Helpers
# ---------------------------------------------------------------------------

def extract_noun_chunks(doc) -> List[Dict]:
    """
    POS Tagging + Chunking:  spaCy's noun_chunks are base noun phrases derived
    from the POS tags and dependency parse.  Each chunk has a *root* (head) token
    whose POS is typically NOUN or PROPN.
    """
    chunks = []
    for chunk in doc.noun_chunks:
        all_lemmas = [t.lemma_.lower() for t in chunk if not t.is_stop and not t.is_punct]
        chunks.append({
            "text": chunk.text.lower(),
            "root_lemma": chunk.root.lemma_.lower(),
            "root_pos": chunk.root.pos_,
            "root_dep": chunk.root.dep_,
            "all_lemmas": all_lemmas,
        })
    return chunks


def extract_main_verbs(doc) -> List[Dict]:
    """
    POS Tagging: Iterate over tokens whose POS tag is VERB.  For each verb we
    also record its subject (child with dep in {nsubj, nsubjpass}).
    """
    verbs = []
    for token in doc:
        if token.pos_ == "VERB":
            subject = None
            subject_lemma = None
            for child in token.children:
                if child.dep_ in ("nsubj", "nsubjpass"):
                    subject = child.text.lower()
                    subject_lemma = child.lemma_.lower()
                    break
            verbs.append({
                "lemma": token.lemma_.lower(),
                "text": token.text.lower(),
                "subject": subject,
                "subject_lemma": subject_lemma,
            })
    return verbs


def extract_svo_triples(doc) -> List[Dict]:
    """
    Dependency Parsing – Walk the dependency tree to extract Subject-Verb-Object
    (SVO) triples.  Also walk conjuncts and compound children.
    """
    triples = []
    for token in doc:
        if token.pos_ != "VERB":
            continue

        subjects = []
        objects = []

        for child in token.children:
            if child.dep_ in ("nsubj", "nsubjpass"):
                subjects.append(child.lemma_.lower())
                for subchild in child.children:
                    if subchild.dep_ == "compound":
                        subjects.append(subchild.lemma_.lower())
                for subchild in child.children:
                    if subchild.dep_ == "conj":
                        subjects.append(subchild.lemma_.lower())

            elif child.dep_ in ("dobj", "attr"):
                objects.append(child.lemma_.lower())
                for subchild in child.children:
                    if subchild.dep_ == "compound":
                        objects.append(subchild.lemma_.lower())
                for subchild in child.children:
                    if subchild.dep_ == "conj":
                        objects.append(subchild.lemma_.lower())

            elif child.dep_ == "prep":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        objects.append(grandchild.lemma_.lower())

        for subj in subjects:
            for obj in objects:
                triples.append({
                    "subject": subj,
                    "verb": token.lemma_.lower(),
                    "object": obj,
                    "raw": f"{subj} {token.lemma_.lower()} {obj}",
                })

        if not objects:
            for subj in subjects:
                triples.append({
                    "subject": subj,
                    "verb": token.lemma_.lower(),
                    "object": None,
                    "raw": f"{subj} {token.lemma_.lower()}",
                })

    return triples


def extract_entities(doc) -> List[Dict]:
    """Named-Entity Recognition (NER): Extract named entities and their labels."""
    return [
        {"text": ent.text.lower(), "label": ent.label_}
        for ent in doc.ents
    ]


def extract_content_tokens(doc) -> List[str]:
    """
    Full-text Lexicon Scanning: Extract all meaningful content tokens
    (NOUN, PROPN, ADJ) as lowercase lemmas.
    """
    return [
        token.lemma_.lower()
        for token in doc
        if token.pos_ in ("NOUN", "PROPN", "ADJ")
        and not token.is_stop
        and not token.is_punct
        and len(token.text) > 1
    ]


def extract_bigrams_from_text(text: str) -> Set[str]:
    """
    N-gram Context Windows: Generate all bigrams and trigrams from lowercased
    text to capture multi-word domain phrases.
    """
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    words = cleaned.split()
    ngrams = set()
    for i in range(len(words) - 1):
        ngrams.add(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        ngrams.add(f"{words[i]} {words[i+1]} {words[i+2]}")
    return ngrams


# ---------------------------------------------------------------------------
# 4.  Scoring Engine (multi-layer approach)
# ---------------------------------------------------------------------------

def _score_categories(
    noun_chunks: List[Dict],
    verbs: List[Dict],
    svo_triples: List[Dict],
    entities: List[Dict],
    content_tokens: List[str],
    text_bigrams: Set[str],
    title_doc,
) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    """
    Multi-layer scoring engine combining:
      Layer 1: SVO triple matching       (grammatical structure – highest weight)
      Layer 2: Verb + subject matching   (POS-tag based)
      Layer 3: Noun-chunk head matching  (chunking based)
      Layer 4: NER label matching        (entity recognition)
      Layer 5: Full-text lexicon scan    (broad vocabulary coverage)
      Layer 6: Bigram/trigram matching   (multi-word domain phrases)
      Layer 7: Title-specific boosting   (title words carry extra weight)
    """
    scores: Dict[str, float] = {cat: 0.0 for cat in VALID_CATEGORIES}
    matched_patterns: Dict[str, List[str]] = {cat: [] for cat in VALID_CATEGORIES}

    token_counts = Counter(content_tokens)
    total_tokens = max(len(content_tokens), 1)

    title_tokens = set()
    if title_doc:
        title_tokens = {
            t.lemma_.lower() for t in title_doc
            if t.pos_ in ("NOUN", "PROPN", "ADJ") and not t.is_stop and len(t.text) > 1
        }

    for cat, patterns in CATEGORY_PATTERNS.items():
        subj_ind = patterns["subject_indicators"]
        verb_ind = patterns["verb_indicators"]
        obj_ind = patterns["object_indicators"]
        ent_labels = patterns["entity_labels"]
        chunk_heads = patterns["chunk_head_words"]
        lexicon = patterns.get("lexicon", set())
        cat_bigrams = patterns.get("bigrams", set())

        # === Layer 1: SVO Triple scoring ===
        for triple in svo_triples:
            subj_match = triple["subject"] in subj_ind if triple["subject"] else False
            verb_match = triple["verb"] in verb_ind
            obj_match = triple["object"] in obj_ind if triple["object"] else False

            matches = sum([subj_match, verb_match, obj_match])
            if matches == 3:
                scores[cat] += 4.0
                matched_patterns[cat].append(triple["raw"])
            elif matches == 2:
                scores[cat] += 2.0
                matched_patterns[cat].append(triple["raw"])
            elif matches == 1 and verb_match:
                scores[cat] += 0.5

        # === Layer 2: Verb + subject matching ===
        for verb in verbs:
            if verb["lemma"] in verb_ind:
                scores[cat] += 0.5
                if verb["subject_lemma"] and verb["subject_lemma"] in subj_ind:
                    scores[cat] += 1.0
                    desc = f"{verb['subject_lemma']} {verb['lemma']}"
                    if desc not in matched_patterns[cat]:
                        matched_patterns[cat].append(desc)

        # === Layer 3: Noun-chunk head-word scoring ===
        for chunk in noun_chunks:
            if chunk["root_lemma"] in chunk_heads:
                scores[cat] += 1.0
                if chunk["root_dep"] in ("nsubj", "nsubjpass"):
                    scores[cat] += 0.5
            for lemma in chunk.get("all_lemmas", []):
                if lemma in lexicon:
                    scores[cat] += 0.3

        # === Layer 4: Named-entity scoring ===
        for ent in entities:
            if ent["label"] in ent_labels:
                scores[cat] += 0.75
                ent_words = ent["text"].split()
                for w in ent_words:
                    if w in lexicon:
                        scores[cat] += 0.5

        # === Layer 5: Full-text lexicon scan ===
        for token_lemma, count in token_counts.items():
            if token_lemma in lexicon:
                freq_weight = min(count / total_tokens * 10, 2.0)
                scores[cat] += 0.4 + freq_weight * 0.2

        # === Layer 6: Bigram / trigram matching ===
        for phrase in cat_bigrams:
            if phrase in text_bigrams:
                scores[cat] += 2.5
                if phrase not in matched_patterns[cat]:
                    matched_patterns[cat].append(f'"{phrase}"')

        # === Layer 7: Title-specific boosting ===
        for title_token in title_tokens:
            if title_token in lexicon:
                scores[cat] += 1.5
            if title_token in chunk_heads:
                scores[cat] += 1.0

    return scores, matched_patterns


# ---------------------------------------------------------------------------
# 5.  Public API – classify_article()
# ---------------------------------------------------------------------------

def classify_article(title: str, content: str) -> Dict:
    """
    Classify a news article into one of the predefined categories.

    Parameters
    ----------
    title   : str – Article headline
    content : str – Article body text

    Returns
    -------
    dict with keys:
        "category"         : str   – best matching category or "general"
        "confidence"       : float – 0.0 … 1.0
        "patterns_matched" : list  – human-readable SVO / bigram patterns
    """
    text = f"{title}. {title}. {content}"

    MAX_CHARS = 15_000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]

    doc = nlp(text)
    title_doc = nlp(title) if title else None

    noun_chunks = extract_noun_chunks(doc)
    verbs = extract_main_verbs(doc)
    svo_triples = extract_svo_triples(doc)
    entities = extract_entities(doc)
    content_tokens = extract_content_tokens(doc)
    text_bigrams = extract_bigrams_from_text(text)

    scores, matched_patterns = _score_categories(
        noun_chunks, verbs, svo_triples, entities,
        content_tokens, text_bigrams, title_doc,
    )

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    total_score = sum(scores.values())
    if total_score == 0:
        confidence = 0.0
    else:
        sorted_scores = sorted(scores.values(), reverse=True)
        runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0
        dominance = best_score / total_score
        margin = (best_score - runner_up) / max(best_score, 1)
        confidence = round(0.6 * dominance + 0.4 * margin, 2)
        confidence = min(confidence, 0.99)

    MIN_CONFIDENCE = 0.10
    MIN_ABSOLUTE_SCORE = 1.5

    if confidence < MIN_CONFIDENCE or best_score < MIN_ABSOLUTE_SCORE:
        return {
            "category": "general",
            "confidence": round(confidence, 2),
            "patterns_matched": [],
        }

    unique_patterns = list(dict.fromkeys(matched_patterns[best_category]))[:10]

    return {
        "category": best_category,
        "confidence": confidence,
        "patterns_matched": unique_patterns,
    }


# ---------------------------------------------------------------------------
# 6.  Batch Classifier (for existing articles)
# ---------------------------------------------------------------------------

def classify_articles_batch(articles: List[Dict]) -> List[Dict]:
    """
    Classify a list of article dicts in-place.
    Each article should have 'title' and 'content' keys.
    """
    results = []
    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        result = classify_article(title, content)
        article["category"] = result["category"]
        article["classification_confidence"] = result["confidence"]
        article["classification_patterns"] = result["patterns_matched"]
        results.append(result)
    return results
