"""Unpinned Apple Silicon Metal runtime with an explicit memory grant.

This module is separate from the hash-pinned CPU runtime in
``local_model_runtime.py``. The CPU path stays temperature=0. Metal
Best-of-4 sampling is allowed only when ``ExplicitMetalGrant(authorized=True)``
is passed and a ``MetalGrantEnforcer`` is running. Without that grant the
host stays fail-closed.

The Metal session ledger is a distinct file. It must never debit the
frozen CPU ledger (3564.568 s used).

Metal sampling and LoRA are test-time / consolidation tools. They are
not learning-to-learn.
"""
from __future__ import annotations

import json
import os
import platform
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .process_memory import sample_process_memory


GPU_REFUSED = "gpu_memory_enforcement_backend_unavailable_no_execution"
CPU_LEDGER_USED_S = 3564.568
DEFAULT_MAX_RSS_MIB = 4096
DEFAULT_MAX_WALL_S = 30.0
DEFAULT_MAX_SESSION_S = 600.0
MAX_CANDIDATES = 4
CANDIDATE_ZERO_TEMPERATURE = 0.0
DIVERSE_TEMPERATURE = 0.35
METAL_N_GPU_LAYERS = -1
LEDGER_KIND = "metal_session_ledger"


@dataclass(frozen=True)
class ExplicitMetalGrant:
    """Owner-passed Metal authorization. Default is fail-closed."""

    authorized: bool = False
    owner: str = ""
    reason: str = ""
    max_rss_mib: int = DEFAULT_MAX_RSS_MIB
    max_wall_seconds_per_call: float = DEFAULT_MAX_WALL_S
    max_session_metal_seconds: float = DEFAULT_MAX_SESSION_S
    seed: int = 42
    n_gpu_layers: int = METAL_N_GPU_LAYERS
    ledger_path: str = ""

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> "ExplicitMetalGrant":
        data = dict(config or {})
        environ = env if env is not None else os.environ
        authorized = data.get("authorized") is True or environ.get("NEXUS_EXPLICIT_METAL_GRANT") == "1"
        return cls(
            authorized=authorized,
            owner=str(data.get("owner") or ""),
            reason=str(data.get("reason") or ""),
            max_rss_mib=int(data.get("max_rss_mib") or DEFAULT_MAX_RSS_MIB),
            max_wall_seconds_per_call=float(
                data.get("max_wall_seconds_per_call") or DEFAULT_MAX_WALL_S
            ),
            max_session_metal_seconds=float(
                data.get("max_session_metal_seconds") or DEFAULT_MAX_SESSION_S
            ),
            seed=int(data.get("seed") or 42),
            n_gpu_layers=int(data.get("n_gpu_layers") or METAL_N_GPU_LAYERS),
            ledger_path=str(data.get("ledger_path") or ""),
        )


@dataclass(frozen=True)
class MetalSamplePlan:
    index: int
    temperature: float
    seed: int
    n_gpu_layers: int = METAL_N_GPU_LAYERS


def apple_silicon_metal_available(probe: Callable[[], bool] | None = None) -> dict[str, Any]:
    system = platform.system()
    machine = platform.machine()
    darwin_arm64 = system == "Darwin" and machine == "arm64"
    if probe is not None:
        available = bool(probe())
    else:
        available = darwin_arm64
        if available:
            try:
                import torch

                mps = getattr(getattr(torch, "backends", None), "mps", None)
                if mps is not None and hasattr(mps, "is_available") and not mps.is_available():
                    available = False
            except Exception:
                available = darwin_arm64
    return dict(
        available=available,
        system=system,
        machine=machine,
        backend="mps" if available else "",
        metal=available,
    )


def current_process_rss_mib(rss_reader: Callable[[], float | None] | None = None) -> float:
    if rss_reader is not None:
        value = rss_reader()
        if value is None:
            raise ValueError("metal_rss_unreadable")
        return float(value)
    mem = sample_process_memory()
    rss = mem.get("parent_rss_mib")
    if rss is None:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            rss = usage / (1024.0 * 1024.0)
        else:
            rss = usage / 1024.0
    if rss is None:
        raise ValueError("metal_rss_unreadable")
    return float(rss)


def metal_candidate_schedule(k: int, seed: int) -> tuple[MetalSamplePlan, ...]:
    if k < 1 or k > MAX_CANDIDATES:
        raise ValueError("metal_best_of_n_width")
    plans = [
        MetalSamplePlan(
            index=0,
            temperature=CANDIDATE_ZERO_TEMPERATURE,
            seed=seed,
            n_gpu_layers=METAL_N_GPU_LAYERS,
        )
    ]
    for offset in range(1, k):
        plans.append(
            MetalSamplePlan(
                index=offset,
                temperature=DIVERSE_TEMPERATURE,
                seed=seed + offset,
                n_gpu_layers=METAL_N_GPU_LAYERS,
            )
        )
    return tuple(plans)


def _empty_ledger(max_session: float) -> dict[str, Any]:
    return dict(
        kind=LEDGER_KIND,
        used_s=0.0,
        max_session_metal_seconds=max_session,
        cpu_ledger_forbidden=True,
        cpu_ledger_used_s_must_remain=CPU_LEDGER_USED_S,
        calls=[],
    )


def _reject_cpu_ledger_mix(data: Mapping[str, Any]) -> None:
    if data.get("kind") and data.get("kind") != LEDGER_KIND:
        raise ValueError("metal_ledger_must_not_mix_cpu")
    if "cpu_used_s" in data or data.get("device") == "cpu_session":
        raise ValueError("metal_ledger_must_not_mix_cpu")
    used = data.get("used_s")
    if used is not None and abs(float(used) - CPU_LEDGER_USED_S) < 1e-6:
        raise ValueError("metal_ledger_must_not_mix_cpu")


def load_metal_ledger(path: Path, max_session: float) -> dict[str, Any]:
    if not path.exists():
        return _empty_ledger(max_session)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("metal_ledger_invalid")
    _reject_cpu_ledger_mix(data)
    if data.get("kind") != LEDGER_KIND:
        raise ValueError("metal_ledger_must_not_mix_cpu")
    return data


def write_metal_ledger(path: Path, data: Mapping[str, Any]) -> None:
    _reject_cpu_ledger_mix(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class MetalGrantEnforcer:
    """Hard RSS, per-call wall, and Metal-only session budget."""

    def __init__(
        self,
        grant: ExplicitMetalGrant,
        *,
        hardware_probe: Callable[[], bool] | None = None,
        rss_reader: Callable[[], float | None] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not grant.authorized:
            raise ValueError(GPU_REFUSED)
        hardware = apple_silicon_metal_available(probe=hardware_probe)
        if not hardware["available"]:
            raise ValueError("apple_silicon_metal_unavailable")
        if not grant.ledger_path:
            raise ValueError("metal_ledger_path_required")
        self.grant = grant
        self.ledger_path = Path(grant.ledger_path)
        self.rss_reader = rss_reader
        self.clock = clock
        self.hardware = hardware

    def remaining_session_s(self) -> float:
        ledger = load_metal_ledger(self.ledger_path, self.grant.max_session_metal_seconds)
        return float(self.grant.max_session_metal_seconds) - float(ledger.get("used_s") or 0.0)

    def check_rss(self) -> float:
        rss = current_process_rss_mib(self.rss_reader)
        if rss > self.grant.max_rss_mib:
            raise ValueError(f"metal_rss_exceeded:{rss}")
        return rss

    def guarded_call(self, fn: Callable[[], Any]) -> Any:
        if self.remaining_session_s() <= 0:
            raise ValueError("metal_session_budget_exceeded")
        before = self.check_rss()
        started = self.clock()
        try:
            result = fn()
        finally:
            wall = float(self.clock() - started)
            after = None
            rss_error = None
            try:
                after = self.check_rss()
            except ValueError as exc:
                rss_error = exc
            self._debit(wall, before_rss=before, after_rss=after)
            if rss_error is not None:
                raise rss_error
        if wall > self.grant.max_wall_seconds_per_call:
            raise ValueError(f"metal_call_wall_exceeded:{wall}")
        if self.remaining_session_s() < 0:
            raise ValueError("metal_session_budget_exceeded")
        return result

    def _debit(self, wall: float, *, before_rss: float, after_rss: float | None) -> None:
        ledger = load_metal_ledger(self.ledger_path, self.grant.max_session_metal_seconds)
        ledger["used_s"] = float(ledger.get("used_s") or 0.0) + max(0.0, wall)
        calls = list(ledger.get("calls") or [])
        calls.append(
            dict(
                wall_s=round(wall, 6),
                before_rss_mib=before_rss,
                after_rss_mib=after_rss,
            )
        )
        ledger["calls"] = calls
        write_metal_ledger(self.ledger_path, ledger)


def require_authorized_grant(grant: ExplicitMetalGrant | None) -> ExplicitMetalGrant:
    resolved = grant if grant is not None else ExplicitMetalGrant()
    if not resolved.authorized:
        raise ValueError(GPU_REFUSED)
    return resolved


def sample_metal_candidates(
    prompt: str,
    n: int = 4,
    temperature: float = 0.7,
    *,
    grant: ExplicitMetalGrant | None = None,
    sampler: Callable[[str, MetalSamplePlan], str] | None = None,
    enforcer: MetalGrantEnforcer | None = None,
) -> list[str]:
    """Best-of-4 diverse Metal samples. Fail-closed without an explicit grant."""
    del temperature
    resolved = require_authorized_grant(grant)
    k = min(int(n), MAX_CANDIDATES)
    plans = metal_candidate_schedule(k, resolved.seed)
    active = enforcer or MetalGrantEnforcer(resolved)

    def _generate() -> list[str]:
        if sampler is None:
            raise ValueError("metal_sampler_backend_not_started")
        texts = [sampler(prompt, plan) for plan in plans]
        if len(texts) != k:
            raise ValueError("metal_sampler_width")
        return texts

    return list(active.guarded_call(_generate))


def run_metal_lora(
    dataset_path: str | Path,
    *,
    output_dir: str | Path,
    steps: int = 50,
    grant: ExplicitMetalGrant | None = None,
    trainer: Callable[..., dict[str, Any]] | None = None,
    enforcer: MetalGrantEnforcer | None = None,
) -> dict[str, Any]:
    """Bounded sleep consolidation. Fail-closed without an explicit grant."""
    resolved = require_authorized_grant(grant)
    active = enforcer or MetalGrantEnforcer(resolved)

    def _train() -> dict[str, Any]:
        if trainer is None:
            raise ValueError("metal_lora_backend_not_started")
        return trainer(dataset_path=str(dataset_path), output_dir=str(output_dir), steps=steps)

    return dict(active.guarded_call(_train))


def metal_runtime_status(grant: ExplicitMetalGrant | None = None) -> dict[str, Any]:
    resolved = grant if grant is not None else ExplicitMetalGrant()
    if not resolved.authorized:
        return dict(
            available=False,
            device="cpu",
            reason=GPU_REFUSED,
            pinned_runtime_temperature=0,
            parallel_samples_supported=False,
            n_gpu_layers=0,
        )
    hardware = apple_silicon_metal_available()
    return dict(
        available=bool(hardware["available"]),
        device="mps" if hardware["available"] else "cpu",
        reason="" if hardware["available"] else "apple_silicon_metal_unavailable",
        pinned_runtime_temperature=None,
        parallel_samples_supported=True,
        n_gpu_layers=METAL_N_GPU_LAYERS,
        temperatures=(CANDIDATE_ZERO_TEMPERATURE,) + (DIVERSE_TEMPERATURE,) * (MAX_CANDIDATES - 1),
        seeds=tuple([resolved.seed] + [resolved.seed + i for i in range(1, MAX_CANDIDATES)]),
        max_rss_mib=resolved.max_rss_mib,
        max_wall_seconds_per_call=resolved.max_wall_seconds_per_call,
        max_session_metal_seconds=resolved.max_session_metal_seconds,
        learning_to_learn=False,
    )
