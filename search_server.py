from __future__ import annotations

import html
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from servers.common import handle_request


class DuckDuckGoResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_link = False
        self._in_snippet = False
        self._current_href = ""
        self._current_title = ""
        self._current_snippet = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get("class", "") or ""

        if tag == "a" and "result__a" in class_name:
            self._in_link = True
            self._current_href = attrs_dict.get("href", "") or ""
            self._current_title = ""

        if tag == "a" and "result__snippet" in class_name:
            self._in_snippet = True
            self._current_snippet = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._current_title:
                self.results.append(
                    {
                        "title": html.unescape(self._current_title.strip()),
                        "snippet": "",
                        "url": self._normalize_url(self._current_href),
                        "source": "DuckDuckGo",
                    }
                )
            self._current_href = ""
            self._current_title = ""

        elif tag == "a" and self._in_snippet:
            self._in_snippet = False
            if self.results and self._current_snippet:
                self.results[-1]["snippet"] = html.unescape(self._current_snippet.strip())
            self._current_snippet = ""

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._current_title += data
        elif self._in_snippet:
            self._current_snippet += data

    def _normalize_url(self, href: str) -> str:
        parsed = urllib.parse.urlparse(href)
        if parsed.path == "/l/" and parsed.query:
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg")
            if uddg:
                return urllib.parse.unquote(uddg[0])
        return href


def search_web(arguments: dict) -> dict:
    query = arguments.get("query", "").strip()
    if not query:
        raise ValueError("query is required for search")

    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        html_text = response.read().decode("utf-8", errors="ignore")

    parser = DuckDuckGoResultsParser()
    parser.feed(html_text)
    results = [item for item in parser.results if item.get("title")][:8]

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }


if __name__ == "__main__":
    handle_request(
        tools={
            "search_web": search_web,
            "search": search_web,
            "lookup": search_web,
        },
        descriptions=[
            {
                "name": "search_web",
                "description": "Search the web for a user query and return summarized results.",
            },
            {
                "name": "search",
                "description": "Alias for web search.",
            },
            {
                "name": "lookup",
                "description": "Alias for web search.",
            },
        ],
    )
