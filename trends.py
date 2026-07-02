import re
import random
import requests
from datetime import datetime


def fetch_trending_topics(limit: int = 15) -> list:
    """
    USA real-time trending topics fetch karta hai.
    Priority:
      1. Google Trends RSS feed (most reliable, real-time)
      2. pytrends (backup)
      3. Dynamic fallback (current year, generic viral topics)
    """
    # Method 1: Google Trends RSS (real-time, no auth needed)
    topics = _fetch_google_rss(limit)
    if topics:
        print(f"  [Trends] ✅ Google RSS se {len(topics)} real-time topics mile")
        return topics

    # Method 2: pytrends
    topics = _fetch_pytrends(limit)
    if topics:
        print(f"  [Trends] ✅ pytrends se {len(topics)} topics mile")
        return topics

    # Method 3: Dynamic fallback (current year injected)
    print("  [Trends] ⚠️ Fallback topics use ho rahe hain (no internet or API block)")
    return _dynamic_fallback(limit)


def _fetch_google_rss(limit: int) -> list:
    """
    Google Trends real-time RSS feed — most reliable method.
    URL: https://trends.google.com/trending/rss?geo=US
    """
    try:
        r = requests.get(
            "https://trends.google.com/trending/rss?geo=US",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=15
        )
        if r.status_code != 200:
            print(f"  [Trends] RSS HTTP {r.status_code}")
            return []

        # Parse <title> tags from RSS — CDATA wrapped
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
        if not titles:
            titles = re.findall(r"<title>(.*?)</title>", r.text)

        # Filter out feed-level titles (not actual trends)
        SKIP_KEYWORDS = [
            "google trends", "daily search trends", "trending searches",
            "rss", "feed", "united states"
        ]
        topics = []
        for t in titles:
            t = t.strip()
            if not t:
                continue
            lower = t.lower()
            if any(kw in lower for kw in SKIP_KEYWORDS):
                continue
            topics.append(t)

        return topics[:limit]

    except Exception as e:
        print(f"  [Trends] RSS error: {e}")
        return []


def _fetch_pytrends(limit: int) -> list:
    """pytrends Google Trends API — secondary method."""
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=-300, timeout=(10, 25))
        df = pt.trending_searches(pn="united_states")
        topics = df[0].tolist()[:limit]
        return [t for t in topics if t.strip()]
    except Exception as e:
        print(f"  [Trends] pytrends error: {e}")
        return []


def _dynamic_fallback(limit: int) -> list:
    """
    Jab koi bhi API kaam na kare — evergreen viral topics.
    Current year automatically inject hota hai.
    """
    year = datetime.utcnow().year
    topics = [
        f"AI replacing jobs {year}",
        f"US economy update {year}",
        f"SpaceX launch {year}",
        f"Bitcoin price surge {year}",
        f"NASA discovery {year}",
        f"OpenAI GPT update {year}",
        f"Stock market news {year}",
        f"Climate change record {year}",
        f"Tesla new model {year}",
        f"US election news {year}",
        f"Google AI breakthrough {year}",
        f"Apple iPhone reveal {year}",
        f"Hollywood celebrity news {year}",
        f"NFL highlights {year}",
        f"Viral news story {year}",
    ]
    random.shuffle(topics)
    return topics[:limit]


def get_single_topic(topic: str = None) -> str:
    """Single topic return karta hai — manual input ya auto-fetched."""
    if topic and topic.strip():
        return topic.strip()
    topics = fetch_trending_topics(limit=10)
    if topics:
        return topics[0]
    return f"Breaking News {datetime.utcnow().year}"
