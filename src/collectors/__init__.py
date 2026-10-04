"""收集器注册表：按来源的 type 字段选用对应实现。"""

from . import html_feed, json_feed, rss

COLLECTORS = {
    "rss": rss.collect,
    "json": json_feed.collect,
    "html": html_feed.collect,
}


def collect(source):
    """按来源类型抓取，返回原始条目列表。"""
    collector = COLLECTORS.get(source["type"])
    if collector is None:
        raise ValueError("未知的来源类型：%s" % source["type"])
    return collector(source)