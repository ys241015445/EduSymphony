"""Preflight and generate-path smoke tests (no live Kimi / DB required)."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import zhuke_lesson as zl


class TestValidateZhukePreflight(unittest.TestCase):
    @unittest.skipUnless(zl.template_exists(), "zhuke template missing")
    def test_tmp_dir_writable(self):
        with tempfile.TemporaryDirectory() as td:
            sub = os.path.join(td, "tmp_zhuke")
            os.makedirs(sub, exist_ok=True)
            with patch.object(zl, "_zhuke_tmp_dir_for_preflight", return_value=sub):
                zl.validate_zhuke_preflight(skip_ai=True)

    def test_missing_template_raises(self):
        with patch.object(zl, "template_exists", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                zl.validate_zhuke_preflight(skip_ai=True)
            self.assertIn("模板", str(ctx.exception))


class TestQueueStatusBatchResilience(unittest.IsolatedAsyncioTestCase):
    async def test_db_failure_returns_unknown(self):
        from app.tasks import queue_manager as qm

        with patch.object(qm, "async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=OSError("getaddrinfo failed"))
            mock_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
            out = await qm.queue_status_batch("test-rid")
        self.assertEqual(out["status"], "unknown")
        self.assertIn("数据库", out.get("error", ""))


class TestZhukeGenerateEnqueueGuard(unittest.IsolatedAsyncioTestCase):
    async def test_active_batch_returns_409(self):
        from fastapi import HTTPException

        from app.api import semester_helper as sh

        body = sh._ZhukeGenerateIn(
            cover={"course_name": "测试"},
            lessons=[sh._ZhukeLessonIn(title="第1课", content="大纲")],
            skip_ai=True,
        )
        mock_user = MagicMock()
        mock_user.id = "user-test-1"
        mock_db = AsyncMock()

        with patch(
            "app.tasks.queue_manager.user_has_active_zhuke_jobs",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with self.assertRaises(HTTPException) as ctx:
                await sh.zhuke_generate(body, db=mock_db, current_user=mock_user)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("进行中", ctx.exception.detail)

    async def test_enqueue_exception_becomes_503(self):
        from fastapi import HTTPException

        from app.api import semester_helper as sh

        body = sh._ZhukeGenerateIn(
            cover={"course_name": "测试"},
            lessons=[sh._ZhukeLessonIn(title="第1课", content="大纲")],
            skip_ai=True,
        )
        mock_user = MagicMock()
        mock_user.id = "user-test-1"
        mock_db = AsyncMock()

        with patch(
            "app.tasks.queue_manager.user_has_active_zhuke_jobs",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with patch.object(zl, "validate_zhuke_preflight"):
                with patch(
                    "app.api.export._record_export_safely",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    with patch("app.tasks.zhuke_task.write_job_params"):
                        with patch(
                            "app.tasks.zhuke_task.enqueue_zhuke_lesson_jobs",
                            new_callable=AsyncMock,
                            side_effect=RuntimeError("db down"),
                        ):
                            with self.assertRaises(HTTPException) as ctx:
                                await sh.zhuke_generate(body, db=mock_db, current_user=mock_user)
                            self.assertEqual(ctx.exception.status_code, 503)
                            self.assertIn("队列", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
