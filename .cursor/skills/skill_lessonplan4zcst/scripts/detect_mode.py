# -*- coding: utf-8 -*-
"""Heuristic mode detection for skill_lessonplan4zcst (read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SYLLABUS_HINTS = ("大纲", "syllabus", "教学大纲")
CALENDAR_HINTS = ("日历", "进度", "calendar", "进度表")
TOC_HINTS = ("目录", "toc", "contents")
TALENT_HINTS = ("人培", "培养方案", "人才培养")
JIAOAN_HINTS = ("教案", "教学设计")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
DOC_EXT = {".doc", ".docx", ".pdf", ".xlsx", ".xls"}


def classify_path(p: Path) -> set[str]:
    tags: set[str] = set()
    name = p.name.lower()
    raw = p.name
    if any(h in raw for h in SYLLABUS_HINTS) or any(h in name for h in ("syllabus",)):
        tags.add("syllabus")
    if any(h in raw for h in CALENDAR_HINTS) or any(h in name for h in ("calendar",)):
        tags.add("calendar")
    if any(h in raw for h in TOC_HINTS):
        tags.add("toc")
    if any(h in raw for h in TALENT_HINTS):
        tags.add("talent")
    if any(h in raw for h in JIAOAN_HINTS):
        tags.add("jiaoan")
    if p.suffix.lower() in IMAGE_EXT:
        tags.add("image")
    if p.suffix.lower() in DOC_EXT:
        tags.add("doc")
    return tags


def detect(paths: list[str]) -> dict:
    all_tags: set[str] = set()
    existing = []
    missing = []
    for s in paths:
        p = Path(s)
        if not p.exists():
            missing.append(s)
            continue
        existing.append(str(p))
        all_tags |= classify_path(p)

    reasons = []
    if "syllabus" in all_tags or "calendar" in all_tags:
        mode = "A"
        reasons.append("found syllabus and/or calendar/progress file")
    elif "toc" in all_tags or ("image" in all_tags and not all_tags & {"syllabus", "calendar"}):
        mode = "B"
        reasons.append("toc or image without syllabus/calendar → treat as textbook-outline mode")
    else:
        mode = "C"
        reasons.append("no syllabus/calendar/toc → course-name / metadata mode")

    hints = [
        "Align with talent plan before filling syllabus",
        "STOP and ask weekday + period range before calendar",
        "Do not alter template formatting",
        "Calendar image cells left for user to fill",
    ]
    if "talent" in all_tags:
        hints.insert(0, "Use uploaded talent plan instead of default")

    return {
        "mode": mode,
        "tags": sorted(all_tags),
        "files": existing,
        "missing": missing,
        "reasons": reasons,
        "hints": hints,
    }


def main(argv: list[str]) -> int:
    paths = argv[1:]
    if not paths:
        print(
            json.dumps(
                {
                    "mode": "C",
                    "tags": [],
                    "files": [],
                    "missing": [],
                    "reasons": ["no paths provided"],
                    "hints": [
                        "Ask course name and any metadata screenshot",
                        "STOP for class schedule before calendar",
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    print(json.dumps(detect(paths), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
