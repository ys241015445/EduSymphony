"""Local E2E smoke: skip_ai generate → sidecar → docx (no HTTP auth)."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

# backend root on path when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import zhuke_lesson as zl
from app.tasks import zhuke_task as zt


async def main() -> int:
    zl.validate_zhuke_preflight(skip_ai=True)
    rid = str(uuid.uuid4())
    params = {
        "result_id": rid,
        "owner_id": "e2e-smoke-user",
        "course_name": "E2E测试课程",
        "file_name": f"E2E测试课程_珠科教案_smoke.docx",
        "cover": {
            "college": "测试学院",
            "major": "测试专业",
            "class_name": "测试班",
            "course_type": "理论",
            "course_name": "E2E测试课程",
            "teacher": "测试教师",
        },
        "lessons": [
            {
                "title": "第1课",
                "week": "1",
                "content": "测试授课内容大纲",
                "hours": "2 学时",
                "time_label": "第 1 周 星期一  第 3、4 节",
            }
        ],
        "major": "计算机",
        "semester_label": "2025～2026 学年第 2 学期",
        "skip_ai": True,
        "export_record_id": None,
    }
    zt.write_job_params(rid, params)
    target = zt.lesson_target_id(rid, 0)
    await zt.run_zhuke_lesson_single(target)
    ok = await zt.maybe_finalize_zhuke_batch(rid)
    if not ok:
        print("FAIL: finalize returned False")
        return 1
    from app.api.semester_helper import _docx_path_for

    path = _docx_path_for(rid)
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        print(f"FAIL: docx missing or empty: {path}")
        return 1
    print(f"OK: docx={path} size={os.path.getsize(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
