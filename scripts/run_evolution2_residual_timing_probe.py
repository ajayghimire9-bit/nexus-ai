"""Read-only residual-MLP timing probe. No env collection. No checkpoint writes."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from nexus.evolution1.catalogue import Generator, Rule, Variant
from nexus.evolution2 import residual_timing_probe as lock
from nexus.evolution2.planner_adapter import decide
from nexus.world.context_model import ContextWorldModel
from nexus.world.dynamics import WorldModel

ROOT = Path(__file__).resolve().parents[1]
USAGE = ROOT / "artifacts" / "research_session_e2_residual_timing_probe_usage.json"
VARIANT = Variant(Rule.SUCCESSOR, Generator.IID, 16)


def _load_model(spec: dict):
    path = ROOT / spec["path"]
    if spec["id"] == "pendulum_frozen_decoder":
        model = ContextWorldModel.create(3, 3, seed=0)
        blob = torch.load(path, map_location="cpu", weights_only=False)
        model.encoder.load_state_dict(blob["encoder"])
        model.net.load_state_dict(blob["net"])
        model.obs_rms.load_state_dict(blob["obs_rms"])
        model.clear_context()
        return model
    if spec["id"] == "pendulum_residual_mlp":
        blob = torch.load(path, map_location="cpu", weights_only=False)
        model = WorldModel.create(3, 3, kind="residual", hidden=(64, 64), seed=0, arch="mlp")
        model.net.load_state_dict(blob["net"])
        model.obs_rms.load_state_dict(blob["obs_rms"])
        model.net.eval()
        return model
    model = WorldModel.load(path, device="cpu")
    model.net.eval()
    return model


def _probe_one(spec: dict, *, imagined_budget: int, time_budget_s: float) -> dict:
    model = _load_model(spec)
    if hasattr(model, "net"):
        model.net.eval()
    rng = np.random.default_rng(0)
    obs = rng.standard_normal(model.net.obs_dim).astype(np.float32)
    decide(spec["family"], VARIANT, obs, model, seed=0)
    imagined = 0
    decisions = 0
    t0 = time.perf_counter()
    while imagined < imagined_budget:
        wall = time.perf_counter() - t0
        if wall >= time_budget_s:
            break
        obs = rng.standard_normal(model.net.obs_dim).astype(np.float32)
        decision = decide(
            spec["family"], VARIANT, obs, model, seed=1 + decisions
        )
        imagined += int(decision.imagined)
        decisions += 1
    wall = time.perf_counter() - t0
    per = wall / imagined if imagined else None
    out = {
        "id": spec["id"],
        "family": spec["family"],
        "path": spec["path"],
        "obs_dim": int(model.net.obs_dim),
        "n_actions": int(model.net.n_actions),
        "kind": str(getattr(model, "kind", spec["id"])),
        "decisions": decisions,
        "imagined": imagined,
        "wall_s": wall,
        "seconds_per_imagined": per,
        "env_steps": 0,
        "checkpoint_writes": 0,
    }
    if per is not None:
        out["extrapolation"] = lock.extrapolate(per)
    return out


def main() -> int:
    lock.require_probe()
    time_cap = float(lock.AUTHORIZED_TIME_CAP_S)
    imagined_cap = int(lock.AUTHORIZED_IMAGINED_CAP)
    per_model = imagined_cap // len(lock.REQUIRED_CHECKPOINTS)
    per_time = time_cap / len(lock.REQUIRED_CHECKPOINTS)
    started = time.perf_counter()
    rows = []
    outcome = "probe_complete"
    try:
        for spec in lock.REQUIRED_CHECKPOINTS:
            remaining = time_cap - (time.perf_counter() - started)
            if remaining <= 0:
                outcome = "incomplete_budget"
                break
            rows.append(
                _probe_one(
                    spec,
                    imagined_budget=per_model,
                    time_budget_s=min(per_time, remaining),
                )
            )
    except Exception as exc:
        outcome = "invalid_integrity"
        rows.append({"error": str(exc)})
    wall = time.perf_counter() - started
    if wall > time_cap and outcome == "probe_complete":
        outcome = "incomplete_budget"
    payload = {
        "scientific": False,
        "collection": False,
        "hold_named": False,
        "outcome": outcome,
        "wall_s": wall,
        "env_steps": 0,
        "checkpoint_writes": 0,
        "models": rows,
        "authorized_time_cap_s": lock.AUTHORIZED_TIME_CAP_S,
        "authorized_env_cap": lock.AUTHORIZED_ENV_CAP,
        "authorized_imagined_cap": lock.AUTHORIZED_IMAGINED_CAP,
        "failed_attempt_s": 0.33463058300549163,
        "session_ledger_used_before_s": lock.SESSION_LEDGER_USED_S,
        "session_ledger_remaining_before_s": lock.SESSION_LEDGER_REMAINING_S,
        "session_ledger_used_after_s": lock.SESSION_LEDGER_USED_S + 0.33463058300549163 + wall,
        "session_ledger_remaining_after_s": lock.SESSION_LEDGER_REMAINING_S - 0.33463058300549163 - wall,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    lock.RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    USAGE.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"outcome": outcome, "wall_s": wall, "models": len(rows)}, indent=2))
    return 0 if outcome == "probe_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
