"""Version-space investigation over executed mechanisms.

Completeness: STOP_IDENTIFY is correct only when the full language is a
singleton. Shortlist agreement is not identification. Ties are randomized.
"""
from __future__ import annotations

import math
import random
from typing import Any

from .capability_evidence import digest
from .mechanism_world import (
    ACTIONS, ACTION_COST, ACT_INPUTS, LANGUAGE, MAX_STEPS, ORACLE_COST,
    advance_candidate, apply_hidden, blank_state, candidate_observation,
)

FEATURE_NAMES = (
    "n_remaining_frac",
    "log_remaining",
    "n_oracle",
    "n_actions",
    "n_score_work",
    "n_unique_obs",
    "last_nonneg",
    "last_zero",
    "budget_left_frac",
    "vs_empty",
    "vs_singleton",
    "did_reset",
    "did_measure",
    "last_was_act",
)
DIAGNOSTIC_ORDER = ("ACT_1", "ACT_0", "ACT_2", "ACT_NEG", "RESET", "MEASURE")
HIDDEN = {"task_id", "family", "mechanism", "split", "gold", "in_language"}


def public_view(task: dict[str, Any]) -> dict[str, Any]:
    return dict(
        interface="act(x) observes the hidden mechanism; RESET clears state; MEASURE is exact and costs 3.",
        actions=list(ACTIONS),
        language=list(LANGUAGE),
        max_steps=MAX_STEPS,
        instance_seed=int(task["instance_seed"]),
    )


def filter_language(transcript: list[dict[str, Any]]) -> list[str]:
    remain = []
    for name in LANGUAGE:
        states = {name: dict(s=0, prev=0)}
        ok = True
        for row in transcript:
            action = row["action"]
            if action.startswith("STOP"):
                continue
            predicted = candidate_observation(name, states[name], action)
            states[name] = advance_candidate(name, states[name], action)
            if predicted is None:
                continue
            if int(row["observation"]) not in predicted:
                ok = False
                break
        if ok:
            remain.append(name)
    return remain


def features(transcript: list[dict[str, Any]], remaining: list[str],
             score_work: int, steps_left: int) -> dict[str, float]:
    last = next((row for row in reversed(transcript) if row.get("observation") is not None), None)
    last_y = None if last is None else int(last["observation"])
    acts = [row["action"] for row in transcript]
    return dict(
        n_remaining_frac=len(remaining) / float(len(LANGUAGE)),
        log_remaining=math.log2(len(remaining) + 1),
        n_oracle=float(sum(int(row.get("oracle") or 0) for row in transcript)),
        n_actions=float(len(transcript)),
        n_score_work=float(score_work),
        n_unique_obs=float(len({row["observation"] for row in transcript if row.get("observation") is not None})),
        last_nonneg=float(last_y is not None and last_y >= 0),
        last_zero=float(last_y == 0),
        budget_left_frac=steps_left / float(MAX_STEPS),
        vs_empty=float(not remaining),
        vs_singleton=float(len(remaining) == 1),
        did_reset=float("RESET" in acts),
        did_measure=float("MEASURE" in acts),
        last_was_act=float(bool(acts) and acts[-1] in ACT_INPUTS),
    )


def feature_vector(feats: dict[str, float]) -> list[float]:
    return [float(feats[name]) for name in FEATURE_NAMES]


def available_actions(_view: dict[str, Any], _transcript: list[dict[str, Any]],
                      _remaining: list[str]) -> list[str]:
    """Shared operational mask. Does not hide STOP_* or reveal the winner."""
    return list(ACTIONS)


def score_information_gain(remaining: list[str], transcript: list[dict[str, Any]],
                           action: str) -> dict[str, Any]:
    """Expected remaining-set size. Charges one candidate execution per remaining hypothesis."""
    if action.startswith("STOP") or not remaining:
        return dict(score=float(len(remaining)), work=0, groups={})
    groups: dict[str, list[str]] = {}
    work = 0
    for name in remaining:
        state = dict(s=0, prev=0)
        for row in transcript:
            if row["action"].startswith("STOP"):
                continue
            state = advance_candidate(name, state, row["action"])
        predicted = candidate_observation(name, state, action)
        work += 1
        key = "none" if predicted is None else ",".join(str(v) for v in sorted(predicted))
        groups.setdefault(key, []).append(name)
    expected = sum(len(group) ** 2 for group in groups.values()) / float(len(remaining))
    return dict(score=float(expected), work=work, groups=groups)


def choose_information_gain(remaining: list[str], transcript: list[dict[str, Any]],
                            available: list[str], rng: random.Random) -> dict[str, Any]:
    scored = []
    work = 0
    for action in available:
        if action.startswith("STOP"):
            continue
        row = score_information_gain(remaining, transcript, action)
        work += int(row["work"])
        scored.append((row["score"], action))
    if remaining and "STOP_IDENTIFY" in available and len(remaining) == 1:
        return dict(action="STOP_IDENTIFY", score_work=work, reason="unique")
    if not remaining and "STOP_UNRESOLVED" in available:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="empty")
    if not scored:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="no_query")
    best = min(value for value, _action in scored)
    tied = [action for value, action in scored if value == best]
    return dict(action=rng.choice(tied), score_work=work, reason="ig_tie" if len(tied) > 1 else "ig")


def choose_diagnostic(remaining: list[str], transcript: list[dict[str, Any]],
                      available: list[str]) -> dict[str, Any]:
    if len(remaining) == 1:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    used = {row["action"] for row in transcript}
    for action in DIAGNOSTIC_ORDER:
        if action in available and action not in used:
            return dict(action=action, score_work=0, reason="diagnostic")
    return dict(action="STOP_UNRESOLVED", score_work=0, reason="diagnostic_exhausted")


def choose_frequency(remaining: list[str], available: list[str], order: list[str],
                     transcript: list[dict[str, Any]]) -> dict[str, Any]:
    if len(remaining) == 1:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    used = {row["action"] for row in transcript}
    for action in order:
        if action in available and action not in used and not action.startswith("STOP"):
            return dict(action=action, score_work=0, reason="frequency")
    return dict(action="STOP_UNRESOLVED", score_work=0, reason="frequency_exhausted")


def choose_random(remaining: list[str], available: list[str], rng: random.Random) -> dict[str, Any]:
    if len(remaining) == 1:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    choices = [action for action in available if not action.startswith("STOP")]
    return dict(action=rng.choice(choices), score_work=0, reason="random")


def outcome(task: dict[str, Any], remaining: list[str], stopped: str | None,
            identified: str | None) -> dict[str, Any]:
    gold = task["mechanism"]
    in_language = gold in LANGUAGE
    unresolved = stopped == "STOP_UNRESOLVED" or identified is None
    unique = len(remaining) == 1
    correct_id = bool(identified == gold and unique)
    correct_unresolved = bool(unresolved and not in_language)
    premature = stopped == "STOP_IDENTIFY" and not unique
    wrong_id = bool(identified is not None and identified != gold)
    success = correct_id or correct_unresolved
    return dict(
        success=success,
        correct_id=correct_id,
        correct_unresolved=correct_unresolved,
        premature=premature,
        wrong_id=wrong_id,
        unresolved=unresolved,
        identified=identified,
        gold_in_language=in_language,
        remaining=list(remaining),
    )


def run_episode(task: dict[str, Any], chooser, rng: random.Random) -> dict[str, Any]:
    view = public_view(task)
    hidden = blank_state(int(task["instance_seed"]))
    transcript: list[dict[str, Any]] = []
    remaining = list(LANGUAGE)
    score_work = 0
    oracle = 0
    actions = 0
    stopped = None
    identified = None
    for step in range(MAX_STEPS):
        remaining = filter_language(transcript)
        feats = features(transcript, remaining, score_work, MAX_STEPS - step)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        avail = available_actions(view, transcript, remaining)
        choice = chooser(dict(
            remaining=remaining, transcript=transcript, available=avail,
            features=feats, rng=rng, view=view,
        ))
        action = choice["action"]
        score_work += int(choice.get("score_work") or 0)
        actions += ACTION_COST[action]
        if action == "STOP_IDENTIFY":
            identified = remaining[0] if len(remaining) == 1 else None
            stopped = action
            transcript.append(dict(action=action, observation=None, oracle=0,
                                   remaining=list(remaining), features=feats,
                                   reason=choice.get("reason")))
            break
        if action == "STOP_UNRESOLVED":
            stopped = action
            transcript.append(dict(action=action, observation=None, oracle=0,
                                   remaining=list(remaining), features=feats,
                                   reason=choice.get("reason")))
            break
        applied = apply_hidden(task["mechanism"], hidden, action)
        hidden = applied["state"]
        oracle += int(applied["oracle"])
        transcript.append(dict(
            action=action, observation=applied["observation"],
            oracle=int(applied["oracle"]), remaining=list(remaining),
            features=feats, reason=choice.get("reason"),
        ))
    else:
        remaining = filter_language(transcript)
        stopped = "budget"
    remaining = filter_language(transcript)
    scored = outcome(task, remaining, stopped, identified)
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        transcript=transcript,
        oracle=oracle,
        action_steps=actions,
        score_work=score_work,
        total_work=oracle + actions + score_work,
        stopped=stopped,
        **scored,
        language_hash=digest(list(LANGUAGE)),
        instance_seed=task["instance_seed"],
    )
