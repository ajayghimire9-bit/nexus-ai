"""Independent policy-only replication of unfamiliar-mechanism acquisition.

Freezes the continual source-trained linear policy (fit_acquire /
select_action). Adds a source-distilled static probe order. Skill
memory stays cleared. Track B stays closed. Opened prior IDs are not
rescored.
"""
from __future__ import annotations

import json
import math
import random
import time
from typing import Any

from .capability_evidence import digest
from .mechanism_acquire import ACQUIRE_STOPS, _with_stops, fit_acquire, zero_acquire
from .mechanism_claims import score_claims
from .mechanism_compose import HOLDOUT_PROBES
from .mechanism_investigate import (
    DIAGNOSTIC_ORDER, FEATURE_NAMES, HIDDEN, QUERY_ACTIONS, REDUNDANT_MASK_ORIGIN,
    feature_vector, used_since_reset,
)
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash, select_action
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_world import (
    ACTION_COST, ACTIONS, ACT_INPUTS, EXECUTORS, LANGUAGE, MAX_STEPS,
    apply_hidden, blank_state, language_hash,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_unfamiliar_policy_replication"
PRIOR_CLOSED = ("92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01")
OPENED_IDS = {
    "c_add4", "c_count2", "d_add_mul", "d_count_add", "e_delay", "e_threshold",
    "mm_abs", "mm_mod3", "mm_clip0", "mm_prev", "ctl_neg", "ctl_toggle",
    "vp_id0", "vp_mod2", "vp_plus", "vp_twin", "vp_add2", "vp_neg", "vp_count",
    "acq_gate_mul_add", "acq_gate_add_neg", "acq_gate_neg_add",
    "acq_hold_add2_mul", "acq_hold_neg_add2", "acq_hold_mul_neg",
    "w1_add1", "w1_mul2", "w1_if_pos", "w1_sat_inc",
    "w1d_add2", "w1d_neg", "w1d_if_neg", "w1d_sat_dec",
    "w2_if_pos_add1", "w2_sat_inc_mul2", "w2_if_neg_neg", "w2_sign_pos",
    "w3_add1_if_pos", "w3r_add1", "w3r_if_pos", "w3r_sat_inc",
}
METHODS = (
    "untrained_default_policy",
    "source_distilled_fixed_order",
    "source_learned_adaptive_policy",
)
HYPOTHESIS_BANK = (
    "add1", "mul2", "if_pos", "sat_inc",
    "up_src_pos_plus", "up_src_twice_pos",
    "up_src_neg_id", "up_src_neg_dbl",
    "up_pos_plus2", "up_twice_plus1",
    "up_neg_gate", "up_neg_twice",
)
FIRST_PROBE = "ACT_1"
FAMILY_X = "ACT_2"
FAMILY_Y = "ACT_NEG"
BRANCH_A_Y1 = 3
BRANCH_B_Y1 = 0
MEMORY_CLEARED = True
TRACK_B_CLOSED = True
SKILL_MEMORY_PAUSED = True


class WorkMeter:
    def __init__(self) -> None:
        self.env_interactions = 0
        self.hypothesis_evals = 0
        self.probe_feature_and_policy_evals = 0

    def add(self, other: "WorkMeter") -> "WorkMeter":
        merged = WorkMeter()
        merged.env_interactions = self.env_interactions + other.env_interactions
        merged.hypothesis_evals = self.hypothesis_evals + other.hypothesis_evals
        merged.probe_feature_and_policy_evals = (
            self.probe_feature_and_policy_evals + other.probe_feature_and_policy_evals
        )
        return merged

    def as_dict(self) -> dict[str, int]:
        return dict(
            env_interactions=int(self.env_interactions),
            hypothesis_evals=int(self.hypothesis_evals),
            probe_feature_and_policy_evals=int(self.probe_feature_and_policy_evals),
            policy_evals=int(self.probe_feature_and_policy_evals),
            total_acquisition_work=int(self.total_acquisition_work),
        )

    @property
    def total_acquisition_work(self) -> int:
        return (
            int(self.env_interactions)
            + int(self.hypothesis_evals)
            + int(self.probe_feature_and_policy_evals)
        )


def apply_candidate(name: str, state: dict[str, Any], action: str) -> dict[str, Any]:
    nxt = dict(s=int(state.get("s") or 0), prev=int(state.get("prev") or 0))
    if action == "RESET":
        return dict(state=dict(s=0, prev=0), observation=None)
    if name not in EXECUTORS:
        raise ValueError("unknown_hypothesis:" + name)
    if action == "MEASURE":
        y = EXECUTORS[name](nxt, 0, True)
        return dict(state=nxt, observation=int(y))
    if action in ACT_INPUTS:
        y = EXECUTORS[name](nxt, ACT_INPUTS[action], True)
        return dict(state=nxt, observation=int(y))
    raise ValueError("not_an_environment_action")


def filter_bank(transcript: list[dict[str, Any]], meter: WorkMeter | None = None) -> list[str]:
    remain = []
    evals = 0
    for name in HYPOTHESIS_BANK:
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


def bank_signature(name: str) -> tuple[tuple[str, int | None], ...]:
    state = dict(s=0, prev=0)
    rows = []
    for action in HOLDOUT_PROBES:
        applied = apply_candidate(name, state, action)
        state = applied["state"]
        rows.append((action, applied["observation"]))
    return tuple(rows)


def observational_groups(remaining: list[str]) -> list[list[str]]:
    groups: dict[Any, list[str]] = {}
    for name in remaining:
        groups.setdefault(bank_signature(name), []).append(name)
    return list(groups.values())


def predict_next(name: str, transcript: list[dict[str, Any]], action: str) -> int | None:
    state = dict(s=0, prev=0)
    for row in transcript:
        if str(row["action"]).startswith("STOP"):
            continue
        applied = apply_candidate(name, state, row["action"])
        state = applied["state"]
    applied = apply_candidate(name, state, action)
    return applied["observation"]


def probe_splits(remaining: list[str], transcript: list[dict[str, Any]],
                 action: str) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for name in remaining:
        predicted = predict_next(name, transcript, action)
        key = "none" if predicted is None else str(predicted)
        groups.setdefault(key, []).append(name)
    informative = bool(remaining) and len(groups) > 1
    return dict(informative=informative, n_groups=len(groups), groups=groups)


def branch_property() -> dict[str, Any]:
    prefix_a = [dict(action=FIRST_PROBE, observation=BRANCH_A_Y1)]
    prefix_b = [dict(action=FIRST_PROBE, observation=BRANCH_B_Y1)]
    remain_a = filter_bank(prefix_a)
    remain_b = filter_bank(prefix_b)
    split_a_x = probe_splits(remain_a, prefix_a, FAMILY_X)
    split_a_y = probe_splits(remain_a, prefix_a, FAMILY_Y)
    split_b_x = probe_splits(remain_b, prefix_b, FAMILY_X)
    split_b_y = probe_splits(remain_b, prefix_b, FAMILY_Y)
    return dict(
        first_probe=FIRST_PROBE,
        family_x=FAMILY_X,
        family_y=FAMILY_Y,
        branch_a=dict(
            y1=BRANCH_A_Y1,
            remaining=list(remain_a),
            family_x_informative=bool(split_a_x["informative"]),
            family_y_splits=int(split_a_y["n_groups"]),
            family_y_redundant=not bool(split_a_y["informative"]),
        ),
        branch_b=dict(
            y1=BRANCH_B_Y1,
            remaining=list(remain_b),
            family_y_informative=bool(split_b_y["informative"]),
            family_x_splits=int(split_b_x["n_groups"]),
            family_x_redundant=not bool(split_b_x["informative"]),
        ),
        holds=bool(
            remain_a
            and remain_b
            and set(remain_a).isdisjoint(remain_b)
            and split_a_x["informative"]
            and not split_a_y["informative"]
            and split_b_y["informative"]
            and not split_b_x["informative"]
        ),
    )


def bank_features(transcript: list[dict[str, Any]], remaining: list[str],
                  steps_left: int, meter: WorkMeter | None = None) -> dict[str, float]:
    last = next((row for row in reversed(transcript) if row.get("observation") is not None), None)
    last_y = None if last is None else int(last["observation"])
    last_act = transcript[-1]["action"] if transcript else None
    n = max(len(HYPOTHESIS_BANK), 1)
    feats = dict(
        n_remaining_frac=len(remaining) / float(n),
        n_remaining=float(len(remaining)),
        log_remaining=math.log2(len(remaining) + 1),
        n_actions=float(len(transcript)),
        budget_left_frac=steps_left / float(MAX_STEPS),
        vs_empty=float(not remaining),
        vs_singleton=float(len(remaining) == 1),
        identification_supported=0.0,
        last_obs_scaled=0.0 if last_y is None else max(-8, min(8, last_y)) / 8.0,
        last_obs_missing=float(last_y is None),
    )
    for action in QUERY_ACTIONS:
        scored = probe_splits(remaining, transcript, action)
        feats[f"used_{action}"] = float(used_since_reset(transcript, action))
        feats[f"informative_{action}"] = float(bool(scored["informative"]))
        feats[f"last_{action}"] = float(last_act == action)
    if meter is not None:
        meter.probe_feature_and_policy_evals += 1
    return feats


def static_available(transcript: list[dict[str, Any]], remaining: list[str]) -> list[str]:
    kept = [action for action in QUERY_ACTIONS if not used_since_reset(transcript, action)]
    kept.append("STOP_UNRESOLVED")
    if remaining and len(observational_groups(remaining)) == 1:
        kept.append("STOP_EQUIVALENT")
    if len(remaining) == 1 and remaining[0] in LANGUAGE:
        kept.append("STOP_IDENTIFY")
    return kept


def adaptive_available(transcript: list[dict[str, Any]], remaining: list[str]) -> list[str]:
    kept = []
    for action in QUERY_ACTIONS:
        if action == "RESET":
            kept.append(action)
            continue
        if used_since_reset(transcript, action) and not probe_splits(
            remaining, transcript, action
        )["informative"]:
            continue
        if not remaining:
            continue
        kept.append(action)
    kept.append("STOP_UNRESOLVED")
    if remaining and len(observational_groups(remaining)) == 1:
        kept.append("STOP_EQUIVALENT")
    if len(remaining) == 1 and remaining[0] in LANGUAGE:
        kept.append("STOP_IDENTIFY")
    return kept


def _stop_if_resolved(remaining: list[str], available: list[str]) -> dict[str, Any] | None:
    if not remaining:
        return dict(action="STOP_UNRESOLVED", reason="bank_empty")
    if len(observational_groups(remaining)) == 1 and "STOP_EQUIVALENT" in available:
        return dict(action="STOP_EQUIVALENT", reason="one_class")
    return None


def choose_untrained_default(remaining: list[str], available: list[str]) -> dict[str, Any]:
    stopped = _stop_if_resolved(remaining, available)
    if stopped:
        return stopped
    for action in DIAGNOSTIC_ORDER:
        if action in available:
            return dict(action=action, reason="untrained_default")
    return dict(
        action="STOP_EQUIVALENT" if "STOP_EQUIVALENT" in available else "STOP_UNRESOLVED",
        reason="untrained_exhausted",
    )


def choose_distilled(remaining: list[str], available: list[str],
                     order: list[str]) -> dict[str, Any]:
    stopped = _stop_if_resolved(remaining, available)
    if stopped:
        return stopped
    for action in order:
        if action in available:
            return dict(action=action, reason="source_distilled_fixed_order")
    return dict(
        action="STOP_EQUIVALENT" if "STOP_EQUIVALENT" in available else "STOP_UNRESOLVED",
        reason="distilled_exhausted",
    )


def choose_bank_ig(remaining: list[str], transcript: list[dict[str, Any]],
                   available: list[str], rng: random.Random) -> dict[str, Any]:
    stopped = _stop_if_resolved(remaining, available)
    if stopped:
        return stopped
    scored = []
    for action in available:
        if str(action).startswith("STOP"):
            continue
        groups = probe_splits(remaining, transcript, action)["groups"]
        expected = sum(len(group) ** 2 for group in groups.values()) / float(max(len(remaining), 1))
        scored.append((expected, action))
    if not scored:
        return dict(action="STOP_UNRESOLVED", reason="no_query")
    best = min(value for value, _action in scored)
    tied = [action for value, action in scored if value == best]
    return dict(action=rng.choice(tied), reason="bank_ig")


def distill_order(source_rows: list[dict[str, Any]]) -> list[str]:
    utility = {action: 0 for action in QUERY_ACTIONS}
    frequency = {action: 0 for action in QUERY_ACTIONS}
    for episode in source_rows:
        prefix: list[dict[str, Any]] = []
        for step in episode.get("transcript") or []:
            remaining = filter_bank(prefix)
            for action in QUERY_ACTIONS:
                if probe_splits(remaining, prefix, action)["informative"]:
                    utility[action] += 1
            chosen = step["action"]
            if chosen in frequency:
                frequency[chosen] += 1
            prefix.append(step)
    return sorted(
        QUERY_ACTIONS,
        key=lambda action: (
            -utility[action],
            -frequency[action],
            DIAGNOSTIC_ORDER.index(action) if action in DIAGNOSTIC_ORDER else 99,
        ),
    )


def run_bank_holdout(task: dict[str, Any], name: str | None) -> list[dict[str, Any]]:
    hidden = blank_state(int(task["instance_seed"]) + 10007)
    hypo = dict(s=0, prev=0)
    rows = []
    for action in HOLDOUT_PROBES:
        observed = apply_hidden(task["mechanism"], hidden, action)
        hidden = observed["state"]
        predicted = None
        if name is not None:
            guessed = apply_candidate(name, hypo, action)
            hypo = guessed["state"]
            predicted = guessed["observation"]
        rows.append(dict(
            action=action, observed=observed["observation"],
            predicted=predicted, oracle=int(observed["oracle"]),
        ))
    return rows


def _choose(method: str, remaining: list[str], available: list[str],
            transcript: list[dict[str, Any]], features: dict[str, float],
            weights: dict[str, list[float]], order: list[str],
            rng: random.Random, meter: WorkMeter) -> dict[str, Any]:
    if method == "untrained_default_policy":
        return choose_untrained_default(remaining, available)
    if method == "source_distilled_fixed_order":
        return choose_distilled(remaining, available, order)
    if method == "bank_ig":
        return choose_bank_ig(remaining, transcript, available, rng)
    picked = select_action(weights, features, available, rng)
    meter.probe_feature_and_policy_evals += len(available)
    return dict(action=picked["selected"], reason=picked["reason"])


def run_episode(task: dict[str, Any], method: str, weights: dict[str, list[float]],
                order: list[str], rng: random.Random) -> dict[str, Any]:
    meter = WorkMeter()
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    stopped = None
    identified = None
    adaptive = method in ("source_learned_adaptive_policy", "bank_ig")
    for step in range(MAX_STEPS):
        remaining = filter_bank(transcript, meter)
        feats = bank_features(transcript, remaining, MAX_STEPS - step, meter if adaptive else None)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        available = adaptive_available(transcript, remaining) if adaptive else static_available(
            transcript, remaining
        )
        choice = _choose(method, remaining, available, transcript, feats, weights, order, rng, meter)
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
    else:
        stopped = "budget"
    remaining = filter_bank(transcript, meter)
    groups = observational_groups(remaining)
    representative = groups[0][0] if len(groups) == 1 else None
    holdout = run_bank_holdout(task, representative)
    synthesized = dict(
        remaining=list(remaining),
        classes=groups,
        representative=representative,
        n_remaining=len(remaining),
        n_classes=len(groups),
    )
    claims = score_claims(task, remaining, synthesized, identified, stopped, holdout)
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        role=task.get("role"),
        method=method,
        transcript=transcript,
        synthesized=synthesized,
        holdout=holdout,
        stopped=stopped,
        identified=identified,
        remaining=list(remaining),
        memory_cleared=MEMORY_CLEARED,
        retrieve=False,
        remember=False,
        memory_updated=False,
        policy_updated=False,
        skill_memory_paused=SKILL_MEMORY_PAUSED,
        track_b_closed=TRACK_B_CLOSED,
        mask=REDUNDANT_MASK_ORIGIN if adaptive else "unused_only",
        instance_seed=task["instance_seed"],
        language_hash=language_hash(),
        **work,
        **claims,
    )


def bank_training_rows(episode: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    first = True
    prefix: list[dict[str, Any]] = []
    rng = random.Random(3)
    for step in episode.get("transcript") or []:
        remaining = filter_bank(prefix)
        available = adaptive_available(prefix, remaining)
        expert = choose_bank_ig(remaining, prefix, available, rng)
        for action in list(QUERY_ACTIONS) + list(ACQUIRE_STOPS):
            rows.append(dict(
                action=action,
                features=dict(step["features"]),
                label=1.0 if action == expert["action"] else 0.0,
                first_query=first and not str(expert["action"]).startswith("STOP"),
                chosen=expert["action"],
                supervision="dagger_bank_ig",
            ))
        prefix.append(step)
        first = False
    return rows


def run_method(tasks: list[dict[str, Any]], method: str, weights: dict[str, list[float]],
               order: list[str], seed: int) -> list[dict[str, Any]]:
    rows = []
    for index, task in enumerate(tasks):
        rng = random.Random(seed * 1009 + index * 17 + 11)
        episode = run_episode(task, method, weights, order, rng)
        episode["policy_seed"] = seed
        rows.append(episode)
    return rows


def _shuffle_source(tasks: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rows = list(tasks)
    random.Random(seed).shuffle(rows)
    return rows


def _sum_work(rows: list[dict[str, Any]]) -> dict[str, int]:
    meter = WorkMeter()
    for row in rows:
        meter.env_interactions += int(row.get("env_interactions") or 0)
        meter.hypothesis_evals += int(row.get("hypothesis_evals") or 0)
        meter.probe_feature_and_policy_evals += int(row.get("probe_feature_and_policy_evals") or 0)
    return meter.as_dict()


def _method_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, useful_acquisition=0, predictive_competence=0,
            exact_mechanism_identification=0, guessed_generator=0,
            env_interactions=0, hypothesis_evals=0,
            probe_feature_and_policy_evals=0, total_acquisition_work=0,
        ))
        cell["n"] += 1
        for key in (
            "useful_acquisition", "predictive_competence",
            "exact_mechanism_identification", "guessed_generator",
        ):
            cell[key] += int(bool(row.get(key)))
        for key in (
            "env_interactions", "hypothesis_evals",
            "probe_feature_and_policy_evals", "total_acquisition_work",
        ):
            cell[key] += int(row.get(key) or 0)
    return out


def _breakeven(source_work: int, learned: dict[str, Any], other: dict[str, Any],
               n_tasks: int) -> dict[str, Any]:
    saved = int(other.get("total_acquisition_work") or 0) - int(learned.get("total_acquisition_work") or 0)
    per_task = saved / float(n_tasks) if n_tasks else 0.0
    if per_task <= 0:
        return dict(source_training_work=source_work, per_task_work_saved=per_task,
                    n_breakeven=None, defined=False)
    return dict(
        source_training_work=source_work,
        per_task_work_saved=per_task,
        n_breakeven=source_work / per_task,
        defined=True,
    )


def reconstruct_work(episode: dict[str, Any]) -> dict[str, int]:
    meter = WorkMeter()
    prefix: list[dict[str, Any]] = []
    adaptive = episode["method"] in ("source_learned_adaptive_policy", "bank_ig")
    weights = zero_acquire()
    order = list(DIAGNOSTIC_ORDER)
    rng = random.Random(0)
    for step in episode.get("transcript") or []:
        remaining = filter_bank(prefix, meter)
        feats = bank_features(prefix, remaining, MAX_STEPS - len(prefix), meter if adaptive else None)
        available = adaptive_available(prefix, remaining) if adaptive else static_available(
            prefix, remaining
        )
        if adaptive and episode["method"] == "source_learned_adaptive_policy":
            meter.probe_feature_and_policy_evals += len(available)
        elif adaptive:
            _choose("bank_ig", remaining, available, prefix, feats, weights, order, rng, meter)
        if not str(step["action"]).startswith("STOP"):
            meter.env_interactions += 1
        prefix.append(step)
    filter_bank(prefix, meter)
    return meter.as_dict()


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("policy_seed"),
            task_id=row["task_id"],
            split=row["split"],
            mechanism=row["mechanism"],
            method=row["method"],
            env_interactions=int(row["env_interactions"]),
            hypothesis_evals=int(row["hypothesis_evals"]),
            policy_evals=int(row["probe_feature_and_policy_evals"]),
            probe_feature_and_policy_evals=int(row["probe_feature_and_policy_evals"]),
            total_acquisition_work=int(row["total_acquisition_work"]),
            solved=bool(row.get("useful_acquisition")),
            retained=bool(row.get("useful_acquisition")) if row.get("split") == "up_retain" else None,
            predictive_competence=bool(row.get("predictive_competence")),
            stopped=row.get("stopped"),
        )
        for row in rows
    ]


def evaluate_gates(seed_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    gate1 = True
    gate2 = True
    gate3 = True
    for block in seed_blocks:
        totals = block["assessment_totals"]
        untrained = totals.get("untrained_default_policy") or {}
        distilled = totals.get("source_distilled_fixed_order") or {}
        learned = totals.get("source_learned_adaptive_policy") or {}
        if (
            int(untrained.get("predictive_competence") or -1)
            != int(distilled.get("predictive_competence") or -2)
            or int(distilled.get("predictive_competence") or -1)
            != int(learned.get("predictive_competence") or -2)
            or int(untrained.get("useful_acquisition") or -1)
            != int(distilled.get("useful_acquisition") or -2)
            or int(distilled.get("useful_acquisition") or -1)
            != int(learned.get("useful_acquisition") or -2)
        ):
            gate1 = False
            notes.append("gate1_accuracy_seed_{0}".format(block["seed"]))
        retain = block.get("retain_totals") or {}
        r_u = retain.get("untrained_default_policy") or {}
        r_d = retain.get("source_distilled_fixed_order") or {}
        r_l = retain.get("source_learned_adaptive_policy") or {}
        if (
            int(r_u.get("useful_acquisition") or -1) != int(r_d.get("useful_acquisition") or -2)
            or int(r_d.get("useful_acquisition") or -1) != int(r_l.get("useful_acquisition") or -2)
        ):
            gate1 = False
            notes.append("gate1_retention_seed_{0}".format(block["seed"]))
        if not (
            int(learned.get("env_interactions") or 10**9) < int(untrained.get("env_interactions") or 0)
            and int(learned.get("env_interactions") or 10**9) < int(distilled.get("env_interactions") or 0)
        ):
            gate2 = False
            notes.append("gate2_seed_{0}".format(block["seed"]))
        if not (
            int(learned.get("total_acquisition_work") or 10**9)
            < int(untrained.get("total_acquisition_work") or 0)
            and int(learned.get("total_acquisition_work") or 10**9)
            < int(distilled.get("total_acquisition_work") or 0)
        ):
            gate3 = False
            notes.append("gate3_seed_{0}".format(block["seed"]))
    return dict(
        gate1_accuracy_retention_parity=gate1,
        gate2_beats_untrained_and_distilled_interactions=gate2,
        gate3_net_total_work_reduction=gate3,
        passed=bool(gate1 and gate2 and gate3),
        notes=notes,
    )


def run_replication(directory) -> dict[str, Any]:
    from pathlib import Path
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = unfamiliar_policy_tasks("up_source")
    holdout = unfamiliar_policy_tasks("up_holdout")
    retain = unfamiliar_policy_tasks("up_retain")
    if any(row["task_id"] in OPENED_IDS for row in source + holdout + retain):
        raise ValueError("opened_id_in_challenge")
    if not branch_property()["holds"]:
        raise ValueError("branch_property_failed")
    seed_blocks = []
    assessment_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    source_work = WorkMeter()
    for seed in TRAIN_SEEDS:
        ordered = _shuffle_source(source, seed)
        teacher = run_method(ordered, "bank_ig", zero_acquire(), list(DIAGNOSTIC_ORDER), seed=5 + seed)
        source_rows.extend(teacher)
        teacher_work = _sum_work(teacher)
        source_work.env_interactions += teacher_work["env_interactions"]
        source_work.hypothesis_evals += teacher_work["hypothesis_evals"]
        source_work.probe_feature_and_policy_evals += teacher_work["probe_feature_and_policy_evals"]
        supervised = []
        for episode in teacher:
            supervised.extend(bank_training_rows(episode))
        weights = fit_acquire(supervised)
        own = run_method(ordered, "source_learned_adaptive_policy", _with_stops(weights),
                         list(DIAGNOSTIC_ORDER), seed=30 + seed)
        source_rows.extend(own)
        own_work = _sum_work(own)
        source_work.env_interactions += own_work["env_interactions"]
        source_work.hypothesis_evals += own_work["hypothesis_evals"]
        source_work.probe_feature_and_policy_evals += own_work["probe_feature_and_policy_evals"]
        for episode in own:
            supervised.extend(bank_training_rows(episode))
        weights = fit_acquire(supervised)
        frozen = policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS})
        order = distill_order(teacher)
        hold_rows = []
        retain_rows = []
        for method, used_weights in (
            ("untrained_default_policy", zero_acquire()),
            ("source_distilled_fixed_order", zero_acquire()),
            ("source_learned_adaptive_policy", _with_stops(weights)),
        ):
            hold_rows.extend(run_method(holdout, method, used_weights, order, seed=80 + seed))
            retain_rows.extend(run_method(retain, method, used_weights, order, seed=90 + seed))
        assessment_rows.extend(hold_rows)
        assessment_rows.extend(retain_rows)
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=frozen,
            distilled_order=list(order),
            source_competence=all(row["useful_acquisition"] for row in own),
            holdout=hold_rows,
            retain=retain_rows,
            assessment_totals=_method_totals(hold_rows),
            retain_totals=_method_totals(retain_rows),
            combined_totals=_method_totals(hold_rows + retain_rows),
        ))
    gates = evaluate_gates(seed_blocks)
    holdout_only = [row for row in assessment_rows if row["split"] == "up_holdout"]
    retain_only = [row for row in assessment_rows if row["split"] == "up_retain"]
    overall = _method_totals(holdout_only)
    retain_overall = _method_totals(retain_only)
    learned = overall.get("source_learned_adaptive_policy") or {}
    untrained = overall.get("untrained_default_policy") or {}
    distilled = overall.get("source_distilled_fixed_order") or {}
    n_hold = max(len(holdout) * len(TRAIN_SEEDS), 1)
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
        skill_memory_paused=SKILL_MEMORY_PAUSED,
        memory_cleared=MEMORY_CLEARED,
    )
    payload = dict(
        kind=KIND,
        prior_closed=list(PRIOR_CLOSED),
        confirmation=False,
        learning_to_learn_established=False,
        track_b_closed=TRACK_B_CLOSED,
        skill_memory_paused=SKILL_MEMORY_PAUSED,
        memory_cleared=MEMORY_CLEARED,
        branch_property=branch_property(),
        hypothesis_bank=list(HYPOTHESIS_BANK),
        methods=list(METHODS),
        seeds=list(TRAIN_SEEDS),
        source=[{k: row[k] for k in (
            "task_id", "method", "mechanism", "policy_seed", "useful_acquisition",
            "env_interactions", "hypothesis_evals", "probe_feature_and_policy_evals",
            "total_acquisition_work",
        ) if k in row} for row in source_rows],
        assessment=assessment_rows,
        seed_blocks=[{k: block[k] for k in (
            "seed", "policy_hash", "distilled_order", "source_competence",
            "assessment_totals", "retain_totals", "combined_totals",
        )} for block in seed_blocks],
        per_task=per_task_rows(assessment_rows),
        totals=dict(holdout=overall, retain=retain_overall),
        source_training_work=source_work.as_dict(),
        breakeven=dict(
            vs_untrained=_breakeven(source_work.total_acquisition_work, learned, untrained, n_hold),
            vs_distilled=_breakeven(source_work.total_acquisition_work, learned, distilled, n_hold),
        ),
        gates=gates,
        bounded_claim=(
            "NEXUS learned an investigation strategy from source tasks that "
            "reduced the cost of acquiring unfamiliar mechanisms within the tested setting."
            if gates["passed"] else
            "The tested setting did not support the bounded investigation-strategy claim."
        ),
        usage=usage,
        language_hash=language_hash(),
        feature_names=list(FEATURE_NAMES),
    )
    payload["hash"] = digest({
        key: payload[key] for key in (
            "kind", "assessment", "totals", "gates", "source_training_work", "breakeven",
        )
    })
    (directory / "seed_unfamiliar_policy_replication.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("usage", {}).get("research_cpu_ledger_debit_s") not in (0, None):
        ok = False
        notes.append("ledger_debit")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("claimed_l2l")
    if not payload.get("memory_cleared") or not payload.get("skill_memory_paused"):
        ok = False
        notes.append("memory_not_cleared")
    if not payload.get("track_b_closed"):
        ok = False
        notes.append("track_b_open")
    if not (payload.get("branch_property") or {}).get("holds"):
        ok = False
        notes.append("branch_property")
    rows = list(payload.get("assessment") or [])
    if any(row["task_id"] in OPENED_IDS for row in rows):
        ok = False
        notes.append("rescored_opened")
    if any(row.get("exact_mechanism_identification") for row in rows):
        ok = False
        notes.append("exact_claimed")
    if any(row.get("remember") or row.get("retrieve") or row.get("memory_updated") for row in rows):
        ok = False
        notes.append("memory_used")
    rebuilt = _method_totals([row for row in rows if row.get("split") == "up_holdout"])
    saved = (payload.get("totals") or {}).get("holdout") or {}
    for name, cell in rebuilt.items():
        other = saved.get(name) or {}
        for key in ("useful_acquisition", "env_interactions", "total_acquisition_work"):
            if cell.get(key) != other.get(key):
                ok = False
                notes.append("column:" + name + ":" + key)
    for row in rows:
        reconstructed = reconstruct_work(row)
        for key in ("env_interactions", "hypothesis_evals", "probe_feature_and_policy_evals",
                    "total_acquisition_work"):
            if reconstructed.get(key) != row.get(key):
                ok = False
                notes.append("reconstruct:" + row["task_id"] + ":" + row["method"] + ":" + key)
                break
    gates = evaluate_gates(list(payload.get("seed_blocks") or []))
    saved_gates = payload.get("gates") or {}
    for key in (
        "gate1_accuracy_retention_parity",
        "gate2_beats_untrained_and_distilled_interactions",
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
