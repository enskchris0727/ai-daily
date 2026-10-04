"""主流程：抓取全部来源 -> 标准化 -> 去重 -> 合并上一版 -> 写出 feed.json。

用法示例：
    python -m src.build_feed --out data/feed.json
    python -m src.build_feed --previous https://example.pages.dev/feed.json
    python -m src.build_feed --only openai,qbitai     # 只跑指定来源，便于调试
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import yaml

from . import collectors, fetcher
from .dedupe import dedupe
from .keywords import matches_keywords
from .normalize import normalize_item, strip_title_prefixes

WINDOW_DAYS = 7
MAX_ITEMS = 500


def load_sources(path):
    """读取来源清单，过滤掉 enabled=false 的条目。"""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sources = data.get("sources") or []
    return [s for s in sources if s.get("enabled", True)]


def load_previous(where):
    """读取上一版 feed.json（本地路径或线上地址）。没有则返回空列表。"""
    if not where:
        return []
    try:
        if where.startswith("http"):
            resp = fetcher.fetch(where, retries=1)
            payload = json.loads(fetcher.decode(resp))
        else:
            if not os.path.exists(where):
                return []
            with open(where, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        return payload.get("items") or []
    except Exception as exc:  # noqa: BLE001 - 上一版读不到不应影响本次产出
        print("  ! 读取上一版失败，忽略：%s" % str(exc)[:120])
        return []


def collect_one(source, fetched_at):
    """抓取单个来源并标准化，返回 (来源, 条目列表, 错误信息)。"""
    try:
        raw_items = collectors.collect(source)
        keywords = source.get("filter_keywords")
        normalized = []
        for raw in raw_items:
            item = normalize_item(raw, source, fetched_at)
            if not item:
                continue
            item["title"] = strip_title_prefixes(item["title"], source.get("strip_title_prefixes"))
            # 综合科技媒体需要按关键词筛出 AI 相关内容
            if keywords and not matches_keywords(item["title"], keywords):
                continue
            normalized.append(item)

        # 有些来源（尤其网页抓取的）会一次列出全部历史文章且不提供日期，
        # 会导致陈年旧帖挤进信息流。这类来源按配置只取列表最前面的 N 条。
        limit = source.get("max_items")
        if limit and len(normalized) > limit:
            normalized = normalized[:limit]

        if not normalized:
            return source, [], "抓到了内容但没有可用条目"
        return source, normalized, None
    except Exception as exc:  # noqa: BLE001 - 单源失败必须隔离，不能影响其他来源
        return source, [], "%s: %s" % (type(exc).__name__, str(exc)[:140])


def build(sources, previous, now):
    """执行一次完整构建，返回 feed 字典与统计信息。"""
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(collect_one, s, now) for s in sources]
        outcomes = [f.result() for f in futures]

    items = list(previous)
    ok, failed = [], []
    for source, source_items, error in outcomes:
        if error:
            failed.append({"source_id": source["id"], "name": source["name"], "error": error})
            print("  FAIL  %-24s %s" % (source["name"], error))
        else:
            ok.append(source["id"])
            items.extend(source_items)
            print("  OK    %-24s %d 条" % (source["name"], len(source_items)))

    merged = dedupe(items)

    cutoff = now - timedelta(days=WINDOW_DAYS)
    kept = []
    for item in merged:
        try:
            published = datetime.fromisoformat(item["published_at"])
        except (KeyError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published >= cutoff:
            kept.append(item)

    # 有真实发布时间的排前面；时间靠抓取时间兜底的排后面，避免假最新抢占顶部
    dated = [i for i in kept if not i.get("date_estimated")]
    estimated = [i for i in kept if i.get("date_estimated")]
    dated.sort(key=lambda i: i["published_at"], reverse=True)
    estimated.sort(key=lambda i: i["published_at"], reverse=True)
    kept = (dated + estimated)[:MAX_ITEMS]

    feed = {
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "window_days": WINDOW_DAYS,
        "item_count": len(kept),
        "sources_ok": len(ok),
        "sources_failed": [f["name"] for f in failed],
        "failures": failed,
        "items": kept,
    }
    return feed


def main(argv=None):
    parser = argparse.ArgumentParser(description="构建 AI 每日前沿的数据文件")
    parser.add_argument("--sources", default="sources.yaml", help="来源清单路径")
    parser.add_argument("--out", default="data/feed.json", help="输出文件路径")
    parser.add_argument("--previous", default=None, help="上一版 feed.json（路径或网址）")
    parser.add_argument("--only", default=None, help="只跑 id 含这些关键字的来源，逗号分隔")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    sources = load_sources(args.sources)
    if args.only:
        patterns = [p.strip() for p in args.only.split(",") if p.strip()]
        sources = [s for s in sources if any(p in s["id"] for p in patterns)]

    print("开始构建：%d 个来源，%s" % (len(sources), now.isoformat()))
    previous = load_previous(args.previous)
    if previous:
        print("  载入上一版 %d 条" % len(previous))

    feed = build(sources, previous, now)

    print("\n结果：成功 %d 个来源，失败 %d 个，共 %d 条"
          % (feed["sources_ok"], len(feed["failures"]), feed["item_count"]))

    if feed["item_count"] == 0:
        print("！本次没有产出任何条目，按设计不覆盖已有数据", file=sys.stderr)
        return 1

    if args.dry_run:
        print("（dry-run：未写入文件）")
        return 0

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(feed, fh, ensure_ascii=False, indent=2)
    print("已写入 %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())