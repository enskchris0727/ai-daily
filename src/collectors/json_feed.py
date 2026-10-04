"""JSON 接口收集器。目前用于 Hugging Face Daily Papers。"""

import json

from .. import fetcher


def _pick_date(node):
    for key in ("publishedAt", "published_at", "createdAt", "date", "submittedAt"):
        if node.get(key):
            return node[key]
    return None


def collect(source):
    resp = fetcher.fetch(source["url"])
    data = json.loads(fetcher.decode(resp))

    if isinstance(data, dict):
        for key in ("items", "data", "results", "papers"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list) or not data:
        raise ValueError("JSON 接口没有返回有效列表")

    items = []
    for node in data:
        if not isinstance(node, dict):
            continue
        paper = node.get("paper") if isinstance(node.get("paper"), dict) else node
        title = paper.get("title") or paper.get("name") or node.get("title")
        url = paper.get("url")
        if not url:
            paper_id = paper.get("id") or node.get("id")
            if paper_id:
                url = "https://huggingface.co/papers/%s" % paper_id
        items.append({
            "title": title,
            "url": url,
            "published_at": _pick_date(node) or _pick_date(paper),
        })
    return items