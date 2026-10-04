"""去重：同一条内容可能来自多个来源，或者同一来源给出多个地址。"""

import re

from .normalize import canonical_url

_PUNCT = re.compile(r"[\s\-_·—–|:：,，.。!！?？\"'“”‘’()（）\[\]【】]+")


def _title_key(title):
    """把标题压成用于比较的键（去掉标点与大小写差异）。"""
    return _PUNCT.sub("", (title or "").lower())


def merge_duplicate(existing, fresh):
    """同一条内容出现两次时的合并规则。

    背景：每次运行都会把上一版数据与本次抓取结果一起合并。
    如果让旧记录胜出，解析规则的改进就永远不会体现在老条目上。

    规则：
      - 显示字段（标题、链接等）用本次抓取的新结果
      - 发布时间保留更早的那个，优先保留真实时间而非抓取时间兜底值
    """
    merged = dict(fresh)
    old_date = existing.get("published_at")
    new_date = fresh.get("published_at")
    old_real = existing.get("date_estimated") is False
    new_real = fresh.get("date_estimated") is False

    real_dates = []
    if old_date and old_real:
        real_dates.append(old_date)
    if new_date and new_real:
        real_dates.append(new_date)

    if real_dates:
        merged["published_at"] = min(real_dates)
        merged["date_estimated"] = False
    elif old_date and new_date:
        merged["published_at"] = min(old_date, new_date)
        merged["date_estimated"] = (existing.get("date_estimated", True)
                                    and fresh.get("date_estimated", True))
    return merged


def dedupe(items):
    """按规范 URL 与标题两轮去重，返回去重后的列表。"""
    by_id = {}
    for item in items:
        key = item["id"]
        by_id[key] = item if key not in by_id else merge_duplicate(by_id[key], item)

    by_title = {}
    for item in by_id.values():
        key = _title_key(item["title"])
        if not key:
            key = item["id"]
        by_title[key] = item if key not in by_title else merge_duplicate(by_title[key], item)

    return list(by_title.values())
