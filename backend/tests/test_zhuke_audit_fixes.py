"""Integration-style tests for EduSymphony audit plan fixes (batches B/C)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.tasks import queue_manager as qm


class TestQueueLeaseAlignment(unittest.TestCase):
    def test_zhuke_lease_at_least_task_timeout(self) -> None:
        self.assertGreaterEqual(qm.ZHUKE_LESSON_LEASE_SEC, qm.TASK_TIMEOUT_SEC)


class TestSystemQueueJobsAccess(unittest.TestCase):
    def test_non_admin_forces_mine(self) -> None:
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from app.api import system as sys_api

        user = MagicMock()
        user.id = "user-1"

        with patch.object(sys_api, "user_access_level", return_value="full"), patch.object(
            sys_api, "list_jobs", new_callable=AsyncMock, return_value=[]
        ) as mock_list:
            asyncio.run(
                sys_api.get_queue_jobs(mine=False, kinds=None, current_user=user)
            )

        mock_list.assert_awaited_once()
        self.assertEqual(mock_list.await_args.kwargs.get("user_id"), "user-1")
