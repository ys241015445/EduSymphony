"""Single source of truth for Zhuke (珠科) Kimi / Moonshot settings."""
from __future__ import annotations

import os


def _env_int(key: str, default: int, lo: int = 1, hi: int = 64) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(key, str(default)) or default)))
    except Exception:
        return default


def _env_float(key: str, default: float, lo: float = 60.0, hi: float = 600.0) -> float:
    try:
        return max(lo, min(hi, float(os.getenv(key, str(default)) or default)))
    except Exception:
        return default


KIMI_K2_CONCURRENCY = _env_int("KIMI_K2_CONCURRENCY", 4, 1, 32)
KIMI_K2_MODEL = (
    os.getenv("KIMI_K2_MODEL", "").strip()
    or os.getenv("KIMI_MODEL", "").strip()
    or "kimi-k2-0905-preview"
)
KIMI_K2_TIMEOUT_SEC = _env_float("KIMI_K2_TIMEOUT_SEC", 120.0, 60.0, 600.0)
KIMI_K2_RETRY_ATTEMPTS = _env_int("KIMI_K2_RETRY_ATTEMPTS", 2, 1, 5)
KIMI_K2_RETRY_BACKOFF: tuple[int, ...] = (15, 45)

KIMI_CIRCUIT_WINDOW_SEC = 60
KIMI_CIRCUIT_FAILURE_THRESHOLD = 3
KIMI_CIRCUIT_PAUSE_SEC = 30
