"""Tests for zhuke auto-recover orchestrator and recover API."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import zhuke_lesson as zl


def _params_payload(*, lessons_count: int = 2, skip_ai: bool = True) -> dict:
    return {
        "owner_id": "user-recover-1",
        "export_record_id": "export-1",
        "skip_ai": skip_ai,
        "course_name": "测试课程",
        "cover": {"course_name": "测试课程"},
        "lessons": [
            {"title": f"第{i + 1}课", "content": f"大纲{i + 1}"}
            for i in range(lessons_count)
        ],
        "file_name": "test.docx",
    }


class TestAutoRecoverZhukeBatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.td = tempfile.mkdtemp()
        self.rid = "recover-test-rid"

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)

    def _paths(self):
        from app.tasks import zhuke_task as zt

        base = os.path.join(self.td, self.rid)
        return {
            "params": base + ".params.json",
            "lessons": base + ".lessons.json",
            "docx": os.path.join(self.td, f"{self.rid}.docx"),
            "meta": base + ".meta.json",
        }

    def _write_params(self, *, lessons_count: int = 2, skip_ai: bool = True) -> None:
        p = self._paths()["params"]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(_params_payload(lessons_count=lessons_count, skip_ai=skip_ai), f)

    def _write_lessons(self, entries: dict) -> None:
        p = self._paths()["lessons"]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)

    def _patch_dirs(self):
        from app.api import semester_helper as sh
        from app.tasks import zhuke_task as zt

        def docx_path(rid: str) -> str:
            return os.path.join(self.td, f"{rid}.docx")

        return (
            patch.object(zt, "_zhuke_tmp_dir", return_value=self.td),
            patch.object(zt, "_batch_has_active_jobs", AsyncMock(return_value=False)),
            patch.object(zt, "_update_export_record", AsyncMock()),
            patch.object(sh, "_docx_path_for", side_effect=docx_path),
            patch.object(sh, "_zhuke_tmp_dir", return_value=self.td),
        )

    def _enter_patches(self):
        from contextlib import ExitStack

        stack = ExitStack()
        for p in self._patch_dirs():
            stack.enter_context(p)
        return stack

    async def test_impossible_without_params(self) -> None:
        from app.tasks.zhuke_task import auto_recover_zhuke_batch

        with self._enter_patches():
            result = await auto_recover_zhuke_batch(self.rid)
        self.assertEqual(result.action, "impossible")

    async def test_requeue_missing_lessons(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params()
        self._write_lessons({"0": {"title": "第1课", "sections": {}, "failed": False}})

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_lesson_jobs", new_callable=AsyncMock, return_value=1
        ) as mock_enqueue:
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=False, mode="full")

        self.assertEqual(result.action, "requeued")
        self.assertEqual(result.enqueued, 1)
        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.await_args.kwargs
        self.assertEqual(call_kwargs.get("only_indices"), {1})

        with open(self._paths()["lessons"], encoding="utf-8") as f:
            remaining = json.load(f)
        self.assertNotIn("1", remaining)

    async def test_requeue_failed_lesson(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params(lessons_count=1)
        self._write_lessons(
            {
                "0": {
                    "title": "第1课",
                    "sections": {},
                    "failed": True,
                    "lesson_idx": 0,
                }
            }
        )

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_lesson_jobs", new_callable=AsyncMock, return_value=1
        ):
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=False, mode="full")

        self.assertEqual(result.action, "requeued")
        with open(self._paths()["lessons"], encoding="utf-8") as f:
            remaining = json.load(f)
        self.assertEqual(remaining, {})

    @unittest.skipUnless(zl.template_exists(), "zhuke template missing")
    async def test_finalize_when_sidecar_complete_no_docx(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params(lessons_count=1)
        self._write_lessons(
            {
                "0": {
                    "title": "第1课",
                    "topic": "大纲",
                    "sections": {"教学目标": "目标内容"},
                    "failed": False,
                }
            }
        )

        with self._enter_patches(), patch.object(
            zt, "_emit_complete", new_callable=AsyncMock
        ):
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=False, mode="full")

        self.assertIn(result.action, ("finalized", "rebuilt"))
        self.assertTrue(result.file_exists)
        self.assertTrue(os.path.isfile(self._paths()["docx"]))

    async def test_relayout_queued_on_lint_issues(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params(lessons_count=1, skip_ai=False)
        # lint_sections_format only flags issues the local normaliser can't
        # fix. Use a markdown bold residue that survives normalize and stays
        # detectable by _RE_MARKDOWN_RESIDUE.
        bad_sections = {"教学目标": "**重要**目标"}
        self.assertTrue(zl.lint_sections_format(bad_sections))
        self._write_lessons(
            {
                "0": {
                    "title": "第1课",
                    "topic": "大纲",
                    "sections": bad_sections,
                    "failed": False,
                }
            }
        )
        with open(self._paths()["docx"], "wb") as f:
            f.write(b"fake")

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_relayout_jobs", new_callable=AsyncMock, return_value=1
        ) as mock_relayout, patch(
            "app.core.config.settings.ZHUKE_LAYOUT_REVIEW_ON_LINT", True,
        ):
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=True, mode="full")

        self.assertEqual(result.action, "relayout_queued")
        self.assertEqual(result.layout_enqueued, 1)
        mock_relayout.assert_awaited_once()
        self.assertFalse(os.path.isfile(self._paths()["docx"]))

    async def test_rebuild_mode_skips_requeue(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params()
        self._write_lessons({"0": {"title": "第1课", "sections": {}, "failed": False}})

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_lesson_jobs", new_callable=AsyncMock, return_value=1
        ) as mock_enqueue:
            result = await zt.auto_recover_zhuke_batch(self.rid, mode="rebuild")

        self.assertIn(result.action, ("rebuilt", "finalized"))
        self.assertTrue(result.file_exists)
        mock_enqueue.assert_not_awaited()

    async def test_default_mode_rebuild_skips_requeue(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params()
        self._write_lessons({"0": {"title": "第1课", "sections": {}, "failed": False}})

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_lesson_jobs", new_callable=AsyncMock, return_value=1
        ) as mock_enqueue:
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=False)

        self.assertIn(result.action, ("rebuilt", "finalized", "impossible"))
        mock_enqueue.assert_not_awaited()

    async def test_relayout_skipped_when_layout_review_off(self) -> None:
        from app.tasks import zhuke_task as zt

        self._write_params(lessons_count=1, skip_ai=False)
        bad_sections = {"教学目标": "**重要**目标"}
        self._write_lessons(
            {
                "0": {
                    "title": "第1课",
                    "topic": "大纲",
                    "sections": bad_sections,
                    "failed": False,
                }
            }
        )
        with open(self._paths()["docx"], "wb") as f:
            f.write(b"fake")

        with self._enter_patches(), patch.object(
            zt, "enqueue_zhuke_relayout_jobs", new_callable=AsyncMock, return_value=1
        ) as mock_relayout, patch(
            "app.core.config.settings.ZHUKE_LAYOUT_REVIEW_ON_LINT", False,
        ):
            result = await zt.auto_recover_zhuke_batch(self.rid, check_layout=True, mode="full")

        self.assertNotEqual(result.action, "relayout_queued")
        mock_relayout.assert_not_awaited()


class TestZhukeStalledReason(unittest.IsolatedAsyncioTestCase):
    async def test_none_when_progress_started(self) -> None:
        from app.api import semester_helper as sh

        self.assertIsNone(await sh._zhuke_stalled_reason("rid", status="running", done=2))

    async def test_none_when_inactive_status(self) -> None:
        from app.api import semester_helper as sh

        self.assertIsNone(await sh._zhuke_stalled_reason("rid", status="done", done=0))


class TestUserCancellation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.td = tempfile.mkdtemp()
        self.rid = "cancel-test-rid"

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.td, ignore_errors=True)

    def _patch_dirs(self):
        from app.api import semester_helper as sh
        from app.tasks import zhuke_task as zt

        def meta_path(rid: str) -> str:
            return os.path.join(self.td, f"{rid}.meta.json")

        return (
            patch.object(zt, "_zhuke_tmp_dir", return_value=self.td),
            patch.object(sh, "_meta_path_for", side_effect=meta_path),
            patch.object(sh, "_zhuke_tmp_dir", return_value=self.td),
        )

    def _enter_patches(self):
        from contextlib import ExitStack

        stack = ExitStack()
        for p in self._patch_dirs():
            stack.enter_context(p)
        return stack

    def test_mark_and_clear_user_cancelled(self) -> None:
        from app.tasks import zhuke_task as zt

        with self._enter_patches():
            self.assertFalse(zt.is_user_cancelled(self.rid))
            zt.mark_user_cancelled(self.rid)
            self.assertTrue(zt.is_user_cancelled(self.rid))
            meta = zt._read_sidecar_meta(self.rid)
            self.assertIn("cancelled_at", meta)
            zt.clear_user_cancelled(self.rid)
            self.assertFalse(zt.is_user_cancelled(self.rid))
            meta = zt._read_sidecar_meta(self.rid)
            self.assertNotIn("cancelled_at", meta)

    async def test_auto_recover_full_clears_cancelled_flag(self) -> None:
        """An explicit user regenerate (mode='full') resumes the batch."""
        from app.tasks import zhuke_task as zt

        with self._enter_patches():
            zt.mark_user_cancelled(self.rid)
            self.assertTrue(zt.is_user_cancelled(self.rid))
            with patch.object(zt, "params_sidecar_exists", return_value=False):
                result = await zt.auto_recover_zhuke_batch(self.rid, mode="full")
            self.assertFalse(zt.is_user_cancelled(self.rid))
            self.assertEqual(result.action, "impossible")

    async def test_auto_recover_rebuild_skips_cancelled(self) -> None:
        """Implicit rebuild MUST respect the stop sentinel."""
        from app.tasks import zhuke_task as zt

        with self._enter_patches():
            zt.mark_user_cancelled(self.rid)
            with patch.object(zt, "params_sidecar_exists", return_value=True):
                result = await zt.rebuild_zhuke_docx_only(self.rid)
            self.assertEqual(result.action, "cancelled")
            self.assertEqual(result.status, "cancelled")
            self.assertTrue(zt.is_user_cancelled(self.rid))

    async def test_recover_snapshot_returns_cancelled(self) -> None:
        from app.api import semester_helper as sh
        from app.tasks import zhuke_task as zt

        with self._enter_patches():
            zt.mark_user_cancelled(self.rid)
            with patch.object(sh, "_docx_path_for", side_effect=lambda rid: os.path.join(self.td, f"{rid}.docx")):
                file_exists, recover_action, recovering = await sh._zhuke_recover_snapshot(
                    self.rid,
                    status="failed",
                    file_exists=False,
                    active_jobs=set(),
                )
            self.assertEqual(recover_action, "cancelled")
            self.assertFalse(recovering)

    async def test_cancel_without_active_jobs_does_not_mark_user(self) -> None:
        from app.tasks import zhuke_task as zt

        with self._enter_patches(), patch(
            "app.tasks.queue_manager.cancel_zhuke_jobs_for_batch", new_callable=AsyncMock, return_value=0
        ), patch.object(
            zt, "_batch_has_active_jobs", new_callable=AsyncMock, return_value=False
        ), patch.object(
            zt, "_docx_exists", return_value=False
        ), patch.object(
            zt, "mark_user_cancelled"
        ) as mock_mark:
            result = await zt.cancel_zhuke_batch(self.rid)

        mock_mark.assert_not_called()
        self.assertEqual(result.cancelled, 0)


class TestZhukeRecoverEndpoint(unittest.IsolatedAsyncioTestCase):
    async def test_recover_forbidden_for_other_user(self) -> None:
        from fastapi import HTTPException

        from app.api import semester_helper as sh

        mock_user = MagicMock()
        mock_user.id = "other-user"

        with patch.object(sh, "_zhuke_owner_from_meta", return_value="owner-user"):
            with self.assertRaises(HTTPException) as ctx:
                await sh.zhuke_recover("rid-forbidden", current_user=mock_user)
            self.assertEqual(ctx.exception.status_code, 403)

    async def test_recover_defaults_rebuild_mode(self) -> None:
        from app.api import semester_helper as sh
        from app.tasks.zhuke_task import ZhukeRecoverResult

        mock_user = MagicMock()
        mock_user.id = "owner-user"

        with patch.object(sh, "_zhuke_owner_from_meta", return_value="owner-user"):
            with patch(
                "app.tasks.zhuke_task.auto_recover_zhuke_batch",
                new_callable=AsyncMock,
                return_value=ZhukeRecoverResult(
                    action="rebuilt",
                    file_exists=True,
                    status="done",
                    message="已从 sidecar 重建 docx",
                ),
            ) as mock_recover:
                out = await sh.zhuke_recover("rid-ok", current_user=mock_user)

        mock_recover.assert_awaited_once()
        call_kwargs = mock_recover.await_args.kwargs
        self.assertEqual(call_kwargs.get("mode"), "rebuild")
        self.assertFalse(call_kwargs.get("check_layout"))
        self.assertEqual(out.action, "rebuilt")
        self.assertTrue(out.file_exists)


class TestZhukeCancelEndpoint(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_forbidden_for_other_user(self) -> None:
        from fastapi import HTTPException

        from app.api import semester_helper as sh

        mock_user = MagicMock()
        mock_user.id = "other-user"

        with patch.object(sh, "_zhuke_owner_from_meta", return_value="owner-user"):
            with self.assertRaises(HTTPException) as ctx:
                await sh.zhuke_cancel("rid-forbidden", current_user=mock_user)
            self.assertEqual(ctx.exception.status_code, 403)

    async def test_cancel_ok(self) -> None:
        from app.api import semester_helper as sh
        from app.tasks.zhuke_task import ZhukeCancelResult

        mock_user = MagicMock()
        mock_user.id = "owner-user"

        with patch.object(sh, "_zhuke_owner_from_meta", return_value="owner-user"):
            with patch(
                "app.tasks.zhuke_task.cancel_zhuke_batch",
                new_callable=AsyncMock,
                return_value=ZhukeCancelResult(
                    cancelled=3,
                    file_exists=True,
                    status="done",
                    message="已停止（取消 3 个任务）；已保留已生成的文件",
                ),
            ):
                out = await sh.zhuke_cancel("rid-ok", current_user=mock_user)

        self.assertEqual(out.cancelled, 3)
        self.assertTrue(out.file_exists)
        self.assertEqual(out.status, "done")


if __name__ == "__main__":
    unittest.main()
