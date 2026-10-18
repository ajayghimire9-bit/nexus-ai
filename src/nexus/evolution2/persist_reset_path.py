"""Development-only real execution-path verification. env_cap=0. Not science.

Connects persist/reset/random/evolution to TrustedEvaluator scores produced
by planner_adapter.decide on disposable residual copies. No Gymnasium.
No new fits. Does not grant 7680.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from nexus.evolution1.catalogue import catalogue, plan_bound
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2 import evaluator_dry_run as dry
from nexus.evolution2 import evaluator_readiness as eval_ready
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import make_methods
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import decide, twelve_arm_scientific_dispatch
from nexus.evolution2.screen import SHARED_PROBES, feedback_event
from nexus.evolution2.tasks import PROPOSALS
from nexus.world.dynamics import WorldModel

ROOT = Path(__file__).resolve().parents[3]
USAGE = budget.USAGE
FAMILIES = ("pendulum", "acrobot")
METHOD_KEYS = {
    "persist": "persistent_adaptive",
    "reset": "reset_adaptive",
    "random": "random",
    "evolution": "evolutionary",
}


def refuse_science() -> None:
    record = lock.allocation_record()
    if record.get("authorized") is True or int(record.get("env_cap") or 0) != 0:
        raise RuntimeError("scientific_authorization_must_remain_false")
    if eval_ready.SCIENTIFIC:
        eval_ready.require_scientific()


def source_obs(family: str, bundle: int = 0) -> np.ndarray:
    spec = next(
        row
        for row in clock.LOCKED_ARRAYS
        if row["family"] == family and int(row["bundle"]) == int(bundle) and row["split"] == "train"
    )
    path = ROOT / spec["path"]
    if eval_ready.file_sha256(path) != spec["sha256"]:
        raise RuntimeError("source_array_hash_mismatch")
    data = np.load(path)
    obs = np.asarray(data["obs"][0], dtype=np.float32)
    if obs.shape[-1] != reviewed_binding(family).obs_dim:
        raise RuntimeError("observation_layout_mismatch")
    return obs


def disposable_model(family: str, bundle: int = 0):
    row = next(
        item
        for item in json.loads(eval_ready.FIT_RUN.read_text())["fits"]
        if item["family"] == family and int(item["bundle"]) == int(bundle)
    )
    path = ROOT / row["path"]
    if eval_ready.file_sha256(path) != row["sha256"]:
        raise RuntimeError("disposable_weight_hash_mismatch")
    model = WorldModel.load(path)
    if getattr(model, "uses_simulator", False):
        raise RuntimeError("simulator_use_forbidden")
    return model


def family_context(family: str) -> PublicFixtureContext:
    binding = reviewed_binding(family)
    return PublicFixtureContext(binding.n_actions, binding.obs_dim, binding.episode_steps, 1536)


def _phys_key(family: str, variant) -> str:
    return f"{family}_{variant.rule.value}_{variant.generator.value}_{variant.horizon}"


def measure_planner_clock() -> dict:
    refuse_science()
    variants = catalogue()
    imagined = 0
    n_decisions = 0
    cpu0 = time.process_time()
    wall0 = time.perf_counter()
    for family in FAMILIES:
        binding = reviewed_binding(family)
        obs = source_obs(family, 0)
        model = disposable_model(family, 0)
        for variant in variants:
            decision = decide(family, variant, obs, model, seed=0)
            dry.decode_action(binding, decision.action)
            imagined += int(decision.imagined)
            n_decisions += 1
    wall_s = time.perf_counter() - wall0
    cpu_s = time.process_time() - cpu0
    per_decision = wall_s / n_decisions if n_decisions else None
    return {
        "scientific": False,
        "gymnasium": False,
        "env_steps": 0,
        "env_cap": 0,
        "n_decisions": n_decisions,
        "imagined": imagined,
        "wall_s": wall_s,
        "cpu_s": cpu_s,
        "seconds_per_decision": per_decision,
        "screen_9600_prior_s": None if per_decision is None else per_decision * budget.SCREEN_DECISIONS_UPPER,
        "prior_label": "development_disposable_defaults_not_new_physics",
        "do_not_treat_as_scientific_clock": True,
        "twenty_fit_measured": False,
    }


def _unit_interval(raw: dict) -> dict:
    values = list(raw.values())
    lo, hi = min(values), max(values)
    if hi == lo:
        return {key: 0.5 for key in raw}
    return {key: (value - lo) / (hi - lo) for key, value in raw.items()}


def verify_execution_path(seed: int = 7) -> dict:
    refuse_science()
    variants = catalogue()
    methods = {short: make_methods(seed)[inner] for short, inner in METHOD_KEYS.items()}
    persist_after = []
    reset_after = []
    lookups = {name: 0 for name in methods}
    hidden_blocked = False
    physical_decisions = 0
    for family in FAMILIES:
        binding = reviewed_binding(family)
        context = family_context(family)
        obs = source_obs(family, 0)
        model = disposable_model(family, 0)
        operations = []
        ticks = [0]

        def clock_read(ticks=ticks) -> Clock:
            ticks[0] += 1
            return Clock(0, ticks[0])

        raw = {}
        for variant in variants:
            bound = plan_bound(variant, binding.n_actions, 1536)
            operations.append(
                Operation(
                    _phys_key(family, variant),
                    "model",
                    Work(
                        imagined_transitions=bound.imagined_per_decision,
                        model_calls=1,
                        network_forwards=1,
                    ),
                )
            )
        physical = Work()
        logical = Work()
        for operation in operations:
            physical = physical.plus(operation.physical_cost)
            logical = logical.plus(operation.cost)
        ledger = ReservationLedger(tuple(operations), Limits(physical, logical, 10**12, 10**12))
        for variant in variants:
            ticket = ledger.reserve(_phys_key(family, variant), clock_read())
            decision = decide(family, variant, obs, model, seed=0)
            dry.decode_action(binding, decision.action)
            raw[variant] = float(max(decision.scores)) if decision.scores else 0.0
            ledger.settle(ticket, "success", clock_read())
            physical_decisions += 1
        closed = ledger.close(clock_read())
        if closed.status != "complete_execution":
            raise RuntimeError("ledger_incomplete")
        unit = _unit_interval(raw)
        evaluator = TrustedEvaluator(
            variants,
            family=family,
            bundle_id=0,
            produce_score=lambda variant, unit=unit: unit[variant],
        )
        hidden = variants[-1]
        evaluator.hide_development(hidden, unit[hidden])
        try:
            evaluator.evaluate("persist", hidden, family=family, bundle_id=0)
        except RuntimeError as exc:
            if "hidden_development_outcome" not in str(exc):
                raise
            hidden_blocked = True
        task = SimpleNamespace(task_id=f"{family}:0")
        for name, method in methods.items():
            if method.resets:
                method.reset_task()
                if name == "reset":
                    reset_after.append(dict(method.learned_state()))
            available = [variant for variant in variants if variant is not hidden]
            for slot in range(PROPOSALS):
                variant = ANCHORS[slot] if slot < SHARED_PROBES else method.choose(tuple(available), context)
                if variant not in available:
                    raise RuntimeError("duplicate_or_invalid_proposal")
                score = evaluator.evaluate(method.name, variant, family=family, bundle_id=0)
                receipt = TrainingFeedback(
                    variant.fingerprint,
                    score,
                    False,
                    feedback_event(task, slot, variant.fingerprint),
                )
                method.update(receipt, context)
                lookups[name] += 1
                available.remove(variant)
            if hidden.fingerprint in evaluator.training_feedback(method.name):
                raise RuntimeError("hidden_development_leaked_into_training")
        persist_after.append(dict(methods["persist"].learned_state()))
    frozen = methods["persist"].freeze()
    if methods["persist"].learned_state()["weights"] != frozen["weights"]:
        raise RuntimeError("persist_mutated_after_freeze")
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unequal_proposal_budget")
    scientific = twelve_arm_scientific_dispatch()
    return {
        "status": "PASS",
        "scientific": False,
        "gymnasium": False,
        "env_steps": 0,
        "env_cap": 0,
        "granted_7680": False,
        "methods_exercised": list(METHOD_KEYS),
        "lookups_per_method": lookups,
        "persist_cross_family": persist_after[-1]["weights"] != persist_after[0]["weights"],
        "reset_discarded": all(
            row["updates"] == 0 and row["weights"] == (0.0,) * 6 for row in reset_after
        ),
        "hidden_development_blocked": hidden_blocked,
        "physical_planner_decisions": physical_decisions,
        "twelve_arm_scientific": scientific["status"],
        "enabled_dispatch": False,
        "training_feedback_unit_interval": True,
        "note": "Disposable default residuals only. Not new-physics source fitting.",
    }


def run_budget_verification() -> dict:
    refuse_science()
    clocked = measure_planner_clock()
    path = verify_execution_path()
    if clocked["env_steps"] != 0 or path["env_steps"] != 0:
        raise RuntimeError("env_steps_must_remain_zero")
    if path["granted_7680"] is not False:
        raise RuntimeError("7680_must_remain_ungranted")
    usage = {
        "scientific": False,
        "env_steps": 0,
        "env_cap": 0,
        "wall_s": clocked["wall_s"],
        "cpu_s": clocked["cpu_s"],
        "h16_scientific_ledger_untouched": True,
        "session_ledger_used_after_s": 305.842,
        "granted_7680": False,
    }
    USAGE.write_text(json.dumps(usage, indent=2) + "\n")
    return budget.write_artifact(clock=clocked, path=path)
