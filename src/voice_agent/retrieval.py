"""Small, bounded retrieval clients. No conversations or credentials are logged."""
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

import httpx

OFFICIAL_DOMAINS = ("gov.in", "nic.in", "rbi.org.in", "nabard.org")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value, limit=3000):
    parser = _Text()
    parser.feed(value if isinstance(value, str) else "")
    return " ".join(" ".join(parser.parts).split())[:limit]


def official_url(url):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and not parsed.username and any(
            host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS
        )
    except (ValueError, TypeError):
        return False


def safe_query(query):
    # Reject common identifiers; the agent must also construct impersonal queries.
    query = query.strip()
    if not query or len(query) > 500 or re.search(
        r"@|https?://|(?:\d[\s-]*){7,}|\b[A-Z]{5}\d{4}[A-Z]\b", query, re.I
    ):
        raise ValueError("Use a short topic/location query without personal identifiers.")
    return query


def result(status, sources=None):
    return {"status": status, "sources": sources or []}


def source(identifier, title, url, excerpt, kind, published=None):
    return {
        "id": identifier, "title": plain(title, 300), "url": url,
        "excerpt": plain(excerpt), "kind": kind,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "published_date": published if isinstance(published, str) else None,
    }


class Retrieval:
    def __init__(self, tavily_key=None, kanoon_token=None, *, transport=None):
        self.tavily_key = tavily_key
        self.kanoon_token = kanoon_token
        self.transport = transport
        self.legal_documents = {}  # Only documents found in this session may be fetched.

    async def _request(self, url, headers, **kwargs):
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            for attempt in range(2):
                try:
                    response = await client.post(url, headers=headers, **kwargs)
                    if response.status_code in (401, 403):
                        return "unauthorized", None
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 0:
                            await asyncio.sleep(0.25)
                            continue
                        return "rate_limited" if response.status_code == 429 else "unavailable", None
                    response.raise_for_status()
                    body = response.json()
                    return ("ok", body) if isinstance(body, dict) else ("invalid_response", None)
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt == 1:
                        return "unavailable", None
                except (httpx.HTTPStatusError, ValueError):
                    return "invalid_response", None
        return "unavailable", None

    async def official(self, query):
        query = safe_query(query)
        if not self.tavily_key:
            return result("not_configured")
        status, body = await self._request(
            "https://api.tavily.com/search",
            {"Authorization": f"Bearer {self.tavily_key}"},
            json={"query": query, "include_domains": list(OFFICIAL_DOMAINS),
                  "max_results": 5, "search_depth": "basic", "include_answer": False},
        )
        if status != "ok":
            return result(status)
        if not isinstance(body.get("results"), list):
            return result("invalid_response")
        sources = []
        for item in body["results"][:5]:
            if not isinstance(item, dict) or not official_url(item.get("url")):
                continue
            if not plain(item.get("content")):
                continue
            sources.append(source(item["url"], item.get("title"), item["url"],
                                  item["content"], "official", item.get("published_date")))
        return result("ok" if sources else "empty", sources)

    async def legal(self, query):
        query = safe_query(query)
        if not self.kanoon_token:
            return result("not_configured")
        status, body = await self._request(
            "https://api.indiankanoon.org/search/", self._kanoon_headers(),
            params={"formInput": query, "pagenum": 0},
        )
        if status != "ok":
            return result(status)
        if not isinstance(body.get("docs"), list):
            return result("invalid_response")
        sources = []
        for item in body["docs"][:5]:
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("tid", ""))
            if not doc_id.isascii() or not doc_id.isdigit():
                continue
            origin = str(item.get("docsource", ""))
            # Do not infer legislation from a judgment title mentioning an Act.
            kind = "judgment" if re.search(r"\b(court|tribunal)\b", origin, re.I) else (
                "legislation" if re.search(r"\bacts?\b", origin, re.I) else "legal_document"
            )
            entry = source(doc_id, item.get("title"), f"https://indiankanoon.org/doc/{doc_id}/",
                           item.get("headline"), kind, item.get("publishdate"))
            self.legal_documents[doc_id] = entry
            sources.append(entry)
        return result("ok" if sources else "empty", sources)

    def _kanoon_headers(self):
        return {"Authorization": f"Token {self.kanoon_token}", "Accept": "application/json"}

    async def excerpt(self, doc_id, query):
        query = safe_query(query)
        if not self.kanoon_token:
            return result("not_configured")
        if doc_id not in self.legal_documents:
            return result("unknown_document")
        status, body = await self._request(
            f"https://api.indiankanoon.org/docfragment/{doc_id}/", self._kanoon_headers(),
            params={"formInput": query},
        )
        if status != "ok":
            return result(status)
        excerpt = plain(body.get("headline"))
        if not excerpt:
            return result("empty")
        entry = dict(self.legal_documents[doc_id], excerpt=excerpt,
                     retrieved_at=datetime.now(timezone.utc).isoformat())
        return result("ok", [entry])
