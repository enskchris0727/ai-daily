"""统一的 HTTP 抓取层：统一超时、重试、请求头与编码处理。

所有联网请求都必须经过这里，方便统一控制行为与排查问题。
"""

import time

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept-Language": "en,zh-CN;q=0.9,zh;q=0.8",
}

TIMEOUT = 25
RETRIES = 2


class FetchError(Exception):
    """抓取失败（网络错误或 HTTP 错误状态）。"""


def fetch(url, timeout=TIMEOUT, retries=RETRIES, headers=None):
    """请求一个地址，返回 requests.Response。

    失败时按退避策略重试 retries 次，最终仍失败则抛 FetchError。
    """
    merged = dict(DEFAULT_HEADERS)
    if headers:
        merged.update(headers)

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=merged, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 400:
                raise FetchError("HTTP %s" % resp.status_code)
            return resp
        except Exception as exc:  # noqa: BLE001 - 需要把各种网络异常统一成 FetchError
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    raise FetchError("%s: %s" % (type(last_error).__name__, str(last_error)[:160]))


def decode(resp):
    """把响应内容解码成文本，尽量不产生乱码。"""
    body = resp.content
    candidates = []
    if resp.encoding:
        candidates.append(resp.encoding)
    candidates.extend(["utf-8", "gbk", "gb18030", "latin-1"])
    for enc in candidates:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def fetch_text(url, **kwargs):
    """抓取并解码为文本。"""
    return decode(fetch(url, **kwargs))