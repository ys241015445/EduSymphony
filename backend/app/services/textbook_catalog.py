"""教材目录服务：加载 ChinaTextbook 静态目录 JSON，提供级联筛选。

仅元数据（学段/学科/版本/年级册次/标题 + 源外链），不含 PDF/正文。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DATA = Path(__file__).resolve().parent.parent / "data" / "textbook_catalog.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8"))
    except Exception:
        return {"source": "", "branch": "", "count": 0, "entries": []}


def _entries() -> list[dict]:
    return _load().get("entries", [])


def _uniq_sorted(vals) -> list[str]:
    return sorted({v for v in vals if v})


def catalog(level: Optional[str] = None, subject: Optional[str] = None,
            publisher: Optional[str] = None) -> dict:
    """返回级联可选项 + 命中的教材册次列表。

    - levels：全部学段
    - subjects：给定 level 下的学科
    - publishers：给定 level+subject 下的版本
    - books：给定 level+subject+publisher 下的册次（含 grade/title/url）
    """
    rows = _entries()
    levels = _uniq_sorted(e["level"] for e in rows)

    subjects: list[str] = []
    publishers: list[str] = []
    books: list[dict] = []

    if level:
        lv = [e for e in rows if e["level"] == level]
        subjects = _uniq_sorted(e["subject"] for e in lv)
        if subject:
            sv = [e for e in lv if e["subject"] == subject]
            publishers = _uniq_sorted(e["publisher"] for e in sv)
            if publisher:
                books = [
                    {"grade": e["grade"], "title": e["title"], "url": e["url"]}
                    for e in sv if e["publisher"] == publisher
                ]
                books.sort(key=lambda b: (b["grade"], b["title"]))

    return {
        "source": _load().get("source", ""),
        "levels": levels,
        "subjects": subjects,
        "publishers": publishers,
        "books": books,
    }
