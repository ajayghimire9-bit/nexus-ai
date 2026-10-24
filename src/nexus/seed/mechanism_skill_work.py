"""Sub-clause skill transfer that must cut total acquisition work.

Freezes the f2e8942 adaptive policy. Wave-1 verified acquisitions
index guard/transform sub-clauses. Wave-2 whole-mechanism cache is
expected to miss. Opened prior IDs are not rescored.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_acquire import ACQUIRE_STOPS, _with_stops, fit_acquire, zero_acquire
from .mechanism_claims import score_claims
from .mechanism_investigate import FEATURE_NAMES, HIDDEN
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash
from .mechanism_policy_replication import (
    FAMILY_X, FAMILY_Y, FIRST_PROBE, HYPOTHESIS_BANK, OPENED_IDS as PRIOR_OPENED,
    TRACK_B_CLOSED, WorkMeter, _choose, _shuffle_source, adaptive_available,
    apply_candidate, bank_features, bank_training_rows, distill_order,
    observational_groups, probe_splits, run_bank_holdout, run_method,
)
from .mechanism_skills import SubMechanismLibrary
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_world import ACTIONS, MAX_STEPS, apply_hidden, blank_state, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_unfamiliar_skill_work_reduction"
PRIOR_CLOSED = (
    "92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01", "f2e8942",
)
OPENED_IDS = set(PRIOR_OPENED)
METHODS = (
    "untrained_policy_no_memory",
    "source_distilled_fixed_no_memory",
    "learned_adaptive_policy_memory_cleared",
    "learned_adaptive_policy_plus_subskill_memory",
)
CLEARED_TO_FROZEN = {
    "untrained_policy_no_memory": "untrained_default_policy",
    "source_distilled_fixed_no_memory": "source_distilled_fixed_order",
    "learned_adaptive_policy_memory_cleared": "source_learned_adaptive_policy",
}
POS_SIGNATURE = "1,0"
NEG_SIGNATURE = "0,1"
HOLDOUT_ENV_TARGET = 21
HOLDOUT_POLICY_TARGET = 246
HOLDOUT_CLEARED_WORK = 699


def filter_named_bank(transcript: list[dict[str, Any]], bank: tuple[str, ...] | list[str],
                      meter: WorkMeter | None = None) -> list[str]:
    remain = []
    evals = 0
    for name in bank:
        state = dict(s=0, prev=0)
        ok = True
        for row in transcript:
            action = row["action"]
            if str(action).startswith("STOP"):
                continue
            applied = apply_candidate(name, state, action)
            evals += 1
            state = applied["state"]
            if applied["observation"] is None:
                continue
            if int(row["observation"]) != int(applied["observation"]):
                ok = False
                break
        if ok:
            remain.append(name)
    if meter is not None:
        meter.hypothesis_evals += evals
    return remain


def branch_signature(transcript: list[dict[str, Any]], remaining: list[str]) -> str | None:
    if not remaining or not any(row.get("observation") is not None for row in transcript):
        return None
    x_inf = bool(probe_splits(remaining, transcript, FAMILY_X)["informative"])
    y_inf = bool(probe_splits(remaining, transcript, FAMILY_Y)["informative"])
    if x_inf and not y_inf:
        return POS_SIGNATURE
    if y_inf and not x_inf:
        return NEG_SIGNATURE
    return "{0},{1}".format(int(x_inf), int(y_inf))


def hyp_family_signature(name: str) -> str | None:
    y1 = apply_candidate(name, dict(s=0, prev=0), FIRST_PROBE)["observation"]
    prefix = [dict(action=FIRST_PROBE, observation=y1)]
    remain = []
    for other in HYPOTHESIS_BANK:
        pred = apply_candidate(other, dict(s=0, prev=0), FIRST_PROBE)["observation"]
        if pred == y1:
            remain.append(other)
    return branch_signature(prefix, remain)


FAMILY_INDEX = {name: hyp_family_signature(name) for name in HYPOTHESIS_BANK}


def compatible_names(signature: str) -> list[str]:
    return [name for name, key in FAMILY_INDEX.items() if key == signature]


def decompose_verified(episode: dict[str, Any]) -> dict[str, Any] | None:
    name = episode.get("mechanism")
    if not name:
        return None
    y1 = apply_candidate(name, dict(s=0, prev=0), FIRST_PROBE)["observation"]
    prefix = [dict(action=FIRST_PROBE, observation=y1)]
    remain = [
        other for other in HYPOTHESIS_BANK
        if apply_candidate(other, dict(s=0, prev=0), FIRST_PROBE)["observation"] == y1
    ]
    signature = branch_signature(prefix, remain)
    if signature not in (POS_SIGNATURE, NEG_SIGNATURE):
        return None
    clause = "pos_guard_or_leaf" if signature == POS_SIGNATURE else "neg_guard_or_leaf"
    return dict(
        source_mechanism=name,
        source_task=episode["task_id"],
        signature=signature,
        clause=clause,
        first_probe=FIRST_PROBE,
        first_observation=y1,
        kind="branch_or_transform",
    )


class SkillWorkMeter(WorkMeter):
    def __init__(self) -> None:
        super().__init__()
        self.retrieval_evals = 0

    def as_dict(self) -> dict[str, int]:
        return dict(
            env_interactions=int(self.env_interactions),
            hypothesis_evals=int(self.hypothesis_evals),
            probe_feature_and_policy_evals=int(self.probe_feature_and_policy_evals),
            policy_evals=int(self.probe_feature_and_policy_evals),
            retrieval_evals=int(self.retrieval_evals),
            total_acquisition_work=int(self.total_acquisition_work),
        )

    @property
    def total_acquisition_work(self) -> int:
        return (
            int(self.env_interactions)
            + int(self.hypothesis_evals)
            + int(self.probe_feature_and_policy_evals)
            + int(self.retrieval_evals)
        )


def populate_library(source_rows: list[dict[str, Any]]) -> SubMechanismLibrary:
    library = SubMechanismLibrary()
    for episode in source_rows:
        if not episode.get("useful_acquisition"):
            continue
        library.remember_whole(episode["mechanism"], episode.get("transcript") or [])
        clause = decompose_verified(episode)
        if clause:
            library.remember_subclause(clause)
    return library


def run_memory_episode(task: dict[str, Any], weights: dict[str, list[float]],
                       order: list[str], rng: random.Random,
                       library: SubMechanismLibrary) -> dict[str, Any]:
    meter = SkillWorkMeter()
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    stopped = None
    identified = None
    bank: list[str] = list(HYPOTHESIS_BANK)
    whole_hits = 0
    sub_hits = 0
    retrieved = False
    for step in range(MAX_STEPS):
        policy_remain = filter_named_bank(transcript, HYPOTHESIS_BANK)
        remaining = filter_named_bank(transcript, bank, meter)
        feats = bank_features(transcript, policy_remain, MAX_STEPS - step, meter)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        available = adaptive_available(transcript, policy_remain)
        choice = _choose(
            "source_learned_adaptive_policy", policy_remain, available, transcript,
            feats, weights, order, rng, meter,
        )
        action = choice["action"]
        if action not in available:
            raise ValueError("chose_unavailable:" + action)
        if action in ACQUIRE_STOPS:
            stopped = action
            if action == "STOP_IDENTIFY" and len(remaining) == 1:
                identified = remaining[0]
            transcript.append(dict(
                action=action, observation=None, remaining=list(remaining),
                features=feats, reason=choice.get("reason"),
            ))
            break
        applied = apply_hidden(task["mechanism"], hidden, action)
        hidden = applied["state"]
        meter.env_interactions += 1
        transcript.append(dict(
            action=action, observation=applied["observation"],
            remaining=list(remaining), features=feats, reason=choice.get("reason"),
        ))
        if not retrieved and meter.env_interactions >= 1:
            before = library.retrieval_evals
            whole = library.lookup_whole(transcript)
            observed = filter_named_bank(transcript, HYPOTHESIS_BANK)
            families = {
                FAMILY_INDEX[name] for name in observed
                if FAMILY_INDEX.get(name) in (POS_SIGNATURE, NEG_SIGNATURE)
            }
            signature = next(iter(families)) if len(families) == 1 else None
            clauses = library.lookup_subclause(signature or "")
            meter.retrieval_evals += library.retrieval_evals - before
            if whole:
                whole_hits += 1
            if clauses and signature:
                sub_hits += 1
                bank = sorted(set(compatible_names(str(signature))) | set(observed))
            retrieved = True
    else:
        stopped = "budget"
    remaining = filter_named_bank(transcript, bank, meter)
    groups = observational_groups(remaining)
    representative = groups[0][0] if len(groups) == 1 else None
    holdout = run_bank_holdout(task, representative)
    synthesized = dict(
        remaining=list(remaining),
        classes=groups,
        representative=representative,
        n_remaining=len(remaining),
        n_classes=len(groups),
        retrieved_bank=list(bank),
    )
    claims = score_claims(task, remaining, synthesized, identified, stopped, holdout)
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        role=task.get("role"),
        method="learned_adaptive_policy_plus_subskill_memory",
        transcript=transcript,
        synthesized=synthesized,
        holdout=holdout,
        stopped=stopped,
        identified=identified,
        remaining=list(remaining),
        memory_cleared=False,
        retrieve=True,
        remember=False,
        memory_updated=False,
        policy_updated=False,
        skill_memory_paused=False,
        track_b_closed=TRACK_B_CLOSED,
        whole_mechanism_hits=whole_hits,
        subclause_hits=sub_hits,
        instance_seed=task["instance_seed"],
        language_hash=language_hash(),
        **work,
        **claims,
    )


def _relabel(row: dict[str, Any], method: str) -> dict[str, Any]:
    out = dict(row)
    out["method"] = method
    out.setdefault("retrieval_evals", 0)
    out.setdefault("whole_mechanism_hits", 0)
    out.setdefault("subclause_hits", 0)
    out["total_acquisition_work"] = (
        int(out.get("env_interactions") or 0)
        + int(out.get("hypothesis_evals") or 0)
        + int(out.get("probe_feature_and_policy_evals") or 0)
        + int(out.get("retrieval_evals") or 0)
    )
    return out


def _method_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, useful_acquisition=0, predictive_competence=0,
            exact_mechanism_identification=0,
            env_interactions=0, hypothesis_evals=0,
            probe_feature_and_policy_evals=0, retrieval_evals=0,
            total_acquisition_work=0, whole_mechanism_hits=0, subclause_hits=0,
        ))
        cell["n"] += 1
        for key in ("useful_acquisition", "predictive_competence", "exact_mechanism_identification"):
            cell[key] += int(bool(row.get(key)))
        for key in (
            "env_interactions", "hypothesis_evals", "probe_feature_and_policy_evals",
            "retrieval_evals", "total_acquisition_work", "whole_mechanism_hits", "subclause_hits",
        ):
            cell[key] += int(row.get(key) or 0)
    return out


def reconstruct_work(episode: dict[str, Any], library: SubMechanismLibrary | None = None) -> dict[str, int]:
    if episode["method"] != "learned_adaptive_policy_plus_subskill_memory":
        from .mechanism_policy_replication import reconstruct_work as frozen_reconstruct
        rebuilt = frozen_reconstruct(dict(episode, method=CLEARED_TO_FROZEN.get(episode["method"], episode["method"])))
        rebuilt["retrieval_evals"] = int(episode.get("retrieval_evals") or 0)
        rebuilt["total_acquisition_work"] = (
            rebuilt["env_interactions"] + rebuilt["hypothesis_evals"]
            + rebuilt["probe_feature_and_policy_evals"] + rebuilt["retrieval_evals"]
        )
        return rebuilt
    meter = SkillWorkMeter()
    prefix: list[dict[str, Any]] = []
    bank: list[str] = list(HYPOTHESIS_BANK)
    local = SubMechanismLibrary()
    if library is not None:
        for clause in library.clauses:
            local.remember_subclause(clause)
        local.exact = library.exact
    retrieved = False
    for step in episode.get("transcript") or []:
        policy_remain = filter_named_bank(prefix, HYPOTHESIS_BANK)
        remaining = filter_named_bank(prefix, bank, meter)
        bank_features(prefix, policy_remain, MAX_STEPS - len(prefix), meter)
        available = adaptive_available(prefix, policy_remain)
        meter.probe_feature_and_policy_evals += len(available)
        if not str(step["action"]).startswith("STOP"):
            meter.env_interactions += 1
        prefix.append(step)
        if (
            library is not None
            and not retrieved
            and not str(step["action"]).startswith("STOP")
            and meter.env_interactions >= 1
        ):
            before = local.retrieval_evals
            local.lookup_whole(prefix)
            observed = filter_named_bank(prefix, HYPOTHESIS_BANK)
            families = {
                FAMILY_INDEX[name] for name in observed
                if FAMILY_INDEX.get(name) in (POS_SIGNATURE, NEG_SIGNATURE)
            }
            signature = next(iter(families)) if len(families) == 1 else None
            clauses = local.lookup_subclause(signature or "")
            meter.retrieval_evals += local.retrieval_evals - before
            if clauses and signature:
                bank = sorted(set(compatible_names(str(signature))) | set(observed))
            retrieved = True
    filter_named_bank(prefix, bank, meter)
    return meter.as_dict()


def evaluate_gates(seed_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    gate1 = True
    gate2 = True
    gate3 = True
    for block in seed_blocks:
        totals = block["assessment_totals"]
        retain = block["retain_totals"]
        useful = [int((totals.get(name) or {}).get("useful_acquisition") or -1) for name in METHODS]
        pred = [int((totals.get(name) or {}).get("predictive_competence") or -1) for name in METHODS]
        r_useful = [int((retain.get(name) or {}).get("useful_acquisition") or -1) for name in METHODS]
        if not (useful[0] == useful[1] == useful[2] == useful[3] == 4):
            gate1 = False
            notes.append("gate1_holdout_seed_{0}".format(block["seed"]))
        if not (pred[0] == pred[1] == pred[2] == pred[3] == 4):
            gate1 = False
            notes.append("gate1_pred_seed_{0}".format(block["seed"]))
        if not (r_useful[0] == r_useful[1] == r_useful[2] == r_useful[3] == 2):
            gate1 = False
            notes.append("gate1_retain_seed_{0}".format(block["seed"]))
        memory = totals.get("learned_adaptive_policy_plus_subskill_memory") or {}
        if int(memory.get("whole_mechanism_hits") or 0) != 0:
            gate2 = False
            notes.append("gate2_whole_hit_seed_{0}".format(block["seed"]))
        if int(memory.get("subclause_hits") or 0) <= 0:
            gate2 = False
            notes.append("gate2_no_sub_hit_seed_{0}".format(block["seed"]))
        cleared = totals.get("learned_adaptive_policy_memory_cleared") or {}
        if int(memory.get("total_acquisition_work") or 10**9) >= int(cleared.get("total_acquisition_work") or 0):
            gate3 = False
            notes.append("gate3_seed_{0}".format(block["seed"]))
    return dict(
        gate1_accuracy_retention_parity=gate1,
        gate2_nonzero_subclause_zero_whole=gate2,
        gate3_net_total_work_reduction=gate3,
        passed=bool(gate1 and gate2 and gate3),
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed", row.get("policy_seed")),
            task_id=row["task_id"],
            split=row["split"],
            mechanism=row["mechanism"],
            method=row["method"],
            env_interactions=int(row["env_interactions"]),
            hypothesis_evals=int(row["hypothesis_evals"]),
            policy_evals=int(row.get("probe_feature_and_policy_evals") or 0),
            retrieval_evals=int(row.get("retrieval_evals") or 0),
            total_acquisition_work=int(row["total_acquisition_work"]),
            whole_mechanism_hits=int(row.get("whole_mechanism_hits") or 0),
            subclause_hits=int(row.get("subclause_hits") or 0),
            solved=bool(row.get("useful_acquisition")),
            retained=bool(row.get("useful_acquisition")) if row.get("split") == "up_retain" else None,
        )
        for row in rows
    ]


def run_skill_work(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = unfamiliar_policy_tasks("up_source")
    holdout = unfamiliar_policy_tasks("up_holdout")
    retain = unfamiliar_policy_tasks("up_retain")
    if any(row["task_id"] in OPENED_IDS for row in source + holdout + retain):
        raise ValueError("opened_id_in_challenge")
    seed_blocks = []
    assessment_rows: list[dict[str, Any]] = []
    for seed in TRAIN_SEEDS:
        from .mechanism_policy_replication import DIAGNOSTIC_ORDER
        ordered = _shuffle_source(source, seed)
        teacher = run_method(ordered, "bank_ig", zero_acquire(), list(DIAGNOSTIC_ORDER), seed=5 + seed)
        supervised = []
        for episode in teacher:
            supervised.extend(bank_training_rows(episode))
        weights = fit_acquire(supervised)
        own = run_method(
            ordered, "source_learned_adaptive_policy", _with_stops(weights),
            list(DIAGNOSTIC_ORDER), seed=30 + seed,
        )
        for episode in own:
            supervised.extend(bank_training_rows(episode))
        weights = fit_acquire(supervised)
        frozen = policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS})
        order = distill_order(teacher)
        library = populate_library(own)
        hold_rows = []
        retain_rows = []
        for public, frozen_name in CLEARED_TO_FROZEN.items():
            used = zero_acquire() if "learned" not in public else _with_stops(weights)
            for row in run_method(holdout, frozen_name, used, order, seed=80 + seed):
                hold_rows.append(dict(_relabel(row, public), source_seed=seed))
            for row in run_method(retain, frozen_name, used, order, seed=90 + seed):
                retain_rows.append(dict(_relabel(row, public), source_seed=seed))
        for index, task in enumerate(holdout):
            rng = random.Random((80 + seed) * 1009 + index * 17 + 11)
            episode = run_memory_episode(task, _with_stops(weights), order, rng, library)
            episode["source_seed"] = seed
            episode["policy_seed"] = 80 + seed
            hold_rows.append(episode)
        for index, task in enumerate(retain):
            rng = random.Random((90 + seed) * 1009 + index * 17 + 11)
            episode = run_memory_episode(task, _with_stops(weights), order, rng, library)
            episode["source_seed"] = seed
            episode["policy_seed"] = 90 + seed
            retain_rows.append(episode)
        assessment_rows.extend(hold_rows)
        assessment_rows.extend(retain_rows)
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=frozen,
            distilled_order=list(order),
            library=library.snapshot(),
            holdout=hold_rows,
            retain=retain_rows,
            assessment_totals=_method_totals(hold_rows),
            retain_totals=_method_totals(retain_rows),
        ))
    gates = evaluate_gates(seed_blocks)
    holdout_only = [row for row in assessment_rows if row["split"] == "up_holdout"]
    retain_only = [row for row in assessment_rows if row["split"] == "up_retain"]
    usage = dict(
        kind=KIND,
        elapsed_s=time.perf_counter() - started,
        model_calls=0,
        metal_used=False,
        frozen_debit_s=0,
        research_cpu_ledger_debit_s=0,
        frozen_cpu_used_s=FROZEN_CPU_USED_S,
        frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
        rss=sample_process_memory(),
        track_b_closed=TRACK_B_CLOSED,
        f2e8942_artifact="6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff",
    )
    payload = dict(
        kind=KIND,
        prior_closed=list(PRIOR_CLOSED),
        confirmation=False,
        learning_to_learn_established=False,
        open_domain_coding_established=False,
        track_b_closed=TRACK_B_CLOSED,
        methods=list(METHODS),
        seeds=list(TRAIN_SEEDS),
        assessment=assessment_rows,
        seed_blocks=[{k: block[k] for k in (
            "seed", "policy_hash", "distilled_order", "library",
            "assessment_totals", "retain_totals",
        )} for block in seed_blocks],
        per_task=per_task_rows(assessment_rows),
        totals=dict(holdout=_method_totals(holdout_only), retain=_method_totals(retain_only)),
        gates=gates,
        usage=usage,
        language_hash=language_hash(),
    )
    payload["hash"] = digest({
        key: payload[key] for key in ("kind", "assessment", "totals", "gates")
    })
    (directory / "seed_unfamiliar_skill_work_reduction.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    if payload.get("learning_to_learn_established") or payload.get("open_domain_coding_established"):
        ok = False
        notes.append("overclaim")
    if not payload.get("track_b_closed"):
        ok = False
        notes.append("track_b_open")
    rows = list(payload.get("assessment") or [])
    if any(row["task_id"] in OPENED_IDS for row in rows):
        ok = False
        notes.append("rescored_opened")
    if any(row.get("exact_mechanism_identification") for row in rows):
        ok = False
        notes.append("exact_claimed")
    rebuilt = _method_totals([row for row in rows if row.get("split") == "up_holdout"])
    saved = (payload.get("totals") or {}).get("holdout") or {}
    for name, cell in rebuilt.items():
        other = saved.get(name) or {}
        for key in ("useful_acquisition", "env_interactions", "total_acquisition_work", "retrieval_evals"):
            if cell.get(key) != other.get(key):
                ok = False
                notes.append("column:" + name + ":" + key)
    libraries = {
        block["seed"]: _library_from_snapshot(block.get("library") or {})
        for block in payload.get("seed_blocks") or []
    }
    for row in rows:
        seed = row.get("source_seed")
        reconstructed = reconstruct_work(row, libraries.get(seed))
        for key in (
            "env_interactions", "hypothesis_evals", "probe_feature_and_policy_evals",
            "retrieval_evals", "total_acquisition_work",
        ):
            if reconstructed.get(key) != row.get(key):
                ok = False
                notes.append("reconstruct:" + row["task_id"] + ":" + row["method"] + ":" + key)
                break
    cleared = saved.get("learned_adaptive_policy_memory_cleared") or {}
    if int(cleared.get("env_interactions") or 0) != HOLDOUT_ENV_TARGET:
        ok = False
        notes.append("cleared_env_changed")
    if int(cleared.get("probe_feature_and_policy_evals") or 0) != HOLDOUT_POLICY_TARGET:
        ok = False
        notes.append("cleared_policy_changed")
    if int(cleared.get("total_acquisition_work") or 0) != HOLDOUT_CLEARED_WORK:
        ok = False
        notes.append("cleared_work_changed")
    memory = saved.get("learned_adaptive_policy_plus_subskill_memory") or {}
    if int(memory.get("env_interactions") or 0) != HOLDOUT_ENV_TARGET:
        ok = False
        notes.append("memory_env_changed")
    if int(memory.get("probe_feature_and_policy_evals") or 0) != HOLDOUT_POLICY_TARGET:
        ok = False
        notes.append("memory_policy_changed")
    gates = evaluate_gates(list(payload.get("seed_blocks") or []))
    saved_gates = payload.get("gates") or {}
    for key in (
        "gate1_accuracy_retention_parity",
        "gate2_nonzero_subclause_zero_whole",
        "gate3_net_total_work_reduction",
        "passed",
    ):
        if gates.get(key) != saved_gates.get(key):
            ok = False
            notes.append("gates:" + key)
    if not saved_gates.get("passed"):
        ok = False
        notes.append("gates_failed")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)


def _library_from_snapshot(snapshot: dict[str, Any]) -> SubMechanismLibrary:
    library = SubMechanismLibrary()
    for clause in snapshot.get("clauses") or []:
        library.remember_subclause(clause)
        evidence = clause.get("evidence")
        if evidence and clause.get("source_mechanism"):
            library.remember_whole(clause["source_mechanism"], [
                dict(action=a, observation=y) for a, y in evidence
            ])
    return library
