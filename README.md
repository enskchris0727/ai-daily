# AI 每日前沿

把全球 AI 公司 / 实验室的一手动态、最新论文、以及中文 AI 媒体的报道，
聚合成**一个按时间倒序的信息流页面**，每条都能点开跳转原文。

- 网址：https://enskchris0727.github.io/ai-daily/
- 更新：每天北京时间 **08:00 / 13:00 / 20:00** 自动运行
- 成本：0 元（GitHub Actions + GitHub Pages 免费额度）
- 无账号、无后端、无数据库；已读与收藏只存在你自己的浏览器里

---

## 它是怎么工作的

```
GitHub Actions（每天 3 次，跑在海外服务器上）
      │  ① 读取 sources.yaml，并发抓取各来源
      │  ② 统一字段 → 合并上一版 → 去重 → 按时间排序
      │  ③ 截取最近 7 天、最多 500 条，写出 feed.json
      ▼
   静态站点（web/ 页面 + data/feed.json）
      ▼
GitHub Pages → 电脑 / 手机 / 平板打开
```

**为什么抓取必须跑在 GitHub 的服务器上**：Hugging Face、Google Research、
Meta AI、Mistral、xAI 等站点在国内网络不可直接访问。GitHub Actions 运行在
海外，能正常抓到这些源。

---

## 怎么手动更新一次

打开 https://github.com/enskchris0727/ai-daily/actions/workflows/update.yml
→ 右侧 **Run workflow** → 绿色 **Run workflow**。

约 1-2 分钟后刷新网页就能看到新内容。

---

## 怎么增删来源

编辑仓库里的 `sources.yaml`，一个来源一段：

```yaml
  - id: openai            # 稳定标识，不要随意改（影响去重与已读状态）
    name: OpenAI          # 页面上显示的名字
    category: lab         # lab（公司/实验室）| paper（论文）| cn-media（中文媒体）
    lang: en              # en | zh
    type: rss             # rss | json | html
    url: https://openai.com/news/rss.xml
    homepage: https://openai.com/news/
    enabled: true         # 改成 false 即可临时停用
```

可选字段：

| 字段 | 作用 |
|---|---|
| `max_items` | 只取列表最前面的 N 条（用于不提供日期、会列出全部历史文章的来源） |
| `filter_keywords` | 只保留标题命中这些关键词的条目（用于综合科技媒体） |
| `strip_title_prefixes` | 剥掉标题开头粘连的栏目名 |
| `fallbacks` | 主地址失效时依次尝试的备用地址 |

改完提交，push 会自动触发一次重建。

### 新增来源前先验证

```bash
python tools/probe_sources.py                          # 探测全部候选
python tools/probe_sources.py --filter openai,qbitai   # 只探测指定来源
```

结果写入 `work/probe_result.json` 与 `work/probe_result.md`。

---

## 本地运行

```bash
pip install -r requirements.txt

# 抓取并生成数据
python -m src.build_feed --out data/feed.json --previous https://enskchris0727.github.io/ai-daily/feed.json

# 组装静态站点到 dist/
python tools/build_site.py

# 本地预览
python -m http.server 8765 --directory dist
# 浏览器打开 http://localhost:8765/
```

调试单个来源：

```bash
python -m src.build_feed --only openai,qbitai --dry-run
```

---

## 测试

```bash
python -m pytest tests -q
```

覆盖：字段标准化、标题清洗、URL 规范化、去重与跨版本合并、来源清单合法性。

---

## 目录结构

```
src/                    抓取与整理（Python）
  collectors/           按来源类型分的收集器：rss / html / json
  normalize.py          字段标准化、URL 规范化、id 生成
  dedupe.py             去重与跨版本合并规则
  keywords.py           关键词过滤
  build_feed.py         主流程
web/                    静态前端（原生 HTML/CSS/JS，无构建步骤）
data/feed.json          生成的数据（也是线上的数据文件）
sources.yaml            来源清单
tools/                  探测与部署脚本
tests/                  单元测试
docs/                   设计文档与实测报告
```

---

## 已知限制

- **部分来源不提供发布时间**：这类条目的时间用抓取时间兜底，页面显示"时间未知"，
  并排在真实时间的条目之后。相关来源已用 `max_items` 限制条数，避免旧文章堆积。
- **Meta AI 官方博客有反爬**：主地址返回 400，目前回退到 Meta 工程博客。
- **机器之心 / 新智元已移除**：前者官网改为数据服务落地页，后者域名失效。
- **github.io 在国内访问需要加速器**。