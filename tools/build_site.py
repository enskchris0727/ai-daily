"""把静态页面和最新数据组装成可直接部署的 dist/ 目录。

用法：
    python tools/build_site.py
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
DATA = os.path.join(ROOT, "data", "feed.json")
DIST = os.path.join(ROOT, "dist")


def main():
    if not os.path.exists(DATA):
        print("找不到 data/feed.json，请先运行 python -m src.build_feed", file=sys.stderr)
        return 1

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)

    for name in sorted(os.listdir(WEB)):
        src = os.path.join(WEB, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DIST, name))

    shutil.copy2(DATA, os.path.join(DIST, "feed.json"))

    with open(DATA, "r", encoding="utf-8") as fh:
        feed = json.load(fh)
    print("dist/ 已生成：%d 个条目，更新于 %s" % (feed["item_count"], feed["generated_at"]))
    print("  文件：" + ", ".join(sorted(os.listdir(DIST))))
    return 0


if __name__ == "__main__":
    sys.exit(main())