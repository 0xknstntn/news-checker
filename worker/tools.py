from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
import os
import json
import asyncio
import re
from datetime import datetime, timedelta

from serpapi import GoogleSearch

import aiohttp
from dotenv import load_dotenv

load_dotenv(override=True)

try:
        from duckduckgo_search import DDGS
        _HAS_DDG = True
except Exception:
        _HAS_DDG = False

try:
        _HAS_SERP = True
except Exception:
        _HAS_SERP = False

try:
        import trafilatura
        _HAS_TRAF = True
except Exception:
        _HAS_TRAF = False

""" INIT Inputs """
class NewsSearchInput(BaseModel):
        query: str = Field(..., description="Поисковый запрос по новости")
        max_results: int = Field(8, ge=1, le=25, description="Максимум результатов")
        days: int = Field(7, ge=1, le=90, description="Ограничение давности (в днях)")

class FetchAndSummarizeInput(BaseModel):
        url: str = Field(..., description="URL статьи/новости")
        char_limit: int = Field(2000, ge=200, le=20000, description="Ограничение длины извлечённого текста")
""" END """


def _normalize_dt(dt_str: Optional[str]) -> Optional[str]:
        if not dt_str:
                return None
        rel = re.search(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", dt_str)
        if rel:
                n, unit = int(rel.group(1)), rel.group(2)
                delta = {
                        "minute": timedelta(minutes=n),
                        "hour": timedelta(hours=n),
                        "day": timedelta(days=n),
                        "week": timedelta(weeks=n),
                        "month": timedelta(days=30*n),
                }[unit]
                return (datetime.utcnow() - delta).isoformat() + "Z"
        try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).isoformat() + "Z"
        except Exception:
                return dt_str

def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for r in items:
                url = (r.get("url") or "").split("#")[0]
                if not url or url in seen:
                        continue
                seen.add(url)
                out.append(r)
        return out

async def _fetch(session: aiohttp.ClientSession, url: str, timeout: int = 15) -> str:
        async with session.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (NewsAgent/1.0)"}) as resp:
                resp.raise_for_status()
                return await resp.text()

def _extract_text(html: str, url: str) -> str:
        if _HAS_TRAF:
                txt = trafilatura.extract(html, include_comments=False, include_tables=False, favor_recall=True, url=url)
                if txt:
                        return " ".join(txt.split())
        txt = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        txt = re.sub(r"<style[\s\S]*?</style>", " ", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt)
        return txt.strip()


def _ddg_news(query: str, max_results: int, days: int) -> List[Dict[str, Any]]:
        if not _HAS_DDG:
                return []
        tl = "d" if days <= 1 else ("w" if days <= 7 else "m")
        out = []
        with DDGS() as ddgs:
                for r in ddgs.news(query, timelimit=tl, max_results=max_results):
                        out.append({
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "snippet": r.get("body"),
                                "source": r.get("source"),
                                "published_at": _normalize_dt(r.get("date")),
                                "engine": "duckduckgo_news",
                        })
        return out

def _ddg_web(query: str, max_results: int) -> List[Dict[str, Any]]:
        if not _HAS_DDG:
                return []
        out = []
        with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results, region="wt-wt", safesearch="off"):
                        out.append({
                                "title": r.get("title"),
                                "url": r.get("href"),
                                "snippet": r.get("body"),
                                "source": "duckduckgo_web",
                                "published_at": None,
                                "engine": "duckduckgo_web",
                        })
        return out

def _serp_google_news(query: str, max_results: int, days: int) -> List[Dict[str, Any]]:
        if not _HAS_SERP:
                return []
        params = {
                "engine": "google_news",
                "q": query,
                "hl": "en",
                "gl": "us",
                "num": max_results,
                "api_key": os.environ["SERPAPI_API_KEY"]
        }
        cutoff = datetime.utcnow() - timedelta(days=days)
        search = GoogleSearch(params)
        data = search.get_dict() or {}
        articles = data.get("news_results", []) or data.get("articles", [])
        out = []
        for a in articles:
                date_str = a.get("date") or a.get("published_date")
                iso = _normalize_dt(date_str)
                try:
                        if iso and datetime.fromisoformat(iso.replace("Z", "+00:00")) < cutoff:
                                continue
                except Exception:
                        pass
                out.append({
                        "title": a.get("title"),
                        "url": a.get("link") or a.get("url"),
                        "snippet": a.get("snippet") or a.get("excerpt"),
                        "source": (a.get("source") or {}).get("name") if isinstance(a.get("source"), dict) else a.get("source"),
                        "published_at": iso,
                        "engine": "google_news_serpapi",
                })
        return out

def _serp_google_web(query: str, max_results: int) -> List[Dict[str, Any]]:
        if not _HAS_SERP:
                return []
        params = {
                "engine": "google",
                "q": query,
                "num": max_results,
                "api_key": os.environ["SERPAPI_API_KEY"]
        }
        search = GoogleSearch(params)
        data = search.get_dict() or {}
        out = []
        for r in data.get("organic_results", []):
                out.append({
                        "title": r.get("title"),
                        "url": r.get("link"),
                        "snippet": r.get("snippet"),
                        "source": "google_web_serpapi",
                        "published_at": None,
                        "engine": "google_web_serpapi",
                })
        return out


""" Tools """
class NewsSearchTool(BaseTool):
        name: str = "news_search"
        description: str = (
                "Searches for the most relevant and recent news articles and web results "
                "related to a given query. Combines multiple sources (Google News, Google Web, "
                "DuckDuckGo News, DuckDuckGo Web), removes duplicates, sorts results by "
                "publication date, and returns the top matches in JSON format."
        )
        args_schema: Type[BaseModel] = NewsSearchInput

        def _run(self, query: str, max_results: int = 8, days: int = 7) -> str:
                results = []
                results += _serp_google_news(query, max_results=max_results, days=days)
                results += _serp_google_web(query, max_results=min(6, max_results))
                results += _ddg_news(query, max_results=max_results, days=days)
                results += _ddg_web(query, max_results=min(6, max_results))
                unique = _dedupe(results)
                def _score(item):
                        ts = item.get("published_at")
                        try:
                                return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime(1970, 1, 1)
                        except Exception:
                                return datetime(1970, 1, 1)
                unique.sort(key=_score, reverse=True)
                print(f"[news_search] Found {len(unique)} unique results for query='{query}'")
                return json.dumps(unique[:max_results], ensure_ascii=False)

        async def _arun(self, query: str, max_results: int = 8, days: int = 7) -> str:
                return await asyncio.to_thread(self._run, query, max_results, days)


class FetchAndSummarizeTool(BaseTool):
        name: str = "fetch_and_summarize"
        description: str = (
                "Fetches the content of a given URL, extracts clean readable text from the HTML, "
                "and returns a JSON object containing the page URL, an optional title, "
                "a text excerpt (up to the specified character limit), and the fetch timestamp. "
                "If extraction fails or the page is empty, an error message is included."
        )
        args_schema: Type[BaseModel] = FetchAndSummarizeInput

        def _run(self, url: str, char_limit: int = 2000) -> str:
                return asyncio.run(self._async_impl(url, char_limit))

        async def _arun(self, url: str, char_limit: int = 2000) -> str:
                return await self._async_impl(url, char_limit)

        async def _async_impl(self, url: str, char_limit: int) -> str:
                try:
                        async with aiohttp.ClientSession() as session:
                                html = await _fetch(session, url)
                        text = _extract_text(html, url)
                        if not text:
                                return json.dumps({"url": url, "title": None, "excerpt": "", "error": "empty"}, ensure_ascii=False)
                        head = text.split(". ")[0].strip()
                        title = head if 5 <= len(head) <= 180 else None
                        payload = {
                                "url": url,
                                "title": title,
                                "excerpt": text[:char_limit],
                                "fetched_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
                        }
                        return json.dumps(payload, ensure_ascii=False)
                except aiohttp.ClientResponseError as e:
                        err = f"{e.status} {getattr(e, 'message', '')}".strip()
                        return json.dumps({"url": url, "title": None, "excerpt": "", "error": f"blocked:{err}"}, ensure_ascii=False)
                except Exception as e:
                        return json.dumps({"url": url, "title": None, "excerpt": "", "error": str(e)}, ensure_ascii=False)
""" END """

def get_tools():
        tools = [
                NewsSearchTool(),
                FetchAndSummarizeTool(),
        ]
        return tools
