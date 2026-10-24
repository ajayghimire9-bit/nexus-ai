"""Acquire an unstored composition, then predict on a fresh instance.

Stage 1 must show the fixed synthesizer works. Stage 2, if opened,
compares source-trained search to that synthesizer on held-out
compositions with per-task reset. Opened prior grids are not rescored.
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from typing import Any, Callable

from .capability_evidence import digest
from .mechanism_claims import parse_pipe, score_claims
from .mechanism_compose import (
    HOLDOUT_PROBES, PRIMITIVE_ORIGIN, PRIMITIVES, compositions,
    filter_compositions, pipe_name, score_compose_gain, synthesize,
)
from .mechanism_investigate import (
    DIAGNOSTIC_ORDER, FEATURE_NAMES, HIDDEN, QUERY_ACTIONS, REDUNDANT_MASK_ORIGIN,
    choose_diagnostic, feature_vector, filter_language,
    used_since_reset,
)
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import fit_source, policy_hash, reset_weights, select_action, shuffle_weights
from .mechanism_tasks import (
    catalogue, split_lock, synthesis_gate_tasks, synthesis_holdout_tasks,
    synthesis_source_tasks,
)
from .mechanism_world import (
    ACTION_COST, ACTIONS, LANGUAGE, MAX_STEPS, apply_hidden, blank_state, language_hash,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_mechanism_acquire"
PRIOR_CLOSED = ("92d6f19", "ff26a18", "5575762", "7ae2432")
OPENED_IDS = {
    "c_add4", "c_count2", "d_add_mul", "d_count_add", "e_delay", "e_threshold",
    "mm_abs", "mm_mod3", "mm_clip0", "mm_prev", "ctl_neg", "ctl_toggle",
    "vp_id0", "vp_mod2", "vp_plus", "vp_twin", "vp_add2", "vp_neg", "vp_count",
}
ACQUIRE_STOPS = ("STOP_IDENTIFY", "STOP_UNRESOLVED", "STOP_EQUIVALENT")
STAGE2_METHODS = (
    "trained", "reset_policy", "shuffled_policy",
    "fixed_synthesis", "catalogue_only", "composition_ig",
)


def _compose_redundant(action: str, transcript: list[dict[str, Any]],
                       compose_remain: list[tuple[str, ...]]) -> dict[str, Any]:
    if action.startswith("STOP") or action == "RESET":
        return dict(redundant=False, work=0)
    scored = score_compose_gain(compose_remain, transcript, action)
    if not used_since_reset(transcript, action):
        return dict(redundant=False, work=int(scored["work"]))
    informative = bool(compose_remain) and scored["score"] < float(len(compose_remain)) - 1e-12
    return dict(redundant=not informative, work=int(scored["work"]))


def acquire_available(transcript: list[dict[str, Any]], language_remain: list[str],
                      compose_remain: list[tuple[str, ...]]) -> dict[str, Any]:
    kept = []
    work = 0
    for action in QUERY_ACTIONS:
        checked = _compose_redundant(action, transcript, compose_remain)
        work += int(checked["work"])
        if not checked["redundant"]:
            kept.append(action)
    kept.append("STOP_UNRESOLVED")
    if len(language_remain) == 1:
        kept.append("STOP_IDENTIFY")
    if compose_remain:
        kept.append("STOP_EQUIVALENT")
    return dict(actions=kept, score_work=work, mask=REDUNDANT_MASK_ORIGIN)


def compose_features(transcript: list[dict[str, Any]], compose_remain: list[tuple[str, ...]],
                     steps_left: int) -> dict[str, Any]:
    last = next((row for row in reversed(transcript) if row.get("observation") is not None), None)
    last_y = None if last is None else int(last["observation"])
    last_act = transcript[-1]["action"] if transcript else None
    n = max(len(compositions()), 1)
    work = 0
    feats = dict(
        n_remaining_frac=len(compose_remain) / float(n),
        n_remaining=float(len(compose_remain)),
        log_remaining=math.log2(len(compose_remain) + 1),
        n_actions=float(len(transcript)),
        budget_left_frac=steps_left / float(MAX_STEPS),
        vs_empty=float(not compose_remain),
        vs_singleton=float(len(compose_remain) == 1),
        identification_supported=0.0,
        last_obs_scaled=0.0 if last_y is None else max(-8, min(8, last_y)) / 8.0,
        last_obs_missing=float(last_y is None),
    )
    for action in QUERY_ACTIONS:
        scored = score_compose_gain(compose_remain, transcript, action)
        work += int(scored["work"])
        feats[f"used_{action}"] = float(used_since_reset(transcript, action))
        feats[f"informative_{action}"] = float(
            bool(compose_remain) and scored["score"] < float(len(compose_remain)) - 1e-12
        )
        feats[f"last_{action}"] = float(last_act == action)
    return dict(features=feats, score_work=work)


def choose_fixed_synthesis(language_remain: list[str], compose_remain: list[tuple[str, ...]],
                           available: list[str]) -> dict[str, Any]:
    if not compose_remain:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="compose_empty")
    if len(observational_groups(compose_remain)) == 1 and "STOP_EQUIVALENT" in available:
        return dict(action="STOP_EQUIVALENT", score_work=0, reason="one_class")
    for action in DIAGNOSTIC_ORDER:
        if action in available:
            return dict(action=action, score_work=0, reason="fixed_synthesis")
    return dict(action="STOP_EQUIVALENT" if "STOP_EQUIVALENT" in available else "STOP_UNRESOLVED",
                score_work=0, reason="fixed_exhausted")


def observational_groups(remaining: list[tuple[str, ...]]) -> list[list[tuple[str, ...]]]:
    from .mechanism_compose import signature
    groups: dict[Any, list[tuple[str, ...]]] = {}
    for parts in remaining:
        groups.setdefault(signature(parts), []).append(parts)
    return list(groups.values())


def choose_catalogue_only(language_remain: list[str], available: list[str],
                          transcript: list[dict[str, Any]]) -> dict[str, Any]:
    return choose_diagnostic(language_remain, transcript, available)


def choose_composition_ig(compose_remain: list[tuple[str, ...]],
                          transcript: list[dict[str, Any]], available: list[str],
                          rng: random.Random) -> dict[str, Any]:
    if not compose_remain:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    if len(observational_groups(compose_remain)) == 1 and "STOP_EQUIVALENT" in available:
        return dict(action="STOP_EQUIVALENT", score_work=0, reason="one_class")
    scored = []
    work = 0
    for action in available:
        if action.startswith("STOP"):
            continue
        row = score_compose_gain(compose_remain, transcript, action)
        work += int(row["work"])
        scored.append((row["score"], action))
    if not scored:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="no_query")
    best = min(value for value, _action in scored)
    tied = [action for value, action in scored if value == best]
    return dict(action=rng.choice(tied), score_work=work, reason="compose_ig")


def _chooser(method: str, weights: dict[str, list[float]]) -> Callable:
    def choose(ctx: dict[str, Any]) -> dict[str, Any]:
        language_remain = ctx["language_remain"]
        compose_remain = ctx["compose_remain"]
        available = ctx["available"]
        transcript = ctx["transcript"]
        rng = ctx["rng"]
        if method == "fixed_synthesis":
            return choose_fixed_synthesis(language_remain, compose_remain, available)
        if method == "catalogue_only":
            return choose_catalogue_only(language_remain, available, transcript)
        if method == "composition_ig":
            return choose_composition_ig(compose_remain, transcript, available, rng)
        picked = select_action(weights, ctx["features"], available, rng)
        return dict(action=picked["selected"], score_work=0, reason=picked["reason"])
    return choose


def run_holdout(task: dict[str, Any], parts: tuple[str, ...] | None) -> list[dict[str, Any]]:
    from .mechanism_compose import apply_pipeline
    hidden = blank_state(int(task["instance_seed"]) + 10007)
    hypo = dict(s=0, prev=0)
    rows = []
    for action in HOLDOUT_PROBES:
        observed = apply_hidden(task["mechanism"], hidden, action)
        hidden = observed["state"]
        predicted = None
        if parts is not None:
            guessed = apply_pipeline(parts, hypo, action)
            hypo = guessed["state"]
            predicted = guessed["observation"]
        rows.append(dict(
            action=action, observed=observed["observation"],
            predicted=predicted, oracle=int(observed["oracle"]),
        ))
    return rows


def run_acquire(task: dict[str, Any], method: str, weights: dict[str, list[float]],
                rng: random.Random) -> dict[str, Any]:
    chooser = _chooser(method, weights)
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    score_work = 0
    oracle = 0
    actions = 0
    stopped = None
    identified = None
    for step in range(MAX_STEPS):
        language_remain = filter_language(transcript)
        compose_remain = filter_compositions(transcript)
        built = compose_features(transcript, compose_remain, MAX_STEPS - step)
        feats = built["features"]
        score_work += int(built["score_work"])
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        avail = acquire_available(transcript, language_remain, compose_remain)
        score_work += int(avail["score_work"])
        choice = chooser(dict(
            language_remain=language_remain, compose_remain=compose_remain,
            available=avail["actions"], transcript=transcript, features=feats,
            rng=rng, view={},
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
            break
        applied = apply_hidden(task["mechanism"], hidden, action)
        hidden = applied["state"]
        oracle += int(applied["oracle"])
        transcript.append(dict(
            action=action, observation=applied["observation"],
            oracle=int(applied["oracle"]), remaining=list(language_remain),
            features=feats, reason=choice.get("reason"),
        ))
    else:
        stopped = "budget"
    language_remain = filter_language(transcript)
    synthesized = synthesize(transcript)
    score_work += int(synthesized["score_work"])
    if method == "catalogue_only":
        parts = parse_pipe(language_remain[0]) if len(language_remain) == 1 and language_remain[0] in PRIMITIVES else None
        synthesized = dict(
            remaining=list(language_remain), classes=[list(language_remain)] if language_remain else [],
            representative=language_remain[0] if language_remain else None,
            n_remaining=len(language_remain), n_classes=int(bool(language_remain)),
            score_work=0, primitives=list(PRIMITIVES), primitive_origin=PRIMITIVE_ORIGIN,
            stored_language=list(LANGUAGE),
        )
    else:
        parts = parse_pipe(synthesized.get("representative"))
    holdout = run_holdout(task, parts)
    claims = score_claims(task, language_remain, synthesized, identified, stopped, holdout)
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        method=method,
        transcript=transcript,
        synthesized=synthesized,
        holdout=holdout,
        stopped=stopped,
        identified=identified,
        remaining=list(language_remain),
        oracle=oracle + sum(int(row["oracle"]) for row in holdout),
        investigate_oracle=oracle,
        action_steps=actions + len(holdout),
        score_work=score_work,
        total_work=oracle + actions + score_work + sum(int(row["oracle"]) for row in holdout),
        interactions=len([row for row in transcript if not str(row["action"]).startswith("STOP")]) + len(holdout),
        **claims,
        language_hash=language_hash(),
        instance_seed=task["instance_seed"],
        solutions_reset=True,
    )


def run_method(tasks: list[dict[str, Any]], method: str, weights: dict[str, list[float]],
               seed: int) -> list[dict[str, Any]]:
    rows = []
    for index, task in enumerate(tasks):
        rng = random.Random(seed * 1009 + index * 17 + 11)
        episode = run_acquire(task, method, weights, rng)
        episode["policy_seed"] = seed
        rows.append(episode)
    return rows


def acquire_training_rows(episode: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    first = True
    prefix: list[dict[str, Any]] = []
    rng = random.Random(3)
    for step in episode.get("transcript") or []:
        compose_remain = filter_compositions(prefix)
        avail = acquire_available(prefix, filter_language(prefix), compose_remain)
        expert = choose_composition_ig(compose_remain, prefix, avail["actions"], rng)
        for action in list(QUERY_ACTIONS) + list(ACQUIRE_STOPS):
            rows.append(dict(
                action=action,
                features=dict(step["features"]),
                label=1.0 if action == expert["action"] else 0.0,
                first_query=first and not expert["action"].startswith("STOP"),
                chosen=expert["action"],
                supervision="dagger_composition_ig",
            ))
        prefix.append(step)
        first = False
    return rows


def fit_acquire(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    labels = {action: [] for action in ACTIONS}
    labels.update({action: [] for action in ACQUIRE_STOPS})
    xs = {action: [] for action in labels}
    for row in rows:
        action = row["action"]
        if action not in xs:
            continue
        xs[action].append(feature_vector(row["features"]))
        labels[action].append(float(row["label"]))
    import numpy as np
    weights = {action: [0.0] * len(FEATURE_NAMES) for action in labels}
    for action, matrix in xs.items():
        if not matrix:
            continue
        x = np.asarray(matrix, dtype=float)
        y = np.asarray(labels[action], dtype=float)
        xtx = x.T @ x + np.eye(x.shape[1])
        weights[action] = np.linalg.solve(xtx, x.T @ y).tolist()
    return weights


def zero_acquire() -> dict[str, list[float]]:
    keys = list(ACTIONS) + [stop for stop in ACQUIRE_STOPS if stop not in ACTIONS]
    return {action: [0.0] * len(FEATURE_NAMES) for action in keys}


def _with_stops(weights: dict[str, list[float]]) -> dict[str, list[float]]:
    merged = zero_acquire()
    merged.update(weights)
    return merged


def score_columns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, useful_acquisition=0, predictive_competence=0,
            catalogue_identification=0, exact_mechanism_identification=0,
            scoped_match=0, guessed_generator=0, claimed_exact=0,
            interactions=0, oracle=0, total_work=0,
        ))
        cell["n"] += 1
        for key in (
            "useful_acquisition", "predictive_competence", "catalogue_identification",
            "exact_mechanism_identification", "scoped_match", "guessed_generator",
            "claimed_exact",
        ):
            cell[key] += int(bool(row.get(key)))
        for key in ("interactions", "oracle", "total_work"):
            cell[key] += int(row.get(key) or 0)
    for cell in out.values():
        n = max(cell["n"], 1)
        cell["mean_interactions"] = cell["interactions"] / n
        cell["mean_oracle"] = cell["oracle"] / n
        cell["mean_work"] = cell["total_work"] / n
    return out


def synthesis_works(rows: list[dict[str, Any]]) -> dict[str, Any]:
    synth = [row for row in rows if row["method"] == "fixed_synthesis"]
    catalogue = [row for row in rows if row["method"] == "catalogue_only"]
    report = dict(
        n=len(synth),
        useful=sum(int(row["useful_acquisition"]) for row in synth),
        predictive=sum(int(row["predictive_competence"]) for row in synth),
        guessed=sum(int(row["guessed_generator"]) for row in synth),
        exact=sum(int(row["exact_mechanism_identification"]) for row in synth),
        catalogue_useful=sum(int(row["useful_acquisition"]) for row in catalogue),
        catalogue_predictive=sum(int(row["predictive_competence"]) for row in catalogue),
    )
    report["passed"] = bool(
        synth
        and report["useful"] == report["n"]
        and report["predictive"] == report["n"]
        and report["guessed"] == 0
        and report["exact"] == 0
        and report["catalogue_predictive"] < report["n"]
    )
    report["reason"] = "synthesis_procedure_works" if report["passed"] else "synthesis_failure"
    return report


def _verdict(closed: bool, columns: dict[str, Any]) -> str:
    if closed:
        return "training_failure" if columns.get("trained") else "synthesis_failure"
    trained = columns.get("trained") or {}
    strongest = None
    for name in ("fixed_synthesis", "composition_ig"):
        cell = columns.get(name)
        if cell is None:
            continue
        if strongest is None or (
            int(cell.get("useful_acquisition") or 0),
            -int(cell.get("interactions") or 0),
        ) > (
            int(strongest.get("useful_acquisition") or 0),
            -int(strongest.get("interactions") or 0),
        ):
            strongest = dict(cell, name=name)
    if strongest is None:
        return "synthesis_failure"
    if int(trained.get("useful_acquisition") or 0) < int(strongest.get("useful_acquisition") or 0):
        return "negative"
    if int(trained.get("useful_acquisition") or 0) == int(strongest.get("useful_acquisition") or 0):
        if int(trained.get("interactions") or 0) < int(strongest.get("interactions") or 0):
            return "useful learned investigation advantage"
        return "fixed-baseline tie"
    return "useful learned investigation advantage"


def run_acquire_study(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = synthesis_source_tasks()
    gate = synthesis_gate_tasks()
    holdout = synthesis_holdout_tasks()
    if any(row["task_id"] in OPENED_IDS for row in source + gate + holdout):
        raise ValueError("opened_id_in_challenge")
    gate_rows = []
    for method in ("fixed_synthesis", "catalogue_only"):
        gate_rows.extend(run_method(gate, method, zero_acquire(), seed=7))
    works = synthesis_works(gate_rows)
    assess_rows: list[dict[str, Any]] = []
    competence_rows = []
    reports = []
    seeds_used = []
    passed = []
    closed = not works["passed"]
    if works["passed"]:
        for seed in TRAIN_SEEDS:
            source_run = run_method(source, "composition_ig", zero_acquire(), seed=5 + seed)
            supervised = []
            for episode in source_run:
                supervised.extend(acquire_training_rows(episode))
            weights = fit_acquire(supervised)
            own = run_method(source, "trained", weights, seed=30 + seed)
            for episode in own:
                supervised.extend(acquire_training_rows(episode))
            weights = fit_acquire(supervised)
            frozen = policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS})
            own_src = run_method(source, "trained", weights, seed=11 + seed)
            report = dict(
                n=len(own_src),
                useful=sum(int(row["useful_acquisition"]) for row in own_src),
                passed=all(row["useful_acquisition"] for row in own_src),
                seed=seed,
                policy_hash=frozen,
            )
            reports.append(report)
            competence_rows.extend(own_src)
            seeds_used.append(dict(seed=seed, policy_hash=frozen, competence=report["passed"]))
            if report["passed"]:
                passed.append(dict(seed=seed, weights=weights, hash=frozen))
        closed = not (passed and all(row["passed"] for row in reports))
        if not closed:
            for block in passed:
                seed = block["seed"]
                for method, used in (
                    ("trained", _with_stops(block["weights"])),
                    ("reset_policy", zero_acquire()),
                    ("shuffled_policy", _with_stops(shuffle_weights(
                        {action: block["weights"].get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS},
                        100 + seed,
                    ))),
                    ("fixed_synthesis", zero_acquire()),
                    ("catalogue_only", zero_acquire()),
                    ("composition_ig", zero_acquire()),
                ):
                    assess_rows.extend(run_method(holdout, method, used, seed=20 + seed))
    columns = score_columns(assess_rows)
    verdict = _verdict(closed, columns)
    payload = dict(
        kind=KIND,
        confirmation=False,
        learning_to_learn_established=False,
        ranking_paused=True,
        prior_assessments_closed=list(PRIOR_CLOSED),
        opened_ids_not_rescored=sorted(OPENED_IDS),
        assessment_closed=closed,
        language=list(LANGUAGE),
        language_hash=language_hash(),
        primitives=list(PRIMITIVES),
        primitive_origin=PRIMITIVE_ORIGIN,
        splits=split_lock(),
        feature_names=list(FEATURE_NAMES),
        claims=("catalogue_identification", "predictive_competence", "exact_mechanism_identification"),
        synthesis_gate=works,
        gate_episodes=gate_rows,
        competence=dict(reports=reports, passed=bool(passed) and all(row["passed"] for row in reports),
                        n_passed=len(passed)),
        competence_episodes=competence_rows,
        policy_seeds=seeds_used,
        assessment=assess_rows,
        columns=columns,
        verdict=verdict,
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
            guessed_generator_not_rewarded=True,
            synthesis_must_work_first=True,
            task_solutions_reset=True,
        ),
    )
    payload["hash"] = digest({
        "synthesis_gate": works,
        "columns": columns,
        "verdict": verdict,
        "assessment_closed": closed,
    })
    (directory / "seed_mechanism_acquire.json").write_text(
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
    for row in (payload.get("gate_episodes") or []) + (payload.get("assessment") or []):
        if row["task_id"] in OPENED_IDS:
            ok = False
            notes.append("rescored_opened:" + row["task_id"])
        if row.get("exact_mechanism_identification"):
            ok = False
            notes.append("exact_claimed:" + row["task_id"])
        if row.get("guessed_generator") and row.get("useful_acquisition"):
            ok = False
            notes.append("rewarded_generator_guess:" + row["task_id"])
    if payload.get("assessment_closed") and payload.get("assessment"):
        ok = False
        notes.append("closed_but_assessed")
    rebuilt = score_columns(payload.get("assessment") or [])
    saved = payload.get("columns") or {}
    if rebuilt and saved:
        for name, cell in rebuilt.items():
            other = saved.get(name) or {}
            for key in ("useful_acquisition", "predictive_competence", "interactions", "oracle"):
                if cell.get(key) != other.get(key):
                    ok = False
                    notes.append("column:" + name + ":" + key)
    return dict(valid=ok, notes=notes, n=len(payload.get("assessment") or []) + len(payload.get("gate_episodes") or []))
