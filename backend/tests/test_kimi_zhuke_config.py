"""Kimi zhuke config and circuit-breaker smoke tests."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestKimiZhukeConfig(unittest.TestCase):
    def test_imported_defaults(self):
        from app.core import kimi_zhuke_config as cfg

        self.assertEqual(cfg.KIMI_K2_CONCURRENCY, 4)
        self.assertEqual(cfg.KIMI_K2_MODEL, "kimi-k2.6")
        self.assertEqual(cfg.KIMI_K2_TIMEOUT_SEC, 120.0)
        self.assertEqual(cfg.KIMI_K2_RETRY_BACKOFF, (15, 45))


class TestKimiCircuitBreaker(unittest.TestCase):
    def test_transient_errors_open_circuit(self):
        from app.tasks import zhuke_task as zt

        zt._kimi_failure_times.clear()
        zt._kimi_circuit_open_until = 0.0
        err = RuntimeError("Request timed out.")
        zt._record_kimi_failure(err)
        zt._record_kimi_failure(err)
        zt._record_kimi_failure(err)
        self.assertGreater(zt._kimi_circuit_open_until, 0.0)

    def test_non_transient_does_not_open_circuit(self):
        from app.tasks import zhuke_task as zt

        zt._kimi_failure_times.clear()
        zt._kimi_circuit_open_until = 0.0
        zt._record_kimi_failure(ValueError("bad json"))
        self.assertEqual(zt._kimi_circuit_open_until, 0.0)


if __name__ == "__main__":
    unittest.main()
