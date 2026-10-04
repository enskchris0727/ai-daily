"""字段标准化相关的测试。"""

from datetime import datetime, timezone

from src.normalize import (
    canonical_url,
    clean_title,
    item_id,
    normalize_item,
    parse_date,
    strip_title_prefixes,
)

FETCHED = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def test_canonical_url():
    a = canonical_url("https://www.example.com/post/1/?utm_source=x&ref=y")
    b = canonical_url("https://example.com/post/1")
    assert a == b


def test_item_id_stable():
    u1 = "https://example.com/a?utm_source=twitter"
    u2 = "https://www.example.com/a/"
    assert item_id(u1) == item_id(u2)


def test_clean_title_trailing_date():
    assert clean_title("某公司发布新模型 2026/03/31") == "某公司发布新模型"


def test_strip_title_prefixes():
    """栏目名剥离是按来源配置的，不放在通用清洗里。"""
    raw = "Announcements Anthropic invests $100 million in AI talent"
    out = strip_title_prefixes(raw, ["Announcements", "Science"])
    assert out == "Anthropic invests $100 million in AI talent"


def test_strip_title_prefixes_leaves_other_titles_alone():
    raw = "Research directions we are excited about this year"
    assert strip_title_prefixes(raw, ["Announcements"]) == raw


def test_clean_title_middle_en_date():
    raw = "Grok 4.7 Sep 21, 2026 Introducing Grok 4.7"
    assert clean_title(raw) == "Grok 4.7 Introducing Grok 4.7"


def test_parse_date_formats():
    assert parse_date("2026-10-04T08:00:00Z") is not None
    assert parse_date("2026-10-04") is not None
    assert parse_date("Sat, 04 Oct 2026 08:00:00 GMT") is not None
    assert parse_date("not a date") is None


def test_normalize_drops_incomplete():
    source = {"id": "s", "name": "S", "category": "lab", "lang": "en"}
    assert normalize_item({"title": "only title"}, source, FETCHED) is None
    assert normalize_item({"url": "https://a.com/x"}, source, FETCHED) is None


def test_normalize_marks_estimated_date():
    source = {"id": "s", "name": "S", "category": "lab", "lang": "en"}
    item = normalize_item({"title": "a long enough title", "url": "https://a.com/x"}, source, FETCHED)
    assert item["date_estimated"] is True
    assert item["published_at"] == FETCHED.isoformat()

    item2 = normalize_item(
        {"title": "a long enough title", "url": "https://a.com/y", "published_at": "2026-10-01"},
        source, FETCHED)
    assert item2["date_estimated"] is False