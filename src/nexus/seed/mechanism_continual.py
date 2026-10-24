"""Three-wave continual mechanism experience. Track A only.

Inner loop: probe, update hypotheses, build a scoped executable model.
Outer loop: source-only policy update. Skill memory and policy reset
independently. Opened prior grids are not rescored.
"""
from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_acquire import (
    ACQUIRE_STOPS, _with_stops, acquire_available, acquire_training_rows,
    choose_composition_ig, choose_fixed_synthesis, compose_features,
    fit_acquire, run_holdout, zero_acquire,
)
from .mechanism_claims import parse_pipe, score_claims
from .mechanism_compose import (
    filter_compositions, pipe_name, synthesize,
)
from .mechanism_investigate import (
    FEATURE_NAMES, HIDDEN, choose_diagnostic, filter_language,
)
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash, shuffle_weights
from .mechanism_skills import MechanismSkillStore
from .mechanism_tasks import catalogue, split_lock, wave_tasks
from .mechanism_types import (
    STRUCTURAL_PRIMITIVES, TYPE_ORIGIN, affine_predict, fit_affine,
    type_tag, typed_compositions,
)
from .mechanism_world import (
    ACTION_COST, ACTIONS, LANGUAGE, MAX_STEPS, apply_hidden, blank_state,
    language_hash,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_continual"
PRIOR_CLOSED = ("92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d")
OPENED_IDS = {
    "c_add4", "c_count2", "d_add_mul", "d_count_add", "e_delay", "e_threshold",
    "mm_abs", "mm_mod3", "mm_clip0", "mm_prev", "ctl_neg", "ctl_toggle",
    "vp_id0", "vp_mod2", "vp_plus", "vp_twin", "vp_add2", "vp_neg", "vp_count",
    "acq_gate_mul_add", "acq_gate_add_neg", "acq_gate_neg_add",
    "acq_hold_add2_mul", "acq_hold_neg_add2", "acq_hold_mul_neg",
}
ARMS = (
    "fixed_learner",
    "fixed_exact",
    "fixed_template",
    "policy_only",
    "memory_only",
    "full_nexus",
    "irrelevant_memory",
)
TRANSFER_USEFUL_DELTA = 1
TRANSFER_COST_RATIO = 0.80
PROBE_ORIGIN = "programmer_supplied"


def _typed_filter(transcript: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    allowed = set(typed_compositions())
    return [parts for parts in filter_compositions(transcript, primitives=STRUCTURAL_PRIMITIVES)
            if parts in allowed]


def _choose(method: str, weights: dict[str, list[float]], ctx: dict[str, Any]) -> dict[str, Any]:
    compose_remain = ctx["compose_remain"]
    language_remain = ctx["language_remain"]
    available = ctx["available"]
    transcript = ctx["transcript"]
    rng = ctx["rng"]
    if method in ("fixed_learner", "fixed_exact", "fixed_template", "memory_only", "irrelevant_memory"):
        return choose_fixed_synthesis(language_remain, compose_remain, available)
    if method in ("policy_only", "full_nexus"):
        from .mechanism_policy import select_action
        picked = select_action(weights, ctx["features"], available, rng)
        return dict(action=picked["selected"], score_work=0, reason=picked["reason"])
    return choose_composition_ig(compose_remain, transcript, available, rng)


def run_episode(task: dict[str, Any], arm: str, weights: dict[str, list[float]],
                store: MechanismSkillStore | None, rng: random.Random,
                *, remember: bool, retrieve: bool) -> dict[str, Any]:
    task = dict(task, primitives=list(STRUCTURAL_PRIMITIVES))
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    score_work = 0
    oracle = 0
    actions = 0
    stopped = None
    identified = None
    retrieval_hits = 0
    sequence: list[dict[str, Any]] = []
    for step in range(MAX_STEPS):
        language_remain = filter_language(transcript)
        compose_remain = _typed_filter(transcript)
        built = compose_features(transcript, compose_remain, MAX_STEPS - step)
        feats = built["features"]
        score_work += int(built["score_work"])
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        avail = acquire_available(transcript, language_remain, compose_remain)
        score_work += int(avail["score_work"])
        choice = _choose(arm, weights, dict(
            language_remain=language_remain, compose_remain=compose_remain,
            available=avail["actions"], transcript=transcript, features=feats,
            rng=rng,
        ))
        action = choice["action"]
        if action not in avail["actions"]:
            raise ValueError("chose_masked_action:" + action)
        score_work += int(choice.get("score_work") or 0)
        actions += ACTION_COST.get(action, 0)
        if action in ACQUIRE_STOPS:
            stopped = action
            if action == "STOP_IDENTIFY" and len(language_remain) == 1:
                identified = language_remain[0]
            transcript.append(dict(action=action, observation=None, oracle=0,
                                   remaining=list(language_remain), features=feats,
                                   reason=choice.get("reason")))
            sequence.append(dict(step=step, probe=action, outcome=None,
                                 remaining=len(compose_remain)))
            break
        applied = apply_hidden(task["mechanism"], hidden, action)
        hidden = applied["state"]
        oracle += int(applied["oracle"])
        transcript.append(dict(
            action=action, observation=applied["observation"],
            oracle=int(applied["oracle"]), remaining=list(language_remain),
            features=feats, reason=choice.get("reason"),
        ))
        sequence.append(dict(
            step=step, probe=action, outcome=applied["observation"],
            remaining=len(_typed_filter(transcript)),
        ))
    else:
        stopped = "budget"
    language_remain = filter_language(transcript)
    affine = fit_affine(transcript)
    synthesized = synthesize(transcript, primitives=STRUCTURAL_PRIMITIVES)
    allowed = {pipe_name(parts) for parts in typed_compositions()}
    synthesized["remaining"] = [name for name in synthesized["remaining"] if name in allowed]
    if synthesized["remaining"]:
        synthesized["representative"] = synthesized["remaining"][0]
    else:
        synthesized["representative"] = None
    synthesized["n_remaining"] = len(synthesized["remaining"])
    score_work += int(synthesized["score_work"])
    parts = parse_pipe(synthesized.get("representative"))
    if retrieve and store is not None:
        if arm == "fixed_exact":
            cached = store.lookup_exact(transcript)
            if cached:
                parts = parse_pipe(cached)
                retrieval_hits += 1
        elif arm == "fixed_template" and parts:
            templates = store.lookup_template(type_tag(parts))
            if templates:
                parts = parse_pipe(templates[0])
                retrieval_hits += 1
        elif arm in ("memory_only", "full_nexus", "irrelevant_memory"):
            found = store.lookup_nexus(transcript)
            if found:
                parts = tuple(found[0]["parts"])
                retrieval_hits += 1
        score_work += int(store.retrieval_cost)
    if affine and not parts:
        # Affine fallback only when typed synthesis is empty.
        holdout_affine = []
        hidden2 = blank_state(int(task["instance_seed"]) + 10007)
        from .mechanism_compose import HOLDOUT_PROBES
        for action in HOLDOUT_PROBES:
            observed = apply_hidden(task["mechanism"], hidden2, action)
            hidden2 = observed["state"]
            holdout_affine.append(dict(
                action=action, observed=observed["observation"],
                predicted=affine_predict(affine, action), oracle=int(observed["oracle"]),
            ))
        claims = score_claims(task, language_remain, synthesized, identified, stopped, holdout_affine)
        holdout = holdout_affine
        model = dict(kind="affine", **affine)
    else:
        holdout = run_holdout(task, parts)
        claims = score_claims(task, language_remain, synthesized, identified, stopped, holdout)
        model = dict(kind="pipeline", pipeline=pipe_name(parts) if parts else None)
    if remember and store is not None and claims["useful_acquisition"] and parts:
        store.remember(parts, transcript, family=task.get("family") or "source")
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        role=task.get("role"),
        arm=arm,
        method=arm,
        transcript=transcript,
        sequence=sequence,
        synthesized=synthesized,
        model=model,
        holdout=holdout,
        stopped=stopped,
        identified=identified,
        remaining=list(language_remain),
        affine=affine,
        retrieval_hits=retrieval_hits,
        oracle=oracle + sum(int(row["oracle"]) for row in holdout),
        investigate_oracle=oracle,
        action_steps=actions + len(holdout),
        score_work=score_work,
        total_work=oracle + actions + score_work + sum(int(row["oracle"]) for row in holdout),
        interactions=len([row for row in transcript if not str(row["action"]).startswith("STOP")]) + len(holdout),
        **claims,
        probe_origin=PROBE_ORIGIN,
        type_origin=TYPE_ORIGIN,
        language_hash=language_hash(),
        instance_seed=task["instance_seed"],
        solutions_reset=arm == "policy_only",
        memory_updated=bool(remember),
        policy_updated=False,
    )


def run_arm_tasks(tasks: list[dict[str, Any]], arm: str, weights: dict[str, list[float]],
                  store: MechanismSkillStore | None, seed: int, *,
                  remember: bool, retrieve: bool) -> list[dict[str, Any]]:
    rows = []
    for index, task in enumerate(tasks):
        rng = random.Random(seed * 1009 + index * 19 + 5)
        episode = run_episode(task, arm, weights, store, rng, remember=remember, retrieve=retrieve)
        episode["policy_seed"] = seed
        rows.append(episode)
    return rows


def score_columns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = out.setdefault(row["arm"], dict(
            n=0, useful_acquisition=0, predictive_competence=0,
            catalogue_identification=0, exact_mechanism_identification=0,
            scoped_match=0, guessed_generator=0, correct_reject=0,
            demonstrated_inconsistency=0, unresolved_uncertainty=0,
            harmful_transfer=0, interactions=0, oracle=0, total_work=0,
            retrieval_hits=0,
        ))
        cell["n"] += 1
        for key in (
            "useful_acquisition", "predictive_competence", "catalogue_identification",
            "exact_mechanism_identification", "scoped_match", "guessed_generator",
            "correct_reject", "demonstrated_inconsistency", "unresolved_uncertainty",
        ):
            cell[key] += int(bool(row.get(key)))
        cell["harmful_transfer"] += int(bool(row.get("retrieve") and row.get("guessed_generator")))
        for key in ("interactions", "oracle", "total_work", "retrieval_hits"):
            cell[key] += int(row.get(key) or 0)
    for cell in out.values():
        n = max(cell["n"], 1)
        cell["mean_interactions"] = cell["interactions"] / n
        cell["mean_oracle"] = cell["oracle"] / n
        cell["mean_work"] = cell["total_work"] / n
    return out


def _competence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    acq = [row for row in rows if row.get("role") != "reject"]
    report = dict(
        n=len(acq),
        useful=sum(int(row["useful_acquisition"]) for row in acq),
        guessed=sum(int(row["guessed_generator"]) for row in acq),
        exact=sum(int(row["exact_mechanism_identification"]) for row in acq),
    )
    report["passed"] = bool(acq and report["useful"] == report["n"] and report["guessed"] == 0)
    report["reason"] = "source_competence" if report["passed"] else "inner_learner_failure"
    return report


def _verdicts(wave2: dict[str, Any], wave3: dict[str, Any]) -> dict[str, str]:
    fixed = wave2.get("fixed_learner") or {}
    memory = wave2.get("memory_only") or {}
    template = wave2.get("fixed_template") or {}
    policy = wave2.get("policy_only") or {}
    full = wave2.get("full_nexus") or {}
    retain = wave3.get("memory_only") or wave3.get("full_nexus") or {}
    skill_transfer = "none"
    if int(memory.get("useful_acquisition") or 0) >= int(fixed.get("useful_acquisition") or 0) + TRANSFER_USEFUL_DELTA:
        skill_transfer = "memory_helps"
    elif (
        int(memory.get("useful_acquisition") or 0) == int(fixed.get("useful_acquisition") or 0)
        and int(memory.get("interactions") or 1) <= TRANSFER_COST_RATIO * max(int(fixed.get("interactions") or 1), 1)
    ):
        skill_transfer = "memory_cheaper"
    elif int(memory.get("useful_acquisition") or 0) <= int(template.get("useful_acquisition") or 0):
        skill_transfer = "no_advantage_over_template"
    l2l = "fixed-baseline tie"
    if int(policy.get("useful_acquisition") or 0) < int(fixed.get("useful_acquisition") or 0):
        l2l = "negative"
    elif int(policy.get("useful_acquisition") or 0) > int(fixed.get("useful_acquisition") or 0):
        l2l = "useful learned investigation advantage"
    elif int(policy.get("interactions") or 0) < int(fixed.get("interactions") or 0):
        l2l = "useful learned investigation advantage"
    inner = "inner_learner_works"
    overall = "skill_reuse_only" if skill_transfer.startswith("memory") and l2l in ("fixed-baseline tie", "negative") else l2l
    if skill_transfer in ("none", "no_advantage_over_template") and l2l == "fixed-baseline tie":
        overall = "fixed-baseline tie"
    return dict(
        inner_learning=inner,
        skill_transfer=skill_transfer,
        policy_learning=l2l,
        retention="reserved_source_retest",
        overall=overall,
        full_nexus_useful=str(int(full.get("useful_acquisition") or 0)),
        reserved_useful=str(int(retain.get("useful_acquisition") or 0)),
    )


def run_continual(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = wave_tasks("wave1_source")
    development = wave_tasks("wave1_dev")
    targets = wave_tasks("wave2_target", "wave2_reject")
    compose = wave_tasks("wave3_compose")
    retain = wave_tasks("wave3_retain")
    if any(row["task_id"] in OPENED_IDS for row in source + development + targets + compose + retain):
        raise ValueError("opened_id_in_challenge")
    inner_rows = run_arm_tasks(development, "fixed_learner", zero_acquire(), None, 7,
                               remember=False, retrieve=False)
    inner = _competence(inner_rows)
    wave1: list[dict[str, Any]] = list(inner_rows)
    competence_reports = []
    seeds_used = []
    passed = []
    closed = not inner["passed"]
    wave2_rows: list[dict[str, Any]] = []
    wave3_rows: list[dict[str, Any]] = []
    snapshots = []
    if inner["passed"]:
        for seed in TRAIN_SEEDS:
            store = MechanismSkillStore()
            src = run_arm_tasks(source, "fixed_learner", zero_acquire(), store, 5 + seed,
                                remember=True, retrieve=False)
            wave1.extend(src)
            supervised: list[dict[str, Any]] = []
            for episode in src:
                supervised.extend(acquire_training_rows(episode, primitives=STRUCTURAL_PRIMITIVES))
            weights = fit_acquire(supervised)
            own_src = run_arm_tasks(source, "policy_only", _with_stops(weights), None, 30 + seed,
                                    remember=False, retrieve=False)
            for episode in own_src:
                supervised.extend(acquire_training_rows(episode, primitives=STRUCTURAL_PRIMITIVES))
            weights = fit_acquire(supervised)
            frozen = policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS})
            own_dev = run_arm_tasks(development, "policy_only", _with_stops(weights), None, 11 + seed,
                                    remember=False, retrieve=False)
            report = _competence(own_dev)
            report["seed"] = seed
            report["policy_hash"] = frozen
            competence_reports.append(report)
            seeds_used.append(dict(seed=seed, policy_hash=frozen, competence=report["passed"],
                                   n_skills=len(store.skills)))
            snapshots.append(store.snapshot())
            if report["passed"]:
                passed.append(dict(seed=seed, weights=weights, store=store, hash=frozen))
        closed = not (passed and all(row["passed"] for row in competence_reports))
        if not closed:
            for block in passed:
                seed = block["seed"]
                frozen_store = MechanismSkillStore()
                for skill in block["store"].skills:
                    frozen_store.skills.append(dict(skill))
                    frozen_store.exact.put(
                        digest([(row["action"], row.get("observation")) for row in skill["evidence"]]),
                        {}, {"pipeline": skill["pipeline"]},
                    )
                    frozen_store.templates.setdefault(skill["type_tag"], []).append(skill["pipeline"])
                irr = MechanismSkillStore()
                for skill in frozen_store.skills:
                    bogus = dict(skill, parts=["add2", "add2"], pipeline="add2|add2", family="irrelevant")
                    irr.skills.append(bogus)
                weights = _with_stops(block["weights"])
                for arm, used_store, remember, retrieve, used_weights in (
                    ("fixed_learner", None, False, False, zero_acquire()),
                    ("fixed_exact", frozen_store, False, True, zero_acquire()),
                    ("fixed_template", frozen_store, False, True, zero_acquire()),
                    ("policy_only", None, False, False, weights),
                    ("memory_only", frozen_store, False, True, zero_acquire()),
                    ("full_nexus", frozen_store, False, True, weights),
                    ("irrelevant_memory", irr, False, True, zero_acquire()),
                ):
                    chunk = run_arm_tasks(targets, arm, used_weights, used_store, 20 + seed,
                                          remember=remember, retrieve=retrieve)
                    wave2_rows.extend(chunk)
                    later = run_arm_tasks(compose + retain, arm, used_weights, used_store, 40 + seed,
                                          remember=remember, retrieve=retrieve)
                    wave3_rows.extend(later)
    columns = dict(
        wave1=score_columns(wave1),
        wave2=score_columns(wave2_rows),
        wave3=score_columns(wave3_rows),
    )
    verdicts = _verdicts(columns["wave2"], columns["wave3"]) if wave2_rows else dict(
        inner_learning="inner_learner_failure" if not inner["passed"] else "training_failure",
        skill_transfer="closed", policy_learning="closed", overall="training_failure",
    )
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        track_b_run=False,
        online_stream_run=False,
        prior_assessments_closed=list(PRIOR_CLOSED),
        opened_ids_not_rescored=sorted(OPENED_IDS),
        assessment_closed=closed,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        primitives=list(STRUCTURAL_PRIMITIVES),
        primitive_origin="programmer_supplied",
        type_origin=TYPE_ORIGIN,
        probe_origin=PROBE_ORIGIN,
        adapters=dict(sign_pos="programmer_supplied_hidden_executor"),
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        supervision="full_sequence_dagger_composition_ig",
        credit="entire_probe_sequence_not_last_probe",
        inner=inner,
        inner_episodes=inner_rows,
        competence=dict(reports=competence_reports, passed=bool(passed) and all(r["passed"] for r in competence_reports),
                        n_passed=len(passed)),
        policy_seeds=seeds_used,
        skill_snapshots=snapshots,
        wave1=wave1,
        wave2=wave2_rows,
        wave3=wave3_rows,
        columns=columns,
        verdicts=verdicts,
        thresholds=dict(
            transfer_useful_delta=TRANSFER_USEFUL_DELTA,
            transfer_cost_ratio=TRANSFER_COST_RATIO,
            retention="report_reserved_not_zero_forgetting",
        ),
        usage=dict(
            wall_s=round(time.perf_counter() - started, 6),
            rss=sample_process_memory(),
            frozen_cpu_used_s=FROZEN_CPU_USED_S,
            frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
            frozen_debit_s=0,
            product_chat_unused=True,
            metal_unused=True,
            model_calls=0,
            ledger="standing_local_cpu_grant",
        ),
        claim_boundaries=dict(
            learning_to_learn=False,
            exact_identity_unrestricted=False,
            reject_is_not_acquisition=True,
            track_b_not_a_substitute=True,
            online_stream_separate=True,
        ),
    )
    payload["hash"] = digest({
        "inner": inner,
        "columns": columns,
        "verdicts": verdicts,
        "assessment_closed": closed,
    })
    (directory / "seed_mechanism_continual.json").write_text(
        json.dumps(payload, default=str), encoding="utf-8")
    return payload


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("claimed_l2l")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    rows = (payload.get("wave1") or []) + (payload.get("wave2") or []) + (payload.get("wave3") or [])
    for row in rows:
        if row["task_id"] in OPENED_IDS:
            ok = False
            notes.append("rescored_opened:" + row["task_id"])
        if row.get("exact_mechanism_identification"):
            ok = False
            notes.append("exact_claimed:" + row["task_id"])
        if row.get("role") == "reject" and row.get("useful_acquisition"):
            ok = False
            notes.append("reject_counted_as_acquired:" + row["task_id"])
        if row.get("split") in ("wave2_target", "wave2_reject", "wave3_compose", "wave3_retain"):
            if row.get("memory_updated"):
                ok = False
                notes.append("assessment_wrote_memory:" + row["task_id"])
            if row.get("policy_updated"):
                ok = False
                notes.append("assessment_wrote_policy:" + row["task_id"])
    if payload.get("assessment_closed") and (payload.get("wave2") or payload.get("wave3")):
        ok = False
        notes.append("closed_but_assessed")
    rebuilt = dict(
        wave2=score_columns(payload.get("wave2") or []),
        wave3=score_columns(payload.get("wave3") or []),
    )
    saved = payload.get("columns") or {}
    for wave in ("wave2", "wave3"):
        for name, cell in rebuilt[wave].items():
            other = (saved.get(wave) or {}).get(name) or {}
            for key in ("useful_acquisition", "predictive_competence", "interactions", "oracle"):
                if cell.get(key) != other.get(key):
                    ok = False
                    notes.append("column:" + wave + ":" + name + ":" + key)
    return dict(valid=ok, notes=notes, n=len(rows))
