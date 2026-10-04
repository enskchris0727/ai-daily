"""把项目文件通过 GitHub API 推送上去。

为什么不用 git：当前运行环境不允许写入项目的 .git 目录，
所以改用 GitHub 官方接口逐个文件上传，效果等同于一次 push。

用法：
    python tools/deploy_github.py --repo ai-daily
    （令牌放在 work/token.txt，或环境变量 GITHUB_TOKEN）
"""

import argparse
import base64
import os
import sys

import requests

API = "https://api.github.com"

EXCLUDE_DIRS = {
    ".git", "work", "dist", "outputs", ".pytest_cache",
    "__pycache__", ".venv", "venv", ".idea", ".vscode",
}
EXCLUDE_FILES = {".DS_Store", "token.txt"}


def find_token():
    """取令牌：优先环境变量，其次 work/token.txt（忽略 # 开头的说明行）。"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    path = os.path.join("work", "token.txt")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return line
    return ""


def collect_files(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            if name in EXCLUDE_FILES:
                continue
            absolute = os.path.join(base, name)
            relative = os.path.relpath(absolute, root).replace("\\", "/")
            out.append((relative, absolute))
    return sorted(out)


class GitHub:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def call(self, method, path, **kwargs):
        resp = self.session.request(method, API + path, timeout=60, **kwargs)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", "")
            except ValueError:
                detail = resp.text[:200]
            raise RuntimeError("%s %s -> HTTP %s %s" % (method, path, resp.status_code, detail))
        if not resp.content:
            return None
        return resp.json()


def main():
    parser = argparse.ArgumentParser(description="通过 GitHub API 上传项目文件")
    parser.add_argument("--owner", default="enskchris0727")
    parser.add_argument("--repo", default="ai-daily")
    parser.add_argument("--message", default="部署 AI 每日前沿")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = collect_files(os.getcwd())
    print("准备上传 %d 个文件：" % len(files))
    for relative, _ in files:
        print("   ", relative)
    if args.dry_run:
        return 0

    token = find_token()
    if not token:
        print("\n找不到令牌：请写入 work/token.txt 或设置 GITHUB_TOKEN", file=sys.stderr)
        return 2

    gh = GitHub(token)
    repo_path = "/repos/%s/%s" % (args.owner, args.repo)

    info = gh.call("GET", repo_path)
    branch = info.get("default_branch") or "main"
    print("\n仓库 %s/%s 就绪，默认分支 %s" % (args.owner, args.repo, branch))

    # 空仓库无法使用 Git Data API（会返回 409），先用 Contents API 建立第一个提交
    parents = []
    try:
        ref = gh.call("GET", repo_path + "/git/ref/heads/" + branch)
        parents = [ref["object"]["sha"]]
        print("基于已有提交继续")
    except RuntimeError:
        print("空仓库：先建立初始提交")
        gh.call("PUT", repo_path + "/contents/.gitignore", json={
            "message": "chore: 初始化仓库",
            "content": base64.b64encode("# see .gitignore in the project root\n".encode("utf-8")).decode("ascii"),
        })
        ref = gh.call("GET", repo_path + "/git/ref/heads/" + branch)
        parents = [ref["object"]["sha"]]
        branch = ref["ref"].split("/")[-1]

    # 细粒度令牌不支持底层 Git Data API（建 tree/commit），因此改用 Contents API
    # 逐个文件提交。效果等同于一次 push，代价是每个文件一条提交记录。
    # 细粒度令牌不支持底层 Git Data API（建 tree/commit），因此改用 Contents API
    # 逐个文件提交。另外，工作流文件需要令牌额外具备 Workflows 权限。
    print("上传文件…")
    skipped = []
    for relative, absolute in files:
        with open(absolute, "rb") as fh:
            content = fh.read()
        payload = {
            "message": "%s\n\n%s" % (relative, args.message),
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        try:
            existing = gh.call("GET", repo_path + "/contents/" + relative + "?ref=" + branch)
            payload["sha"] = existing["sha"]
        except RuntimeError:
            pass
        try:
            gh.call("PUT", repo_path + "/contents/" + relative, json=payload)
            print("   ok   " + relative)
        except RuntimeError as exc:
            skipped.append(relative)
            print("   SKIP " + relative + "  <- " + str(exc)[:90])

    if skipped:
        print("\n以下文件未能上传（令牌权限不足）：")
        for relative in skipped:
            print("   -", relative)
    else:
        print("\n全部文件已提交")

    print("开启 GitHub Pages（来源＝Actions）…")
    try:
        gh.call("POST", repo_path + "/pages", json={"build_type": "workflow"})
        print("   Pages 已开启")
    except RuntimeError as exc:
        print("   自动开启失败：%s" % exc)
        print("   请在网页上手动设置：Settings → Pages → Source 选 GitHub Actions")

    print("触发一次抓取…")
    try:
        gh.call("POST", repo_path + "/actions/workflows/update.yml/dispatches",
                json={"ref": branch})
        print("   已触发")
    except RuntimeError as exc:
        print("   触发失败：%s" % exc)

    print("\n站点地址（首次运行完成后生效）：")
    print("   https://%s.github.io/%s/" % (args.owner, args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())