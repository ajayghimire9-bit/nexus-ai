"""Parent plus llama-server RSS. Weight-file size is not runtime memory."""
from __future__ import annotations

import os
import subprocess
from typing import Any


def _rss_kib(pid: int | None) -> int | None:
    if not pid:
        return None
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(pid)],
            text=True,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    try:
        return int(out.split()[0])
    except ValueError:
        return None


def _mib(kib: int | None) -> float | None:
    if kib is None:
        return None
    return round(kib / 1024, 3)


def sample_process_memory(runtime=None) -> dict[str, Any]:
    parent = os.getpid()
    server = getattr(getattr(runtime, "process", None), "pid", None)
    parent_kib = _rss_kib(parent)
    server_kib = _rss_kib(server)
    combined = None
    if parent_kib is not None and server_kib is not None:
        combined = parent_kib + server_kib
    elif parent_kib is not None:
        combined = parent_kib
    return {
        "parent_pid": parent,
        "server_pid": server,
        "parent_rss_mib": _mib(parent_kib),
        "server_rss_mib": _mib(server_kib),
        "combined_rss_mib": _mib(combined),
        "source": "ps_rss_kib",
        "weight_file_is_not_memory": True,
    }
