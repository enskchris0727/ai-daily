"""去重：同一条内容可能来自多个来源，或者同一来源给出多个地址。"""

import re

from .normalize import canonical_url

_PUNCT = re.compile(r"[\s\-_·—–|:：,，.。!！?？\"'“”‘’()（）\[\]【】]+")


def _title_key(title):
    """把标题压成用于比较的键（去掉标点与大小写差异）。"""
    return _PUNCT.sub("", (title or "").lower())


def _prefer(a, b):
    """两条记录里挑保留价值更高的那条。

    优先保留发布时间更早的（更接近真实发布时间，而不是抓取时间兜底），
    其次保留标题更完整的。
    """
    if a["published_at"] != b["published_at"]:
        return a if a["published_at"] < b["published_at"] else b
    return a if len(a["title"]) >= len(b["title"]) else b


def dedupe(items):
    """按规范 URL 与标题两轮去重，返回去重后的列表。"""
    by_id = {}
    for item in items:
        key = item["id"]
        by_id[key] = item if key not in by_id else _prefer(by_id[key], item)

    by_title = {}
    for item in by_id.values():
        key = _title_key(item["title"])
        if not key:
            key = item["id"]
        by_title[key] = item if key not in by_title else _prefer(by_title[key], item)

    return list(by_title.values())