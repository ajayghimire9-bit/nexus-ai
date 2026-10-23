"""Product chat usage ledger. Separate from frozen research CPU and Metal grants.

Daily conversation may start the owned CPU llama-server. It must not debit
the frozen 3564.568 s research CPU ledger or write metal_ledger.json.
A Metal backend existing in the tree does not mean the GUI is on GPU.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

FROZEN_RESEARCH_CPU_S = 3564.568
DEFAULT_DAILY_CAP_S = 600.0
DEFAULT_DAILY_CALLS = 40
LEDGER_NAME = "chat_usage.json"


def _utc_day() -> str:
    return date.today().isoformat()


class ChatUsageLedger:
    def __init__(
        self,
        path: str | Path,
        *,
        daily_cap_s: float = DEFAULT_DAILY_CAP_S,
        daily_calls: int = DEFAULT_DAILY_CALLS,
    ):
        self.path = Path(path)
        self.daily_cap_s = float(daily_cap_s)
        self.daily_calls = int(daily_calls)
        self.data = self._load()

    def _blank(self) -> dict[str, Any]:
        return dict(
            kind="product_chat_usage",
            day=_utc_day(),
            used_s=0.0,
            calls=0,
            cancelled=0,
            inference_ran=0,
            daily_cap_s=self.daily_cap_s,
            daily_call_cap=self.daily_calls,
            backend="cpu",
            gpu_offload=False,
            metal_used=False,
            research_cpu_ledger_frozen_s=FROZEN_RESEARCH_CPU_S,
            research_cpu_ledger_debit_s=0.0,
            consumes_closed_research_allowance=False,
            updated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._blank()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._blank()
        if type(data) is not dict or data.get("kind") != "product_chat_usage":
            return self._blank()
        if data.get("day") != _utc_day():
            return self._blank()
        return data

    def remaining_s(self) -> float:
        return max(0.0, float(self.data.get("daily_cap_s") or self.daily_cap_s) - float(self.data.get("used_s") or 0))

    def remaining_calls(self) -> int:
        return max(0, int(self.data.get("daily_call_cap") or self.daily_calls) - int(self.data.get("calls") or 0))

    def snapshot(self) -> dict[str, Any]:
        row = dict(self.data)
        row.update(
            remaining_s=round(self.remaining_s(), 3),
            remaining_calls=self.remaining_calls(),
            backend="cpu",
            gpu_offload=False,
            metal_used=False,
            research_cpu_ledger_frozen_s=FROZEN_RESEARCH_CPU_S,
            research_cpu_ledger_debit_s=0.0,
            consumes_closed_research_allowance=False,
        )
        return row

    def allow(self, estimated_s: float = 30.0) -> None:
        if self.remaining_calls() < 1 or self.remaining_s() < min(1.0, estimated_s):
            raise ValueError("chat_budget_exhausted")

    def charge(self, wall_s: float, *, inference_ran: bool = False, cancelled: bool = False) -> dict[str, Any]:
        used = max(0.0, float(wall_s or 0.0))
        self.data["used_s"] = round(float(self.data.get("used_s") or 0.0) + used, 3)
        self.data["calls"] = int(self.data.get("calls") or 0) + 1
        if cancelled:
            self.data["cancelled"] = int(self.data.get("cancelled") or 0) + 1
        if inference_ran:
            self.data["inference_ran"] = int(self.data.get("inference_ran") or 0) + 1
        self.data["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.data["backend"] = "cpu"
        self.data["gpu_offload"] = False
        self.data["metal_used"] = False
        self.data["research_cpu_ledger_debit_s"] = 0.0
        self.data["consumes_closed_research_allowance"] = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, allow_nan=False, indent=2), encoding="utf-8")
        return self.snapshot()


def ledger_for(store) -> ChatUsageLedger:
    existing = getattr(store, "chat_usage", None)
    if existing is not None:
        return existing
    path = Path(store.directory) / LEDGER_NAME
    ledger = ChatUsageLedger(path)
    store.chat_usage = ledger
    return ledger
