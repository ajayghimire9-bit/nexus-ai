"""Development-only twelve-arm evaluator dry-run. No Gymnasium. No training."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from nexus.evolution1.catalogue import catalogue, plan_bound
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution2 import evaluator_readiness as ready
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import decide
from nexus.world.dynamics import WorldModel

USAGE = ready.ROOT / "artifacts" / "evolution2_evaluator_dry_run.json"


def decode_action(binding, action: int):
    idx = int(action)
    if idx < 0 or idx >= binding.n_actions:
        raise RuntimeError("action_decode_failed")
    return binding.action_values[idx]


def source_obs(family: str) -> np.ndarray:
    spec = next(
        row
        for row in clock.LOCKED_ARRAYS
        if row["family"] == family and row["bundle"] == 0 and row["split"] == "train"
    )
    path = ready.ROOT / spec["path"]
    if ready.file_sha256(path) != spec["sha256"]:
        raise RuntimeError("source_array_hash_mismatch")
    data = np.load(path)
    obs = np.asarray(data["obs"][0], dtype=np.float32)
    if obs.shape[-1] != reviewed_binding(family).obs_dim:
        raise RuntimeError("observation_layout_mismatch")
    return obs


def disposable_model(family: str):
    row = next(
        item
        for item in json.loads(ready.FIT_RUN.read_text())["fits"]
        if item["family"] == family and int(item["bundle"]) == 0
    )
    path = ready.ROOT / row["path"]
    if ready.file_sha256(path) != row["sha256"]:
        raise RuntimeError("disposable_weight_hash_mismatch")
    model = WorldModel.load(path)
    if getattr(model, "uses_simulator", False):
        raise RuntimeError("simulator_use_forbidden")
    return model


def _key(family: str, variant) -> str:
    return f"{family}_{variant.rule.value}_{variant.generator.value}_{variant.horizon}"


def run_dry_run() -> dict:
    if ready.SCIENTIFIC:
        ready.require_scientific()
    families = ("pendulum", "acrobot")
    variants = catalogue()
    if len(variants) != 12:
        raise RuntimeError("catalogue_size_mismatch")
    rows = []
    interruption = None
    for family in families:
        binding = reviewed_binding(family)
        obs = source_obs(family)
        model = disposable_model(family)
        operations = []
        ticks = [0]

        def clock_read() -> Clock:
            ticks[0] += 1
            return Clock(0, ticks[0])

        for variant in variants:
            bound = plan_bound(variant, binding.n_actions, 1536)
            operations.append(
                Operation(
                    _key(family, variant),
                    "model",
                    Work(
                        imagined_transitions=bound.imagined_per_decision,
                        model_calls=1,
                        network_forwards=1,
                    ),
                )
            )
        replay = variants[0]
        operations.append(
            Operation(
                f"{family}_cache_{replay.horizon}",
                "cached",
                Work(imagined_transitions=1),
                cache_record_hash=replay.fingerprint,
            )
        )
        physical = Work()
        logical = Work()
        for operation in operations:
            physical = physical.plus(operation.physical_cost)
            logical = logical.plus(operation.cost)
        ledger = ReservationLedger(tuple(operations), Limits(physical, logical, 10**12, 10**12))

        def produce(variant, *, family=family, binding=binding, obs=obs, model=model, ledger=ledger):
            ticket = ledger.reserve(_key(family, variant), clock_read())
            decision = decide(family, variant, obs, model, seed=0)
            decode_action(binding, decision.action)
            ledger.settle(ticket, "success", clock_read())
            return float(max(decision.scores)) if decision.scores else 0.0

        evaluator = TrustedEvaluator(variants, family=family, bundle_id=0, produce_score=produce)
        for variant in variants:
            score = evaluator.evaluate("persist", variant, family=family, bundle_id=0)
            rows.append(
                {
                    "family": family,
                    "rule": variant.rule.value,
                    "generator": variant.generator.value,
                    "horizon": variant.horizon,
                    "score": score,
                    "decoded": True,
                }
            )
        cached = evaluator.evaluate("reset", replay, family=family, bundle_id=0)
        if evaluator.physical != 12 or evaluator.cached != 1:
            raise RuntimeError("trusted_cache_accounting_mismatch")
        ticket = ledger.reserve(f"{family}_cache_{replay.horizon}", clock_read())
        ledger.settle(ticket, "success", clock_read())
        closed = ledger.close(clock_read())
        if closed.status != "complete_execution":
            raise RuntimeError("ledger_incomplete")
        rows[-1]["cache_hit_score"] = cached

    interrupt_ops = (
        Operation("interrupt_probe", "model", Work(imagined_transitions=1, model_calls=1, network_forwards=1)),
        Operation("never_started", "model", Work(imagined_transitions=1, model_calls=1, network_forwards=1)),
    )
    stopped = ReservationLedger(
        interrupt_ops,
        Limits(Work(imagined_transitions=2, model_calls=2, network_forwards=2), Work(imagined_transitions=2, model_calls=2, network_forwards=2), 10**12, 10**12),
    )
    ticket = stopped.reserve("interrupt_probe", Clock(0, 1))
    stopped.settle(ticket, "interrupted", Clock(0, 2))
    report = stopped.close(Clock(0, 3))
    interruption = {"status": report.status, "reason": report.reason, "unresolved": list(report.unresolved_keys)}
    payload = {
        "scientific": False,
        "collection": False,
        "gymnasium": False,
        "training": False,
        "hold_named": False,
        "n_planner_configs": 12,
        "n_family_rows": len(rows),
        "rows": rows,
        "interruption": interruption,
        "physical_vs_logical": {"physical_decisions": 24, "cached_replays": 2},
        "enabled_dispatch": False,
        "twenty_fit_measured": False,
        "h16_scientific_ledger_untouched": True,
        "claims_learning_to_learn": False,
        "is_agi": False,
    }
    USAGE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
