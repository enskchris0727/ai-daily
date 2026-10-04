"""网页收集器：从列表页里提取文章链接。

策略是先看页面有没有 JSON-LD 结构化数据（最可靠），
没有再退回 DOM 启发式规则。
"""

import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .. import fetcher
from ..normalize import clean_text, parse_date

ARTICLE_HINT = re.compile(
    r"/(20\d{2}/|news/|blog/|article|post|p/|archives/|insight|detail|zh-cn/news)",
    re.I,
)
BAD_HREF = re.compile(r"(javascript:|mailto:|#|\.(css|js|png|jpe?g|svg|gif|webp|ico|pdf)$)", re.I)
# 导航、分类、标签、作者页不是文章
NAV_HREF = re.compile(r"/(tag|tags|category|categories|topic|topics|author|authors|page|search|about|careers|contact|legal|privacy|events|webinar)s?(/|$)", re.I)
# 这类短标题基本是导航按钮，不是文章
JUNK_TITLE = {
    "read article", "read more", "learn more", "read now", "see more", "view all",
    "enterprise ai", "ai for developers", "product launch", "company news",
    "open science", "for business", "sovereign ai", "ai governance",
    "healthcare & life sciences", "manufacturing", "energy & utilities",
    "public sector", "customer stories", "news", "blog", "research", "products",
}
MIN_TITLE = 12
MAX_TITLE = 300
DATE_HINT = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")


def _from_json_ld(soup, base_url):
    """尝试从 JSON-LD 里取文章列表。"""
    items = []

    def walk(node):
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any(t in ("BlogPosting", "NewsArticle", "Article", "TechArticle") for t in types if t):
            url = node.get("url") or node.get("mainEntityOfPage")
            if isinstance(url, dict):
                url = url.get("@id")
            headline = node.get("headline") or node.get("name")
            if url and headline:
                items.append({
                    "title": headline,
                    "url": urljoin(base_url, url),
                    "published_at": node.get("datePublished") or node.get("dateModified"),
                })
        for value in node.values():
            walk(value)

    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except (ValueError, TypeError):
            continue
    return items


def _from_dom(soup, base_url):
    """DOM 启发式：找标题像文章、链接像文章的 a 标签。"""
    host = urlsplit(base_url).netloc
    items = []
    seen = set()

    candidates = soup.find_all(["article", "li", "div", "section"])
    anchors = []
    for node in candidates:
        for a in node.find_all("a", href=True, recursive=False):
            anchors.append((a, node))
    anchors.extend((a, None) for a in soup.find_all("a", href=True))

    for a, container in anchors:
        href = a["href"].strip()
        if not href or BAD_HREF.search(href):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if not (MIN_TITLE <= len(title) <= MAX_TITLE):
            continue
        if title.strip().lower() in JUNK_TITLE:
            continue
        if NAV_HREF.search(urlsplit(href).path):
            continue
        absolute = urljoin(base_url, href)
        if urlsplit(absolute).netloc != host:
            continue
        path = urlsplit(absolute).path
        if not ARTICLE_HINT.search(path):
            continue
        if NAV_HREF.search(path):
            continue
        # 文章页的地址通常有较长的末段（slug 或数字 id）
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        if len(slug) < 8:
            continue

        published = None
        if container is not None:
            time_tag = container.find("time")
            if time_tag:
                published = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
            if not published:
                m = DATE_HINT.search(clean_text(container.get_text(" ", strip=True)))
                if m:
                    published = m.group(0)

        key = absolute.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        items.append({"title": title, "url": absolute, "published_at": published})

    return items


def collect(source):
    resp = fetcher.fetch(source["url"])
    soup = BeautifulSoup(fetcher.decode(resp), "html.parser")

    items = _from_json_ld(soup, source["url"])
    if len(items) < 3:
        dom_items = _from_dom(soup, source["url"])
        known = set(i["url"] for i in items)
        items.extend(i for i in dom_items if i["url"] not in known)

    for item in items:
        if item.get("published_at"):
            item["published_at"] = parse_date(item["published_at"]) or item["published_at"]

    if not items:
        raise ValueError("页面里没有找到文章列表")
    return items