"""Equal-access recovery evaluation. Fixture path has no language-model calls.

Initial public failures are shared across methods. Capsules and solution
caches are not used. Assessment stays locked until a live grant exists.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .recovery_actions import (
    MAX_ACTIONS, apply_evidence, available_actions, blank_evidence,
    execute_action, public_observation, run_cases,
)
from .recovery_policy import (
    choose, fit_source, frequency_order, policy_hash, reset_weights,
    shuffle_weights, zero_weights,
)
from .recovery_tasks import catalogue, public_task_view, tasks_for

METHODS = (
    "immediate_revise",
    "fixed_diagnostic",
    "source_frequency",
    "learned",
    "reset_policy",
    "shuffled_policy",
    "all_cheap_first",
)
FROZEN_CPU_USED_S = 3564.568
FROZEN_CPU_REMAINING_S = 35.432


def initial_failure(task: dict[str, Any]) -> dict[str, Any]:
    public = run_cases(task["files"], task["public"])
    if public.get("status") == "passed":
        raise ValueError("initial_solution_did_not_fail")
    return public


def score_files(task: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    public = run_cases(files, task["public"])
    private = run_cases(files, task["private"])
    return dict(
        public_passed=bool(public.get("status") == "passed"),
        private_passed=bool(private.get("status") == "passed"),
        public=public,
        private=private,
    )


def _label(task: dict[str, Any], stopped: bool, private_passed: bool) -> int:
    if not task.get("identifiable", True):
        return int(stopped)
    return int(private_passed)


def run_episode(task: dict[str, Any], method: str, weights: dict[str, list[float]],
                freq: list[str], directory: str | Path,
                initial: dict[str, Any] | None = None,
                force_first: str | None = None) -> dict[str, Any]:
    view = public_task_view(task)
    public = initial if initial is not None else initial_failure(task)
    files = dict(task["files"])
    evidence = blank_evidence(files, public)
    actions = []
    model_calls = 0
    teacher_queries = 0
    tool_executions = int(public.get("tool_executions") or 1)
    wall_s = float(public.get("wall_s") or 0.0)
    stopped = False
    first = None
    for step in range(MAX_ACTIONS):
        avail = available_actions(view, evidence)
        feats = public_observation(view, files, evidence.get("public") or public, evidence,
                                   MAX_ACTIONS - step)
        if any(key in feats for key in ("task_id", "family", "private", "reference")):
            raise ValueError("hidden_label_leakage")
        if force_first and step == 0 and force_first in avail:
            decision = dict(selected=force_first, scores={force_first: 1.0},
                            available=avail, reason="source_branch", features=feats)
        else:
            decision = choose(method, feats, avail, weights, freq)
        action = decision["selected"]
        if first is None:
            first = action
        result = execute_action(action, task, files, evidence, directory)
        evidence = apply_evidence(evidence, result)
        if result.get("files"):
            files = result["files"]
        wall_s += float(result.get("wall_s") or 0.0)
        tool_executions += int(result.get("tool_executions") or 0)
        model_calls += int(result.get("model_calls") or 0)
        teacher_queries += int(result.get("teacher_queries") or 0)
        actions.append(dict(
            step=step,
            action=action,
            available=avail,
            scores=decision["scores"],
            reason=decision["reason"],
            features=feats,
            action_available=bool(result.get("available", True)),
            wall_s=result.get("wall_s"),
            teacher_queries=result.get("teacher_queries"),
        ))
        if action == "STOP_UNRESOLVED":
            stopped = True
            break
        if action == "REVISE" and (evidence.get("public") or {}).get("status") == "passed":
            if not task.get("teacher_available") or evidence.get("distinguished") or not task.get("identifiable", True):
                break
    scored = score_files(task, files)
    unnecessary = 0
    if task.get("family") == "immediate_ok":
        unnecessary = sum(1 for row in actions if row["action"] != "REVISE" and row["action"] != "STOP_UNRESOLVED")
    return dict(
        task_id=task["task_id"],
        split=task["split"],
        method=method,
        origin=task["origin"],
        identifiable=bool(task.get("identifiable", True)),
        correct_stop=bool(task.get("correct_stop")),
        actions=[row["action"] for row in actions],
        action_log=actions,
        first_action=first,
        stopped=stopped,
        public_passed=scored["public_passed"],
        private_passed=scored["private_passed"],
        files=files,
        model_calls=model_calls,
        teacher_queries=teacher_queries,
        tool_executions=tool_executions,
        wall_s=round(wall_s, 6),
        unnecessary_diagnostics=unnecessary,
        confident_error=bool((not stopped) and (not scored["private_passed"]) and "REVISE" in [row["action"] for row in actions]),
        appropriate_stop=bool(stopped and task.get("correct_stop")),
        budget_exhausted=len(actions) >= MAX_ACTIONS and not scored["public_passed"] and not stopped,
        initial_public_status=public.get("status"),
        label=_label(task, stopped, scored["private_passed"]),
    )


def train_source(directory: str | Path) -> dict[str, Any]:
    rows = []
    branches = []
    for task in tasks_for("source"):
        initial = initial_failure(task)
        view = public_task_view(task)
        evidence = blank_evidence(task["files"], initial)
        feats = public_observation(view, task["files"], initial, evidence, MAX_ACTIONS)
        for action in available_actions(view, evidence):
            episode = run_episode(task, "fixed_diagnostic", zero_weights(), list(METHODS),
                                  directory, initial=initial, force_first=action)
            row = dict(
                action=action,
                features=feats,
                label=episode["label"],
                first_action=True,
                task_id=task["task_id"],
                private_passed=episode["private_passed"],
                wall_s=episode["wall_s"],
                tool_executions=episode["tool_executions"],
                teacher_queries=episode["teacher_queries"],
            )
            rows.append(row)
            branches.append(episode)
    weights = fit_source(rows)
    return dict(
        weights=weights,
        policy_hash=policy_hash(weights),
        frequency=frequency_order(rows),
        source_rows=rows,
        source_branches=branches,
        source_wall_s=round(sum(row["wall_s"] for row in rows), 6),
        source_tool_executions=sum(row["tool_executions"] for row in rows),
        source_teacher_queries=sum(row["teacher_queries"] for row in rows),
        source_model_calls=0,
    )


def evaluate_split(split: str, trained: dict[str, Any], directory: str | Path,
                   *, methods: tuple[str, ...] = METHODS) -> list[dict[str, Any]]:
    episodes = []
    for task in tasks_for(split):
        initial = initial_failure(task)
        for method in methods:
            if method == "learned":
                weights = trained["weights"]
            elif method == "reset_policy":
                weights = reset_weights(trained["weights"])
            elif method == "shuffled_policy":
                weights = shuffle_weights(trained["weights"], seed=7)
            else:
                weights = trained["weights"]
            episodes.append(run_episode(task, method, weights, trained["frequency"],
                                        directory, initial=initial))
    return episodes


def summarize(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = {}
    for row in episodes:
        by_method.setdefault(row["method"], []).append(row)
    out = {}
    for method, rows in by_method.items():
        ident = [row for row in rows if row["identifiable"]]
        unident = [row for row in rows if not row["identifiable"]]
        out[method] = dict(
            n=len(rows),
            identifiable_n=len(ident),
            private_correct=sum(int(row["private_passed"]) for row in ident),
            public_correct=sum(int(row["public_passed"]) for row in rows),
            appropriate_stop=sum(int(row["appropriate_stop"]) for row in unident),
            confident_errors=sum(int(row["confident_error"]) for row in rows),
            budget_exhausted=sum(int(row["budget_exhausted"]) for row in rows),
            teacher_queries=sum(row["teacher_queries"] for row in rows),
            tool_executions=sum(row["tool_executions"] for row in rows),
            model_calls=sum(row["model_calls"] for row in rows),
            wall_s=round(sum(row["wall_s"] for row in rows), 6),
            unnecessary_diagnostics=sum(row["unnecessary_diagnostics"] for row in rows),
            mean_actions=round(sum(len(row["actions"]) for row in rows) / max(1, len(rows)), 4),
        )
    return out


def strongest_simple(summary: dict[str, Any]) -> str:
    candidates = ("immediate_revise", "fixed_diagnostic", "source_frequency", "all_cheap_first")
    def key(name: str):
        row = summary[name]
        return (row["private_correct"], -row["wall_s"], -row["tool_executions"])
    return max(candidates, key=key)


def acceptance(dev_summary: dict[str, Any]) -> dict[str, Any]:
    best = strongest_simple(dev_summary)
    learned = dev_summary["learned"]
    baseline = dev_summary[best]
    better_acc = learned["private_correct"] > baseline["private_correct"]
    tie_cheaper = (
        learned["private_correct"] == baseline["private_correct"]
        and learned["tool_executions"] < baseline["tool_executions"]
    )
    accepted = better_acc or tie_cheaper
    return dict(
        strongest_simple=best,
        accepted=accepted,
        reason=(
            "learned_beats_simple_accuracy" if better_acc else
            "learned_ties_accuracy_lower_cost" if tie_cheaper else
            "retain_stronger_simple_baseline"
        ),
        reset_or_shuffle_not_sufficient=True,
    )


def live_budget_proposal() -> dict[str, Any]:
    assess_n = len(tasks_for("assessment"))
    methods = len(METHODS)
    initial_calls = assess_n
    recover_calls = assess_n * methods * 2
    source_live = len(tasks_for("source"))
    return dict(
        status="BLOCKED_BUDGET",
        closed_cpu_used_s=FROZEN_CPU_USED_S,
        closed_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
        closed_cpu_debit_s=0,
        closed_cpu_frozen=True,
        product_chat_usage_forbidden=True,
        metal_forbidden=True,
        proposed_live_model="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        proposed_assessment_tasks=assess_n,
        proposed_methods=methods,
        proposed_initial_model_calls=initial_calls,
        proposed_recovery_model_calls=recover_calls,
        proposed_source_model_calls=source_live,
        proposed_total_model_calls=initial_calls + recover_calls + source_live,
        proposed_wall_cap_s=900,
        proposed_call_timeout_s=25,
        note=(
            "Closed 3600s scientific ledger has 35.432s leftover and is frozen "
            "at 0 debit. A live 1.5B grid needs about 900s and must not spend "
            "product chat_usage or Metal. Offline fixture evaluation is complete."
        ),
    )


def run_offline(directory: str | Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    trained = train_source(directory)
    development = evaluate_split("development", trained, directory)
    retention = evaluate_split("retention", trained, directory)
    if policy_hash(trained["weights"]) != trained["policy_hash"]:
        raise ValueError("policy_hash_mutated")
    dev_summary = summarize(development)
    ret_summary = summarize(retention)
    gate = acceptance(dev_summary)
    payload = dict(
        kind="seed_recovery_policy_offline",
        confirmation=False,
        learning_to_learn_established=False,
        baseline_sha="e3d21b66785408a357d8f108231264ced4c0964b",
        live_inference=False,
        authored_fixtures_are_not_model_competence=True,
        cpu_ledger_used_s=FROZEN_CPU_USED_S,
        cpu_ledger_remaining_s=FROZEN_CPU_REMAINING_S,
        cpu_ledger_debit_s=0,
        product_chat_usage_used=False,
        metal_used=False,
        policy_hash=trained["policy_hash"],
        frequency=trained["frequency"],
        source=dict(
            rows=[{k: v for k, v in row.items() if k != "features" or True} for row in trained["source_rows"]],
            wall_s=trained["source_wall_s"],
            tool_executions=trained["source_tool_executions"],
            teacher_queries=trained["source_teacher_queries"],
            model_calls=0,
            branches=len(trained["source_branches"]),
        ),
        development=development,
        retention=retention,
        development_summary=dev_summary,
        retention_summary=ret_summary,
        acceptance=gate,
        assessment=[],
        live=live_budget_proposal(),
        config_hash=digest(load_config()),
    )
    payload["hash"] = digest({k: v for k, v in payload.items() if k != "hash"})
    return payload


def load_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "configs" / "seed_recovery_policy.json"
    return json.loads(path.read_text(encoding="utf-8"))
