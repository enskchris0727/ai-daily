"""关键词匹配：把综合科技媒体里的 AI 相关内容筛出来。

英文关键词用词边界匹配，避免 "AI" 命中 "said" 这类误判；
中文关键词按子串匹配。
"""

import re

_ASCII_WORD = re.compile(r"^[A-Za-z0-9+#.\- ]+$")
_cache = {}


def _pattern(keyword):
    key = keyword.strip()
    if not key:
        return None
    if key in _cache:
        return _cache[key]
    if _ASCII_WORD.match(key):
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(key) + r"(?![A-Za-z0-9])", re.I)
    else:
        pattern = re.compile(re.escape(key), re.I)
    _cache[key] = pattern
    return pattern


def matches_keywords(title, keywords):
    """标题命中任意关键词即返回 True。"""
    if not title or not keywords:
        return False
    for keyword in keywords:
        pattern = _pattern(keyword)
        if pattern and pattern.search(title):
            return True
    return False