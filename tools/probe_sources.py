"""来源探测脚本。

逐个请求候选来源地址，判断类型（RSS/Atom、JSON、HTML），
输出每个来源是否可用、能取到多少条、最新一条的时间。

用途：
  1. 实施阶段确定最终来源清单
  2. 以后新增来源时，先用它验证再写进 sources.yaml

用法：
  python tools/probe_sources.py
输出：
  work/probe_result.json   机器可读结果
  work/probe_result.md     便于阅读的表格
"""

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

TIMEOUT = 20
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en,zh-CN;q=0.9,zh;q=0.8"}

ARXIV = (
    "http://export.arxiv.org/api/query"
    "?search_query=cat:{cat}&sortBy=submittedDate&sortOrder=descending&max_results=30"
)

SOURCES = [
    # ---------------- A 类：AI 公司 / 实验室 ----------------
    {"id": "openai", "name": "OpenAI", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://openai.com/news/rss.xml"),
                    ("html", "https://openai.com/news/")]},
    {"id": "anthropic", "name": "Anthropic", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://www.anthropic.com/rss.xml"),
                    ("html", "https://www.anthropic.com/news")]},
    {"id": "deepmind", "name": "Google DeepMind", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://deepmind.google/blog/rss.xml"),
                    ("html", "https://deepmind.google/discover/blog/")]},
    {"id": "google-research", "name": "Google Research", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://research.google/blog/rss/"),
                    ("rss", "http://feeds.feedburner.com/blogspot/gJZg")]},
    {"id": "meta-ai", "name": "Meta AI", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://ai.meta.com/blog/rss/"),
                    ("html", "https://ai.meta.com/blog/")]},
    {"id": "msr", "name": "Microsoft Research", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://www.microsoft.com/en-us/research/feed/")]},
    {"id": "nvidia", "name": "NVIDIA AI", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://blogs.nvidia.com/feed/"),
                    ("rss", "https://developer.nvidia.com/blog/feed/")]},
    {"id": "apple-ml", "name": "Apple ML Research", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://machinelearning.apple.com/rss.xml")]},
    {"id": "aws-ml", "name": "AWS Machine Learning", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://aws.amazon.com/blogs/machine-learning/feed/")]},
    {"id": "ibm-research", "name": "IBM Research", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://research.ibm.com/blog/rss"),
                    ("rss", "https://www.ibm.com/blogs/research/feed/")]},
    {"id": "mistral", "name": "Mistral AI", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://mistral.ai/feed.xml"),
                    ("html", "https://mistral.ai/news/")]},
    {"id": "xai", "name": "xAI", "category": "lab", "lang": "en",
     "candidates": [("html", "https://x.ai/blog")]},
    {"id": "cohere", "name": "Cohere", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://cohere.com/blog/rss.xml"),
                    ("html", "https://cohere.com/blog")]},
    {"id": "stability", "name": "Stability AI", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://stability.ai/news/rss.xml"),
                    ("html", "https://stability.ai/news")]},
    {"id": "huggingface", "name": "Hugging Face", "category": "lab", "lang": "en",
     "candidates": [("rss", "https://huggingface.co/blog/feed.xml")]},
    {"id": "deepseek", "name": "DeepSeek", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://api-docs.deepseek.com/news/"),
                    ("html", "https://www.deepseek.com/")]},
    {"id": "qwen", "name": "阿里通义 Qwen", "category": "lab", "lang": "zh",
     "candidates": [("rss", "https://qwenlm.github.io/blog/index.xml"),
                    ("html", "https://qwenlm.github.io/blog/")]},
    {"id": "bytedance-seed", "name": "字节 Seed", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://seed.bytedance.com/blog"),
                    ("html", "https://seed.bytedance.com/en/blog")]},
    {"id": "moonshot", "name": "月之暗面", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://www.moonshot.cn/"),
                    ("html", "https://moonshotai.github.io/")]},
    {"id": "zhipu", "name": "智谱 AI", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://www.zhipuai.cn/zh/news"),
                    ("html", "https://www.zhipuai.cn/")]},
    {"id": "minimax", "name": "MiniMax", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://www.minimax.io/news"),
                    ("html", "https://www.minimaxi.com/news")]},

    # ---------------- B 类：论文 ----------------
    {"id": "arxiv-ai", "name": "arXiv cs.AI", "category": "paper", "lang": "en",
     "candidates": [("rss", ARXIV.format(cat="cs.AI"))]},
    {"id": "arxiv-lg", "name": "arXiv cs.LG", "category": "paper", "lang": "en",
     "candidates": [("rss", ARXIV.format(cat="cs.LG"))]},
    {"id": "arxiv-cl", "name": "arXiv cs.CL", "category": "paper", "lang": "en",
     "candidates": [("rss", ARXIV.format(cat="cs.CL"))]},
    {"id": "hf-papers", "name": "Hugging Face Daily Papers", "category": "paper", "lang": "en",
     "candidates": [("json", "https://huggingface.co/api/daily_papers?limit=30"),
                    ("html", "https://huggingface.co/papers")]},

    # ---------------- C 类：中文媒体 ----------------
    {"id": "jiqizhixin", "name": "机器之心", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.jiqizhixin.com/rss"),
                    ("html", "https://www.jiqizhixin.com/")]},
    {"id": "qbitai", "name": "量子位", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.qbitai.com/feed"),
                    ("html", "https://www.qbitai.com/")]},
    {"id": "ai-era", "name": "新智元", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.ai-era.cn/feed"),
                    ("html", "https://www.ai-era.cn/")]},
    {"id": "zhidx", "name": "智东西", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://zhidx.com/feed"),
                    ("html", "https://zhidx.com/")]},
    {"id": "leiphone", "name": "雷锋网", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.leiphone.com/feed"),
                    ("html", "https://www.leiphone.com/")]},

    # ---------------- C 类补充候选（扩测用） ----------------
    {"id": "tmtpost", "name": "钛媒体", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.tmtpost.com/feed"),
                    ("html", "https://www.tmtpost.com/")]},
    {"id": "36kr", "name": "36氪", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://36kr.com/feed"), ("html", "https://36kr.com/")]},
    {"id": "infoq-cn", "name": "InfoQ 中文站", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.infoq.cn/feed"), ("html", "https://www.infoq.cn/")]},
    {"id": "ifanr", "name": "爱范儿", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.ifanr.com/feed"),
                    ("html", "https://www.ifanr.com/")]},
    {"id": "huxiu", "name": "虎嗅", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.huxiu.com/rss/0.xml"),
                    ("html", "https://www.huxiu.com/")]},
    {"id": "pingwest", "name": "品玩", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.pingwest.com/feed"),
                    ("html", "https://www.pingwest.com/")]},
    {"id": "baai-hub", "name": "智源社区", "category": "cn-media", "lang": "zh",
     "candidates": [("html", "https://hub.baai.ac.cn/")]},
    {"id": "leikeji", "name": "雷科技", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.leikeji.com/feed"),
                    ("html", "https://www.leikeji.com/")]},
    {"id": "ai-front", "name": "AI 前线", "category": "cn-media", "lang": "zh",
     "candidates": [("html", "https://www.infoq.cn/topic/AI")]},
    {"id": "jiqi-zhineng", "name": "机器之能", "category": "cn-media", "lang": "zh",
     "candidates": [("html", "https://www.jiqizhixin.com/rss")]},
    {"id": "qbitai-alt", "name": "量子位(备用地址)", "category": "cn-media", "lang": "zh",
     "candidates": [("rss", "https://www.qbitai.com/feed/atom"),
                    ("html", "https://www.qbitai.com/")]},

    # ---------------- 中国 AI 公司 / 研究机构官方源（扩测用） ----------------
    {"id": "msra", "name": "微软亚洲研究院", "category": "lab", "lang": "zh",
     "candidates": [("rss", "https://www.msra.cn/feed"),
                    ("html", "https://www.msra.cn/zh-cn/news")]},
    {"id": "tencent-ailab", "name": "腾讯 AI Lab", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://ai.tencent.com/ailab/zh/news/")]},
    {"id": "sensetime", "name": "商汤科技", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://www.sensetime.com/cn/news")]},
    {"id": "damo", "name": "阿里达摩院", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://damo.alibaba.com/")]},
    {"id": "iflytek", "name": "科大讯飞", "category": "lab", "lang": "zh",
     "candidates": [("html", "https://www.iflytek.com/")]},
    {"id": "paperweekly", "name": "PaperWeekly", "category": "paper", "lang": "zh",
     "candidates": [("html", "https://www.paperweekly.site/")]},
]


def _parse_date(value):
    """把各种格式的日期字符串尽量转成 aware datetime。"""
    if not value:
        return None
    value = str(value).strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[:len(datetime.now().strftime(fmt))] if False else value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _latest_of(dates):
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def try_rss(text):
    parsed = feedparser.parse(text)
    entries = parsed.entries or []
    dates = []
    for e in entries:
        for key in ("published_parsed", "updated_parsed"):
            t = e.get(key)
            if t:
                try:
                    dates.append(datetime(*t[:6], tzinfo=timezone.utc))
                    break
                except Exception:
                    pass
        else:
            dates.append(_parse_date(e.get("published") or e.get("updated")))
    if not entries:
        raise ValueError("解析成功但没有任何条目")
    return len(entries), _latest_of(dates)


def try_json(text):
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ("items", "data", "results", "papers"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON 结构不是列表")
    if not data:
        raise ValueError("JSON 列表为空")
    dates = []
    for item in data:
        if not isinstance(item, dict):
            continue
        for key in ("publishedAt", "published_at", "createdAt", "date", "published", "submittedAt"):
            if item.get(key):
                dates.append(_parse_date(item[key]))
                break
        else:
            paper = item.get("paper")
            if isinstance(paper, dict):
                dates.append(_parse_date(paper.get("publishedAt") or paper.get("publicationDate")))
    return len(data), _latest_of(dates)


def try_html(text):
    soup = BeautifulSoup(text, "html.parser")
    dates = []
    for tag in soup.find_all("time"):
        dates.append(_parse_date(tag.get("datetime") or tag.get_text(" ", strip=True)))
    links = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(20\d{2}|news|blog|article|post)/", href) or re.search(r"/\d{4}/\d{2}/", href):
            links += 1
    if links == 0 and not dates:
        raise ValueError("页面里没有找到文章列表特征")
    return max(links, len(dates)), _latest_of(dates)


def probe_candidate(method, url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    if resp.status_code >= 400:
        raise ValueError("HTTP %s" % resp.status_code)
    ctype = (resp.headers.get("Content-Type") or "").lower()
    body = resp.content
    if len(body) < 200:
        raise ValueError("响应内容过短（%d 字节）" % len(body))
    text = None
    for enc in (resp.encoding, "utf-8", "gbk", "latin-1"):
        if not enc:
            continue
        try:
            text = body.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        raise ValueError("无法解码响应内容")
    head = text.lstrip()[:400].lower()
    if "xml" in ctype or head.startswith("<?xml") or "<rss" in head or "<feed" in head:
        count, latest = try_rss(text)
        return {"kind": "rss", "count": count, "latest": latest}
    if "json" in ctype or head.startswith("{") or head.startswith("["):
        count, latest = try_json(text)
        return {"kind": "json", "count": count, "latest": latest}
    count, latest = try_html(text)
    return {"kind": "html", "count": count, "latest": latest}


def probe_source(src):
    rec = {
        "id": src["id"], "name": src["name"],
        "category": src["category"], "lang": src["lang"],
        "ok": False, "method": None, "url": None,
        "count": 0, "latest": None, "error": None,
    }
    errors = []
    for method, url in src["candidates"]:
        try:
            info = probe_candidate(method, url)
            rec.update({"ok": True, "method": info["kind"], "url": url,
                        "count": info["count"],
                        "latest": info["latest"].isoformat() if info["latest"] else None})
            return rec
        except Exception as exc:
            errors.append("%s %s -> %s: %s" % (method, url, type(exc).__name__, str(exc)[:110]))
    rec["error"] = " | ".join(errors)
    return rec


def main():
    only = None
    argv = sys.argv[1:]
    if "--filter" in argv:
        idx = argv.index("--filter")
        only = argv[idx + 1] if idx + 1 < len(argv) else None

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "work")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    if only:
        pats = [x.strip() for x in only.split(",") if x.strip()]
        targets = [s for s in SOURCES if any(p in s["id"] for p in pats)]
    else:
        targets = list(SOURCES)
    if only:
        print("只探测 id 含 %r 的来源，共 %d 个\n" % (only, len(targets)))

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for rec in pool.map(probe_source, targets):
            results.append(rec)
            flag = "OK  " if rec["ok"] else "FAIL"
            extra = ""
            if rec["ok"]:
                extra = "%-5s %3d 条  最新 %s" % (rec["method"], rec["count"], rec["latest"] or "未知")
            else:
                extra = (rec["error"] or "")[:150]
            print("%s  %-24s %s" % (flag, rec["name"], extra), flush=True)

    with open(os.path.join(out_dir, "probe_result.json"), "w", encoding="utf-8") as fh:
        json.dump({"probed_at": datetime.now(timezone.utc).isoformat(),
                   "results": results}, fh, ensure_ascii=False, indent=2)

    ok = [r for r in results if r["ok"]]
    lines = ["| 来源 | 分类 | 方式 | 状态 | 条目数 | 最新时间 |",
             "|---|---|---|---|---|---|"]
    cat_name = {"lab": "实验室", "paper": "论文", "cn-media": "中文媒体"}
    for r in results:
        if r["ok"]:
            latest = (r["latest"] or "未知")[:16].replace("T", " ")
            lines.append("| %s | %s | %s | ✅ 可用 | %d | %s |" % (
                r["name"], cat_name[r["category"]], r["method"], r["count"], latest))
        else:
            lines.append("| %s | %s | — | ❌ 不可用 | — | — |" % (
                r["name"], cat_name[r["category"]]))
    lines.append("")
    lines.append("可用 %d / 共 %d" % (len(ok), len(results)))
    md = "\n".join(lines)
    with open(os.path.join(out_dir, "probe_result.md"), "w", encoding="utf-8") as fh:
        fh.write(md)

    print("\n可用 %d / 共 %d" % (len(ok), len(results)))
    print("结果已写入 work/probe_result.json 与 work/probe_result.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())