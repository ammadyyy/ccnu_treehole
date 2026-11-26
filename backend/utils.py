"""通用工具函数。"""
from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc


def utcnow() -> str:
    """返回当前 UTC 时间，ISO-8601 秒级字符串（YYYY-MM-DDTHH:MM:SSZ）。

    全库时间字段统一使用该格式保存，字典序即时间序。
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utcnow_ms() -> str:
    """返回当前 UTC 时间，含毫秒（用于需要更高精度的场景）。"""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"


def seconds_since(iso_str: str | None) -> float | None:
    """返回自某个 ISO-8601 UTC 时间以来的秒数；为空时返回 None。"""
    if not iso_str:
        return None
    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds()
