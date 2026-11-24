import logging
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.config import settings
from app.database import db
from app.services.market_data import is_crypto_ticker, normalize_ticker

logger = logging.getLogger(__name__)

_VADER = SentimentIntensityAnalyzer()
# Enhance VADER financial lexicon slightly for cleaner market headline scoring
_VADER.lexicon.update(
    {
        "beat": 2.0,
        "beats": 2.0,
        "upgrade": 2.1,
        "upgraded": 2.1,
        "outperform": 2.0,
        "breakout": 1.9,
        "surge": 2.2,
        "surges": 2.2,
        "rally": 1.9,
        "record": 1.3,
        "guidance": 0.4,
        "raised": 1.6,
        "downgrade": -2.2,
        "downgraded": -2.2,
        "miss": -2.0,
        "misses": -2.0,
        "plunge": -2.4,
        "plunges": -2.4,
        "slump": -2.0,
        "layoffs": -1.8,
        "lawsuit": -1.9,
        "sec": -0.6,
        "probe": -1.7,
        "investigation": -1.8,
        "hack": -2.6,
        "exploit": -2.5,
        "bankruptcy": -3.0,
        "dilution": -1.8,
        "offering": -0.9,
    }
)

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

CRYPTO_RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]


def _clean_html(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:320]


def score_sentiment(text: str) -> dict[str, Any]:
    scores = _VADER.polarity_scores(text or "")
    compound = round(float(scores["compound"]), 3)
    if compound >= 0.12:
        label = "Positivo"
        code = "positive"
    elif compound <= -0.12:
        label = "Negativo"
        code = "negative"
    else:
        label = "Neutro"
        code = "neutral"
    return {"label": label, "code": code, "score": compound}


def _fetch_rss(url: str, source_fallback: str, max_items: int = 12) -> tuple[list[dict[str, Any]], str | None]:
    try:
        with httpx.Client(timeout=7.0, follow_redirects=True, headers=_HTTP_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)

        items: list[dict[str, Any]] = []
        for entry in parsed.entries[:max_items]:
            title = _clean_html(entry.get("title", ""))
            if not title:
                continue
            summary = _clean_html(entry.get("summary", "") or entry.get("description", ""))
            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")
            pub_ts = time.time()
            if entry.get("published_parsed"):
                try:
                    pub_ts = datetime(*entry.published_parsed[:6]).timestamp()
                except Exception:
                    pass

            source = source_fallback
            if isinstance(entry.get("source"), dict) and entry["source"].get("title"):
                source = str(entry["source"]["title"])

            sentiment = score_sentiment(f"{title}. {summary}")
            items.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": source,
                    "published": published,
                    "published_ts": pub_ts,
                    "sentiment": sentiment,
                }
            )
        return items, None
    except Exception as exc:
        logger.debug("Falha RSS %s: %s", url, exc)
        return [], f"Feed {source_fallback} indisponível ({type(exc).__name__})."


def get_asset_news(
    ticker: str,
    company_name: str | None = None,
    limit: int = 12,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Fetches free RSS news (Yahoo Finance RSS, Google News RSS, Crypto feeds)
    and applies local VADER sentiment scoring with 15-min SQLite TTL cache.
    """
    norm = normalize_ticker(ticker)
    cache_key = f"news:{norm}"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            return cached

    is_crypto = is_crypto_ticker(norm)
    base_sym = norm.replace("-USD", "")
    warnings: list[str] = []
    collected: list[dict[str, Any]] = []

    # 1. Yahoo Finance RSS (free, no key)
    yahoo_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(norm)}&region=US&lang=en-US"
    y_items, y_warn = _fetch_rss(yahoo_url, "Yahoo Finance", max_items=10)
    collected.extend(y_items)
    if y_warn:
        warnings.append(y_warn)

    # 2. Google News RSS (free, targeted search)
    if is_crypto:
        q = f"{base_sym} crypto OR cryptocurrency"
    else:
        q = f"{norm} stock" if not company_name or company_name == norm else f'"{norm}" OR "{company_name}" stock'
    gnews_url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en"
    g_items, g_warn = _fetch_rss(gnews_url, "Google News", max_items=10)
    collected.extend(g_items)
    if g_warn:
        warnings.append(g_warn)

    # 3. Crypto-specific RSS feeds filtered by symbol/name
    if is_crypto:
        keywords = {base_sym.lower()}
        if company_name:
            first_word = company_name.split()[0].lower()
            if len(first_word) >= 3:
                keywords.add(first_word)
        crypto_name_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "AVAX": "avalanche",
            "LINK": "chainlink",
            "BNB": "binance",
        }
        if base_sym in crypto_name_map:
            keywords.add(crypto_name_map[base_sym])

        for feed_name, feed_url in CRYPTO_RSS_FEEDS[:2]:
            c_items, c_warn = _fetch_rss(feed_url, feed_name, max_items=18)
            if c_warn:
                warnings.append(c_warn)
                continue
            for it in c_items:
                blob = f"{it['title']} {it['summary']}".lower()
                if any(kw in blob for kw in keywords):
                    collected.append(it)

    # Deduplicate by normalized title prefix
    seen: set[str] = set()
    unique_items: list[dict[str, Any]] = []
    for it in sorted(collected, key=lambda x: x["published_ts"], reverse=True):
        key = re.sub(r"[^a-z0-9]", "", it["title"].lower())[:55]
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(it)
        if len(unique_items) >= limit:
            break

    # Aggregate sentiment summary
    pos = sum(1 for x in unique_items if x["sentiment"]["code"] == "positive")
    neg = sum(1 for x in unique_items if x["sentiment"]["code"] == "negative")
    neu = sum(1 for x in unique_items if x["sentiment"]["code"] == "neutral")
    avg_score = (
        round(sum(x["sentiment"]["score"] for x in unique_items) / len(unique_items), 3)
        if unique_items
        else 0.0
    )
    if avg_score >= 0.12:
        overall = "Positivo"
    elif avg_score <= -0.12:
        overall = "Negativo"
    else:
        overall = "Neutro"

    payload = {
        "ticker": norm,
        "updated_at": time.time(),
        "items": unique_items,
        "sentiment_summary": {
            "overall": overall,
            "average_score": avg_score,
            "positive": pos,
            "neutral": neu,
            "negative": neg,
            "total": len(unique_items),
        },
        "warnings": warnings,
    }

    if unique_items:
        db.cache_set(cache_key, "news", payload, settings.cache_ttl_news)
    else:
        stale = db.cache_get(cache_key, allow_stale=True)
        if stale and isinstance(stale, dict) and stale.get("items"):
            stale["warnings"] = warnings + ["Notícias carregadas de cache anterior."]
            return stale

    return payload
