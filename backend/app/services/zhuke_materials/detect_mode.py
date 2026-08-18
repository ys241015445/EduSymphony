"""Heuristic mode detection for 珠科材料助手 (ported from skill_lessonplan4zcst)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

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
    if any(h in raw for h in SYLLABUS_HINTS) or "syllabus" in name:
        tags.add("syllabus")
    if any(h in raw for h in CALENDAR_HINTS) or "calendar" in name:
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


def detect(paths: Iterable[str]) -> dict:
    all_tags: set[str] = set()
    existing: list[str] = []
    missing: list[str] = []
    for s in paths:
        p = Path(s)
        if not p.exists():
            missing.append(s)
            continue
        existing.append(str(p))
        all_tags |= classify_path(p)

    reasons: list[str] = []
    if "syllabus" in all_tags or "calendar" in all_tags:
        mode = "A"
        reasons.append("found syllabus and/or calendar/progress file")
    elif "toc" in all_tags or ("image" in all_tags and not all_tags & {"syllabus", "calendar"}):
        mode = "B"
        reasons.append("toc or image without syllabus/calendar")
    else:
        mode = "C"
        reasons.append("no syllabus/calendar/toc → course-name mode")

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


def detect_from_filenames(names: Iterable[str]) -> dict:
    """Detect mode from upload filenames only (files may not be on disk yet)."""
    fake_paths = []
    for n in names:
        # classify_path only looks at name; invent a path
        fake_paths.append(str(Path("/tmp") / Path(n).name))
    all_tags: set[str] = set()
    for s in fake_paths:
        all_tags |= classify_path(Path(s))
    if "syllabus" in all_tags or "calendar" in all_tags:
        mode = "A"
        reasons = ["filename suggests syllabus/calendar"]
    elif "toc" in all_tags or "image" in all_tags:
        mode = "B"
        reasons = ["filename suggests toc/image"]
    else:
        mode = "C"
        reasons = ["default course-name mode"]
    return {
        "mode": mode,
        "tags": sorted(all_tags),
        "files": list(names),
        "missing": [],
        "reasons": reasons,
        "hints": [
            "STOP for class schedule before calendar",
            "Calendar image cells left for user",
        ],
    }
