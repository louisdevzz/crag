"""Controlled Web Search Tool with Official Vietnamese Legal Domain Filtering."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import OFFICIAL_DOMAINS


def is_allowed_source(url: str) -> bool:
    """Validate whether an external URL belongs to approved Vietnamese legal portals."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if ":" in host:
            host = host.split(":")[0]
        return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)
    except Exception:
        return False


def clean_web_text(html_content: str) -> str:
    """Extract clean text content from HTML, removing scripts and navigation chrome."""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Clean whitespace
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return "\n".join(lines)


def search_official_web(
    query: str,
    max_results: int = 5,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """Execute controlled web search restricted to official government legal domains.

    Parameters
    ----------
    query : str
        Legal search query (typically rewritten by Agent).
    max_results : int
        Maximum search hits to return.
    timeout : int
        HTTP timeout in seconds.

    Returns
    -------
    list of dict
        Validated external candidate pages.
    """
    candidates: List[Dict[str, Any]] = []

    # Attempt live search via DuckDuckGo
    try:
        from duckduckgo_search import DDGS

        ddgs = DDGS()
        # Constrain to allowed domains in query or post-filter
        domain_filter = " OR ".join([f"site:{d}" for d in list(OFFICIAL_DOMAINS)[:3]])
        full_query = f"{query} ({domain_filter})"

        raw_results = list(ddgs.text(full_query, max_results=max_results * 2))
        for r in raw_results:
            url = r.get("href") or r.get("link") or ""
            if is_allowed_source(url):
                candidates.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("body", ""),
                    "source_domain": urlparse(url).netloc,
                })
                if len(candidates) >= max_results:
                    break
    except Exception as e:
        # Fallback to general query or graceful offline handling
        pass

    return candidates


def fetch_external_evidence(
    candidates: List[Dict[str, Any]],
    max_chars: int = 2000,
) -> List[Dict[str, Any]]:
    """Fetch and parse content from verified candidate URLs into evidence strips."""
    evidence_items: List[Dict[str, Any]] = []

    for idx, cand in enumerate(candidates, start=1):
        url = cand.get("url", "")
        title = cand.get("title", f"Nguồn ngoài #{idx}")
        snippet = cand.get("snippet", "")

        text_content = snippet
        try:
            resp = requests.get(
                url,
                timeout=5,
                headers={"User-Agent": "LegalCRAGAssistant/3.0 (Educational Academic Research)"},
            )
            if resp.status_code == 200:
                parsed = clean_web_text(resp.text)
                if len(parsed) > 100:
                    text_content = parsed[:max_chars]
        except Exception:
            # If network fetch fails, fall back to search snippet
            pass

        evidence_items.append({
            "strip_id": f"EXT_{idx}",
            "evidence_id": f"EXT_{idx}",
            "heading": title,
            "text": text_content,
            "source_url": url,
            "source_priority": 1,  # 1 = External auxiliary, 2 = Official internal
            "score": 0.0,
            "metadata": {
                "document_title": title,
                "source_url": url,
                "is_external": True,
            }
        })

    return evidence_items
