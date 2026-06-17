"""
web_search / web_fetch — Tavily 搜索 + 网页抓取
"""

import os, urllib.request, urllib.error
from html import unescape
from .base import ToolHandler


class WebSearchHandler(ToolHandler):
    name = "web_search"
    description = "搜索网页（Tavily API），返回标题、内容摘要和链接，结果可直接用于回答。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        }

    def execute(self, tool_input: dict) -> str:
        query = tool_input["query"]
        try:
            from tavily import TavilyClient
            key = os.environ.get("TAVILY_API_KEY", "")
            if not key:
                return "Tavily API key not set. Set TAVILY_API_KEY env var."

            client = TavilyClient(api_key=key)
            r = client.search(query, max_results=5, include_raw_content=False)

            results = []
            for item in r.get("results", []):
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")[:300]
                results.append(f"{title}\n  {url}\n  {content}")

            answer = r.get("answer", "")
            if answer:
                results.insert(0, f"[Tavily Answer] {answer}")

            return "\n\n".join(results) if results else f"no results: {query}"
        except Exception as e:
            return f"search error: {e}"


class WebFetchHandler(ToolHandler):
    name = "web_fetch"
    description = "抓取网页内容，返回纯文本。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "网页 URL"}},
            "required": ["url"],
        }

    def execute(self, tool_input: dict) -> str:
        url = tool_input["url"]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
            if proxy:
                handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                opener = urllib.request.build_opener(handler)
                resp = opener.open(req, timeout=15)
            else:
                resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode("utf-8", errors="replace")
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 3000:
                text = text[:3000] + "\n... (truncated)"
            return text or "(empty)"
        except urllib.error.URLError as e:
            return f"fetch failed: {e}"
        except Exception as e:
            return f"fetch error: {e}"
