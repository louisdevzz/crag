"""Controlled Web Search Tool with Official Vietnamese Legal Domain Filtering.

Modeled after Hermes Agent and OpenClaw web search tools.
Enforces domain allow-list, cleans HTML chrome, and packages into standardized evidence strips.
"""
from __future__ import annotations

import re
import warnings
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from config import OFFICIAL_DOMAINS
from tools.base import BaseLegalTool

# Suppress duckduckgo rename warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")


class ControlledWebSearchInput(BaseModel):
    """Input argument schema for controlled legal web search."""
    query: str = Field(..., min_length=2, description="Câu tìm kiếm cụ thể, súc tích cho cổng thông tin pháp luật nhà nước (do bạn tự soạn)")
    max_results: int = Field(default=4, ge=1, le=10, description="Max external candidates to retrieve")
    allowed_domains: Optional[List[str]] = Field(default=None, description="Domain allow-list overrides")


class ControlledWebSearchTool(BaseLegalTool):
    """Tool for querying official Vietnamese government legal portals.

    The calling agent composes `query` itself (no separate query-rewrite step) —
    it already has the user's question, conversation history, and any prior
    `crag_search` evidence, so it is best placed to phrase a precise search string.
    """

    name: str = "controlled_web_search"
    description: str = (
        "Tìm kiếm có kiểm soát trên các cổng thông tin pháp luật chính thống của nhà nước "
        "(vbpl.vn, chinhphu.vn, moj.gov.vn...). Dùng khi crag_search trả về bằng chứng nội bộ "
        "không đủ (AMBIGUOUS/INCORRECT). Hãy tự soạn một câu truy vấn tìm kiếm cụ thể, không "
        "chép nguyên văn câu hỏi của người dùng."
    )
    args_schema = ControlledWebSearchInput

    def __init__(self, allowed_domains: Optional[Set[str]] = None):
        self.allowed_domains = allowed_domains or OFFICIAL_DOMAINS

    def execute(
        self,
        query: str,
        max_results: int = 4,
        allowed_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search, fetch, and refine verified legal web evidence into ready-to-cite strips."""
        domains = set(allowed_domains) if allowed_domains else self.allowed_domains
        candidates = search_official_web(query, max_results=max_results, allowed_domains=domains)
        raw_evidence = fetch_external_evidence(candidates, max_chars=1500)
        from retrieval.refine import refine_external
        refined = refine_external(query, raw_evidence)
        return {"evidence": refined, "candidates_found": len(candidates)}


def is_allowed_source(url: str, allowed_domains: Optional[Set[str]] = None) -> bool:
    """Validate whether an external URL belongs to approved Vietnamese legal portals."""
    domains = allowed_domains or OFFICIAL_DOMAINS
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if ":" in host:
            host = host.split(":")[0]
        return any(host == d or host.endswith("." + d) for d in domains)
    except Exception:
        return False


def clean_web_text(html_content: str) -> str:
    """Extract clean text content from HTML, removing scripts and navigation chrome."""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return "\n".join(lines)


def search_official_web(
    query: str,
    max_results: int = 5,
    allowed_domains: Optional[Set[str]] = None,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """Execute controlled web search restricted to official government legal domains."""
    domains = allowed_domains or OFFICIAL_DOMAINS
    candidates: List[Dict[str, Any]] = []

    try:
        from duckduckgo_search import DDGS

        ddgs = DDGS()
        domain_filter = " OR ".join([f"site:{d}" for d in list(domains)[:3]])
        full_query = f"{query} ({domain_filter})"

        raw_results = list(ddgs.text(full_query, max_results=max_results * 2))
        for r in raw_results:
            url = r.get("href") or r.get("link") or ""
            if is_allowed_source(url, domains):
                candidates.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("body", ""),
                    "source_domain": urlparse(url).netloc,
                })
                if len(candidates) >= max_results:
                    break
    except Exception:
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
            pass

        evidence_items.append({
            "strip_id": f"EXT_{idx}",
            "evidence_id": f"EXT_{idx}",
            "heading": title,
            "text": text_content,
            "source_url": url,
            "source_priority": 1,
            "score": 0.0,
            "metadata": {
                "document_title": title,
                "source_url": url,
                "is_external": True,
            },
        })

    return evidence_items
