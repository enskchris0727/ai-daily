"""字段标准化：URL 规范化、稳定 id、时间解析、文本清洗。"""

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 这些查询参数只跟来源统计有关，去掉后同一个页面才能归为同一条
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "spm",
}

_WS = re.compile(r"\s+")

# 标题末尾常常粘着发布日期，展示时要剥掉
_TRAILING_DATE = re.compile(
    r"[\s\-|,]*20\d{2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}\s*$"
)

_LEADING_DATE = re.compile(
    r"^[\s\-|,·]*(?:[A-Za-z]{3,9}\s+\d{1,2},\s*20\d{2}|20\d{2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2})\s*[-|,·]?\s*"
)


def clean_title(value):
    """清洗标题，并去掉首尾粘连的发布日期。"""
    text = clean_text(value)
    previous = None
    while previous != text:
        previous = text
        text = _TRAILING_DATE.sub("", text)
        text = _LEADING_DATE.sub("", text)
        text = text.strip(" -|,·")
    return text


def canonical_url(url):
    """去掉跟踪参数、统一大小写与末尾斜杠，得到规范 URL。"""
    if not url:
        return ""
    url = url.strip()
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def item_id(url):
    """由规范 URL 生成稳定的条目 id。"""
    return "sha1:" + hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()


def clean_text(value):
    """去 HTML 实体、折叠空白、去首尾空格。"""
    if not value:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return _WS.sub(" ", text).strip()


_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%d %B %Y",
    "%B %d, %Y",
)


def parse_date(value):
    """把各种格式的时间字符串解析成带时区的 datetime，失败返回 None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    text = str(value).strip()
    if not text:
        return None

    try:
        dt = parsedate_to_datetime(text)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass

    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def normalize_item(raw, source, fetched_at):
    """把各收集器产出的原始记录，统一成 feed.json 的条目结构。

    缺少标题或链接的记录会被丢弃（返回 None）。
    """
    url = (raw.get("url") or "").strip()
    title = clean_title(raw.get("title"))
    if not url or not title:
        return None
    if not url.startswith("http"):
        return None

    published = parse_date(raw.get("published_at"))
    date_estimated = published is None
    if published is None:
        published = fetched_at

    return {
        "id": item_id(url),
        "title": title,
        "url": url,
        "source": source["name"],
        "source_id": source["id"],
        "category": source["category"],
        "lang": source.get("lang", "en"),
        "published_at": published.astimezone(timezone.utc).isoformat(),
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(),
        "date_estimated": date_estimated,
    }

def strip_title_prefixes(title, prefixes):
    """按来源配置剥掉标题开头的栏目名（例如 Anthropic 列表页的 Announcements）。"""
    if not title or not prefixes:
        return title
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if title.startswith(prefix + " ") and len(title) > len(prefix) + 15:
                title = title[len(prefix) + 1:].strip()
                changed = True
    return title
