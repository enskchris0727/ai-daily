"""RSS / Atom 收集器。arXiv 的接口也是 Atom，走这里。"""

import feedparser

from .. import fetcher


def _entry_date(entry):
    for key in ("published", "updated", "created"):
        if entry.get(key):
            return entry[key]
    return None


def collect(source):
    resp = fetcher.fetch(source["url"])
    parsed = feedparser.parse(fetcher.decode(resp))

    if getattr(parsed, "bozo", 0) and not parsed.entries:
        raise ValueError("订阅源解析失败：%s" % getattr(parsed, "bozo_exception", "未知原因"))
    if not parsed.entries:
        raise ValueError("订阅源里没有任何条目")

    items = []
    for entry in parsed.entries:
        link = entry.get("link") or ""
        if not link:
            for l in entry.get("links", []) or []:
                if l.get("href"):
                    link = l["href"]
                    break
        items.append({
            "title": entry.get("title"),
            "url": link,
            "published_at": _entry_date(entry),
        })
    return items