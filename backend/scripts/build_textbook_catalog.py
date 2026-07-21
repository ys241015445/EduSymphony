"""一次性离线脚本：从 ChinaTextbook 仓库目录树生成静态教材目录 JSON。

仅抓取**目录结构与外链**（学段/学科/版本/年级册次/PDF 名 + GitHub 源链接），
**不下载 PDF、不提取正文**，规避版权风险。产物提交后运行时零网络依赖。

用法（backend 目录，需联网一次）：
    .\\venv\\Scripts\\python.exe scripts\\build_textbook_catalog.py
可选：设置环境变量 GITHUB_TOKEN 提升 API 限额。

来源：https://github.com/TapXWorld/ChinaTextbook （默认分支 master）
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

REPO = "TapXWorld/ChinaTextbook"
BRANCH = os.getenv("CHINATEXTBOOK_BRANCH", "master")
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "textbook_catalog.json"

# 顶层目录名 → 规范学段
_LEVELS = {"小学": "小学", "初中": "初中", "高中": "高中", "大学": "大学"}


def _tree() -> list[dict]:
    url = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=60) as c:
        r = c.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    if data.get("truncated"):
        print("WARNING: GitHub tree was truncated; catalog may be partial.", file=sys.stderr)
    return data.get("tree", [])


def _blob_url(path: str) -> str:
    from urllib.parse import quote
    return f"https://github.com/{REPO}/blob/{BRANCH}/{quote(path)}"


def _base_pdf(path: str) -> str | None:
    """归一化 PDF 路径：`x.pdf.1` → `x.pdf`；非 pdf 返回 None。"""
    if ".pdf." in path:  # 分片
        return path.split(".pdf.")[0] + ".pdf"
    if path.lower().endswith(".pdf"):
        return path
    return None


def main() -> None:
    tree = _tree()
    seen: set[str] = set()
    entries: list[dict] = []
    for node in tree:
        if node.get("type") not in ("blob",):
            continue
        path = node.get("path") or ""
        base = _base_pdf(path)
        if not base or base in seen:
            continue
        parts = base.split("/")
        if len(parts) < 2 or parts[0] not in _LEVELS:
            continue
        seen.add(base)
        level = _LEVELS[parts[0]]
        subject = parts[1] if len(parts) >= 2 else ""
        # 版本：第 3 段（若存在且不是文件名）
        publisher = parts[2] if len(parts) >= 4 else ""
        title = parts[-1][:-4]  # 去掉 .pdf
        # 年级/册次：优先取路径中的年级文件夹（更准），否则回退标题正则
        grade = ""
        for seg in parts[3:-1]:
            if re.search(r"年级|必修|全一?册|上册|下册", seg):
                grade = seg
                break
        if not grade:
            m = re.search(
                r"([一二三四五六七八九]|[1-9])\s*年级[上下]?册?|选择性必修.{0,4}册|必修.{0,4}册|上册|下册",
                title,
            )
            grade = m.group(0) if m else ""
        entries.append({
            "level": level,
            "subject": subject,
            "publisher": publisher,
            "grade": grade,
            "title": title,
            "url": _blob_url(base),
        })

    entries.sort(key=lambda e: (e["level"], e["subject"], e["publisher"], e["title"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"source": f"https://github.com/{REPO}", "branch": BRANCH,
                    "count": len(entries), "entries": entries},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} textbook entries -> {OUT}")


if __name__ == "__main__":
    main()
