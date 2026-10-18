"""Development-only persist-versus-reset dry-run. Not scientific dispatch.

Reuses evolution2.methods, screen proposal contracts, TrustedEvaluator,
ReservationLedger, catalogue bindings, and synthetic tasks. Does not call
persist_reset_request.dispatch or the scientific holdout gate. Does not
collect environment steps, fit models, or debit the scientific ledger.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from nexus.evolution1.catalogue import catalogue, digest
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import fixture_checkpoint, reviewed_binding
from nexus.evolution2.methods import EvolutionarySearch, make_methods
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import FakeStepModel, decide, twelve_arm_scientific_dispatch
from nexus.evolution2.screen import ProposalRecord, feedback_event, summarize_records
from nexus.evolution2.tasks import (
    DEV_FAMILY,
    HOLDOUT_FAMILY,
    MODE,
    PROPOSALS,
    SHARED_PROBES,
    TRAIN_FAMILIES,
    hidden_score,
    make_task,
)

ROOT = Path(__file__).resolve().parents[3]
USAGE = ROOT / "artifacts" / "evolution2_persist_reset_dry_run.json"
H16 = ROOT / "artifacts" / "research_session_h16_same_state_library_usage.json"
H16_SHA = "ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117"

METHOD_KEYS = {
    "persist": "persistent_adaptive",
    "reset": "reset_adaptive",
    "random": "random",
    "evolution": "evolutionary",
}
SLOT_WORK = Work(imagined_transitions=1, model_calls=1, network_forwards=1)
CACHE_WORK = Work(imagined_transitions=1)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refuse_if_scientific() -> None:
    record = lock.allocation_record()
    if record.get("authorized") is True or int(record.get("env_cap") or 0) != 0:
        raise RuntimeError("scientific_authorization_must_use_unimplemented_dispatch")
    if lock.persist_reset_authorized(1):
        raise RuntimeError("scientific_authorization_must_use_unimplemented_dispatch")


def development_split() -> dict:
    train = tuple(make_task(name, 0) for name in TRAIN_FAMILIES)
    development = (make_task(DEV_FAMILY, 0),)
    used = train + development
    if any(task.family == HOLDOUT_FAMILY or task.role == "holdout" for task in used):
        raise RuntimeError("holdout_family_consumed")
    if any(task.role not in ("train", "development") for task in used):
        raise RuntimeError("confirmation_or_shifted_not_in_dry_run")
    if len(train) != lock.N_BUNDLES:
        raise RuntimeError("n3_train_bundle_mismatch")
    return {"train": train, "development": development}


def development_fixtures_are_not_a_holdout(tasks) -> None:
    for task in tasks:
        if task.family == HOLDOUT_FAMILY or task.role == "holdout":
            raise RuntimeError("holdout_family_consumed")
        view = task.public_view()
        if "hidden" in view or "oracle" in view:
            raise RuntimeError("hidden_weights_leaked_into_public_view")


def _phys_key(family: str, variant) -> str:
    family_key = family.replace("_", "-")
    return f"{family_key}_{variant.rule.value}_{variant.generator.value}_{variant.horizon}"


def _slot_key(method: str, phase: str, task_idx: int, slot: int) -> str:
    return f"{method}-{phase}{task_idx}-s{slot}"


def _cache_hash(method: str, task_id: str, slot: int) -> str:
    return digest({"method": method, "task": task_id, "slot": int(slot), "mode": MODE})


def checkpoint_identity() -> dict:
    rows = {}
    for family in ("pendulum", "acrobot"):
        binding = reviewed_binding(family)
        expected = fixture_checkpoint(family)
        if binding.checkpoint_id != expected:
            raise RuntimeError("checkpoint_identity_mismatch")
        rows[family] = expected
    return rows


def twelve_arm_development_bind() -> dict:
    variants = catalogue()
    if len(variants) != 12:
        raise RuntimeError("catalogue_size_mismatch")
    binding = reviewed_binding("pendulum")
    model = FakeStepModel(binding.obs_dim, binding.n_actions)
    obs = np.zeros(binding.obs_dim, dtype=np.float32)
    rows = []
    for variant in variants:
        decision = decide("pendulum", variant, obs, model, seed=0)
        rows.append(
            {
                "rule": variant.rule.value,
                "generator": variant.generator.value,
                "horizon": variant.horizon,
                "status": decision.status,
                "imagined": decision.imagined,
            }
        )
    scientific = twelve_arm_scientific_dispatch()
    return {
        "development_binding": "PASS",
        "scientific_dispatch": scientific["status"],
        "n_planner_configs": len(rows),
        "rows": rows,
        "scientific": False,
        "enabled_dispatch": False,
    }


def random_choice_sequence(seed: int, context) -> tuple[str, ...]:
    proposer = make_methods(seed)["random"]
    available = list(VARIANTS)
    chosen = []
    for _ in range(PROPOSALS):
        variant = proposer.choose(tuple(available), context)
        chosen.append(variant.fingerprint)
        available.remove(variant)
    return tuple(chosen)


def _clock_factory():
    ticks = [0]

    def read() -> Clock:
        ticks[0] += 1
        return Clock(0, ticks[0])

    return read


def _plan_operations(tasks) -> tuple[tuple[Operation, ...], Work, Work]:
    operations = []
    for task in tasks:
        for variant in VARIANTS:
            operations.append(Operation(_phys_key(task.family, variant), "model", SLOT_WORK))
        for method in METHOD_KEYS:
            for slot in range(PROPOSALS):
                phase = "tr" if task.role == "train" else "dv"
                task_idx = (
                    TRAIN_FAMILIES.index(task.family)
                    if task.role == "train"
                    else 0
                )
                operations.append(
                    Operation(
                        _slot_key(method, phase, task_idx, slot),
                        "cached",
                        CACHE_WORK,
                        cache_record_hash=_cache_hash(method, task.task_id, slot),
                    )
                )
    physical = Work()
    logical = Work()
    for operation in operations:
        physical = physical.plus(operation.physical_cost)
        logical = logical.plus(operation.cost)
    return tuple(operations), physical, logical


def _warmup_task(task, ledger, clock_read):
    def produce(variant, *, task=task, ledger=ledger, clock_read=clock_read):
        ticket = ledger.reserve(_phys_key(task.family, variant), clock_read())
        score = hidden_score(task, variant)
        ledger.settle(ticket, "success", clock_read())
        return score

    evaluator = TrustedEvaluator(
        VARIANTS,
        family=task.family,
        bundle_id=task.instance,
        produce_score=produce,
    )
    for variant in VARIANTS:
        evaluator.evaluate("warmup", variant, family=task.family, bundle_id=task.instance)
    return evaluator


def _propose_trusted(method, method_id, task, evaluator, ledger, clock_read, *,
                     phase, task_idx, apply_update, eval_mode, evolution_audit):
    available = list(VARIANTS)
    records = []
    for slot in range(PROPOSALS):
        variant = ANCHORS[slot] if slot < SHARED_PROBES else method.choose(tuple(available), task.context)
        if variant not in available:
            raise RuntimeError("duplicate_or_invalid_proposal")
        population = getattr(method, "population", None)
        if method_id == "evolution" and slot >= SHARED_PROBES and population:
            distances = [
                int(variant.rule is not parent.rule)
                + int(variant.generator is not parent.generator)
                + int(variant.horizon != parent.horizon)
                for _score, parent in population
            ]
            legal = 1 in distances
            evolution_audit.append(
                {"task": task.task_id, "slot": slot, "distances": distances, "legal": legal}
            )
            if not legal:
                raise RuntimeError("illegal_evolution_proposal")
        ticket = ledger.reserve(_slot_key(method_id, phase, task_idx, slot), clock_read())
        score = evaluator.evaluate(
            method.name,
            variant,
            family=task.family,
            bundle_id=task.instance,
        )
        event_id = feedback_event(task, slot, variant.fingerprint)
        receipt = TrainingFeedback(variant.fingerprint, score, False, event_id)
        if eval_mode:
            method.update_eval(receipt, task.context)
        elif apply_update:
            method.update(receipt, task.context)
        ledger.settle(ticket, "success", clock_read())
        records.append(
            ProposalRecord(
                task.task_id,
                slot,
                method.name,
                variant.fingerprint,
                score,
                False,
                event_id,
            )
        )
        available.remove(variant)
    return tuple(records)


def interrupted_evaluation() -> dict:
    operations = (
        Operation("interrupt-probe", "model", SLOT_WORK),
        Operation("never-started", "model", SLOT_WORK),
    )
    ledger = ReservationLedger(
        operations,
        Limits(
            Work(imagined_transitions=2, model_calls=2, network_forwards=2),
            Work(imagined_transitions=2, model_calls=2, network_forwards=2),
            10**12,
            10**12,
        ),
    )
    ticket = ledger.reserve("interrupt-probe", Clock(0, 1))
    ledger.settle(ticket, "interrupted", Clock(0, 2))
    report = ledger.close(Clock(0, 3))
    return {
        "status": report.status,
        "reason": report.reason,
        "unresolved": list(report.unresolved_keys),
        "physical_completed": report.physical_completed_reported.payload(),
        "physical_unknown": report.physical_unknown_upper_bound.payload(),
        "logical_charged": report.logical_charged.payload(),
    }


def run_development_dry_run(seed: int = 7) -> dict:
    refuse_if_scientific()
    split = development_split()
    used = split["train"] + split["development"]
    development_fixtures_are_not_a_holdout(used)
    methods = {short: make_methods(seed)[inner] for short, inner in METHOD_KEYS.items()}
    operations, physical_cap, logical_cap = _plan_operations(used)
    clock_read = _clock_factory()
    ledger = ReservationLedger(operations, Limits(physical_cap, logical_cap, 10**12, 10**12))
    evaluators = {task.task_id: _warmup_task(task, ledger, clock_read) for task in used}

    train_records = {name: [] for name in methods}
    persist_after_task = []
    reset_after_reset = []
    evolution_audit = []
    for task_idx, task in enumerate(split["train"]):
        for name, method in methods.items():
            if method.resets:
                method.reset_task()
                if name == "reset":
                    reset_after_reset.append(dict(method.learned_state()))
            rows = _propose_trusted(
                method,
                name,
                task,
                evaluators[task.task_id],
                ledger,
                clock_read,
                phase="tr",
                task_idx=task_idx,
                apply_update=True,
                eval_mode=False,
                evolution_audit=evolution_audit,
            )
            train_records[name].extend(rows)
        persist_after_task.append(dict(methods["persist"].learned_state()))

    frozen = methods["persist"].freeze()
    frozen_before_eval = dict(frozen)
    development_records = {name: [] for name in methods}
    development_summaries = {name: [] for name in methods}
    for task in split["development"]:
        for name, method in methods.items():
            actor = method.eval_clone(local_updates=False)
            rows = _propose_trusted(
                actor,
                name,
                task,
                evaluators[task.task_id],
                ledger,
                clock_read,
                phase="dv",
                task_idx=0,
                apply_update=False,
                eval_mode=True,
                evolution_audit=evolution_audit,
            )
            development_records[name].extend(rows)
            development_summaries[name].append(summarize_records(rows, task))

    if methods["persist"].learned_state()["weights"] != frozen_before_eval["weights"]:
        raise RuntimeError("global_weights_mutated_during_eval")
    closed = ledger.close(clock_read())
    if closed.status != "complete_execution":
        raise RuntimeError("ledger_incomplete")

    lookups = {
        name: len(train_records[name]) + len(development_records[name]) for name in methods
    }
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
    expected = (len(split["train"]) + len(split["development"])) * PROPOSALS
    if any(count != expected for count in lookups.values()):
        raise RuntimeError("unequal_proposal_budget")

    ctx = split["train"][0].context
    random_a = random_choice_sequence(7, ctx)
    random_b = random_choice_sequence(11, ctx)
    if random_a == random_b:
        raise RuntimeError("random_states_not_independent")
    if random_choice_sequence(7, ctx) != random_a:
        raise RuntimeError("random_same_seed_mismatch")

    evo = EvolutionarySearch(seed=seed)
    try:
        evo._crossover()
    except Exception as exc:
        crossover = str(exc)
    else:
        raise RuntimeError("crossover_must_remain_illegal")
    if "crossover_is_illegal" not in crossover:
        raise RuntimeError("crossover_must_remain_illegal")

    evaluator_physical = sum(item.physical for item in evaluators.values())
    evaluator_cached = sum(item.cached for item in evaluators.values())
    twelve_arm = twelve_arm_development_bind()
    identity = checkpoint_identity()
    interruption = interrupted_evaluation()
    if file_sha256(H16) != H16_SHA:
        raise RuntimeError("h16_scientific_ledger_mutated")

    payload = {
        "scientific": False,
        "collection": False,
        "gymnasium": False,
        "training": False,
        "hold_named": False,
        "status": "development_dry_run_pass",
        "dry_run": "PASS",
        "methods_exercised": list(METHOD_KEYS),
        "all_four_methods_exercised": True,
        "n_train_tasks": len(split["train"]),
        "n_development_tasks": len(split["development"]),
        "matched_proposals": PROPOSALS,
        "lookups_per_method": lookups,
        "equal_budget": True,
        "leakage_audit": "PASS",
        "persist_cross_task": {
            "updates": persist_after_task[-1]["updates"],
            "weights_changed": persist_after_task[0]["weights"] != persist_after_task[-1]["weights"],
            "frozen_updates": frozen_before_eval["updates"],
        },
        "reset_genuine": {
            "after_reset_updates": [row["updates"] for row in reset_after_reset],
            "after_reset_zero_weights": all(
                row["weights"] == (0.0,) * 6 for row in reset_after_reset
            ),
        },
        "random_independent": random_a != random_b,
        "evolution_legal": all(row["legal"] for row in evolution_audit),
        "crossover_illegal": True,
        "checkpoint_identity": identity,
        "hidden_feedback_isolated": True,
        "evaluator_physical": evaluator_physical,
        "evaluator_cached": evaluator_cached,
        "ledger": {
            "status": closed.status,
            "physical": closed.physical_completed_reported.payload(),
            "logical": closed.logical_charged.payload(),
            "physical_unknown": closed.physical_unknown_upper_bound.payload(),
        },
        "interruption": interruption,
        "twelve_arm_dispatch": twelve_arm["development_binding"],
        "twelve_arm_scientific": twelve_arm["scientific_dispatch"],
        "scientific_execution": "BLOCKED",
        "science_runner": lock.SCIENCE_RUNNER,
        "bonferroni_comparisons_locked": 5,
        "listed_controls": 3,
        "bonferroni_conservatism": lock.BONFERRONI_NOTE,
        "bonferroni_t_crit": lock.worksheet()["bonferroni_t_crit"],
        "holdout_consumed": False,
        "h16_scientific_ledger_untouched": True,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "development_summaries": development_summaries,
        "claims_learning_to_learn": False,
        "is_agi": False,
        "enabled_dispatch": False,
        "twenty_fit_measured": False,
    }
    USAGE.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload
