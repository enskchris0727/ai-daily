"""收集器注册表：按来源的 type 字段选用对应实现。"""

from . import html_feed, json_feed, rss

COLLECTORS = {
    "rss": rss.collect,
    "json": json_feed.collect,
    "html": html_feed.collect,
}


def collect(source):
    """按来源抓取，返回原始条目列表。

    支持候选链：先试来源自己的地址，再按顺序试 fallbacks，
    取第一个能拿到内容的。用于主地址失效时自动降级。
    """
    attempts = [source] + list(source.get("fallbacks") or [])
    errors = []
    for candidate in attempts:
        merged = dict(source)
        merged.update(candidate)
        collector = COLLECTORS.get(merged["type"])
        if collector is None:
            errors.append("未知类型 %s" % merged["type"])
            continue
        try:
            items = collector(merged)
        except Exception as exc:
            errors.append("%s %s -> %s" % (merged["type"], merged["url"], str(exc)[:70]))
            continue
        if items:
            return items
        errors.append("%s %s -> 没有条目" % (merged["type"], merged["url"]))
    raise ValueError("所有候选地址都失败： " + " | ".join(errors))