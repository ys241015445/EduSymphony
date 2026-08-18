"""Pipeline helpers for 珠科材料助手 projects."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from app.core.config import settings


def project_dir(project_id: str) -> str:
    d = os.path.join(settings.FILES_DIR, "zhuke_materials", project_id)
    os.makedirs(d, exist_ok=True)
    return d


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def loads(s: Optional[str], default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def project_public(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "course_name": row.course_name,
        "mode": row.mode,
        "status": row.status,
        "error": row.error,
        "schedule": loads(row.schedule_json),
        "syllabus": loads(row.syllabus_json),
        "weeks": loads(row.weeks_json),
        "lessons": loads(row.lessons_json),
        "has_syllabus_file": bool(row.syllabus_path),
        "has_calendar_theory": bool(row.calendar_theory_path),
        "has_calendar_lab": bool(row.calendar_lab_path),
        "has_lessons_file": bool(row.lessons_path),
        "has_material_html": bool(getattr(row, "material_html_path", None)),
        "has_ppt": bool(getattr(row, "ppt_path", None)),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
