"""去重与合并规则的测试。"""

from src.dedupe import dedupe, merge_duplicate


def _item(url, title, published, estimated=False):
    return {
        "id": "sha1:" + url,
        "title": title,
        "url": url,
        "source": "S",
        "source_id": "s",
        "category": "lab",
        "lang": "en",
        "published_at": published,
        "fetched_at": "2026-10-04T12:00:00+00:00",
        "date_estimated": estimated,
    }


def test_merge_uses_fresh_title():
    """解析规则改进后，老条目也要跟着更新，不能被旧数据顶掉。"""
    old = _item("https://a.com/1", "dirty title 2026/03/31", "2026-10-01T00:00:00+00:00")
    fresh = _item("https://a.com/1", "clean title", "2026-10-01T00:00:00+00:00")
    assert merge_duplicate(old, fresh)["title"] == "clean title"


def test_merge_keeps_earliest_real_date():
    old = _item("https://a.com/1", "T", "2026-10-01T00:00:00+00:00")
    fresh = _item("https://a.com/1", "T", "2026-10-03T00:00:00+00:00")
    merged = merge_duplicate(old, fresh)
    assert merged["published_at"] == "2026-10-01T00:00:00+00:00"
    assert merged["date_estimated"] is False


def test_merge_prefers_real_over_estimated():
    old = _item("https://a.com/1", "T", "2026-10-01T00:00:00+00:00", estimated=False)
    fresh = _item("https://a.com/1", "T", "2026-10-05T00:00:00+00:00", estimated=True)
    merged = merge_duplicate(old, fresh)
    assert merged["published_at"] == "2026-10-01T00:00:00+00:00"
    assert merged["date_estimated"] is False


def test_dedupe_by_id():
    items = [
        _item("https://a.com/1", "T", "2026-10-01T00:00:00+00:00"),
        _item("https://a.com/1", "T", "2026-10-01T00:00:00+00:00"),
    ]
    assert len(dedupe(items)) == 1


def test_dedupe_by_title():
    items = [
        _item("https://a.com/1", "same story", "2026-10-01T00:00:00+00:00"),
        _item("https://b.com/2", "same story", "2026-10-01T00:00:00+00:00"),
    ]
    assert len(dedupe(items)) == 1