"""Version-space investigation over executed mechanisms.

Features must distinguish a still-informative query from one whose
answer is already known. Completeness: STOP_IDENTIFY only when the full
language is a singleton. The redundant-query mask is programmer-supplied
and shared by every method.
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

QUERY_ACTIONS = ("ACT_0", "ACT_1", "ACT_2", "ACT_NEG", "RESET", "MEASURE")
FEATURE_NAMES = (
    "n_remaining_frac",
    "n_remaining",
    "log_remaining",
    "n_actions",
    "budget_left_frac",
    "vs_empty",
    "vs_singleton",
    "identification_supported",
    "last_obs_scaled",
    "last_obs_missing",
    *(f"used_{name}" for name in QUERY_ACTIONS),
    *(f"informative_{name}" for name in QUERY_ACTIONS),
    *(f"last_{name}" for name in QUERY_ACTIONS),
)
DIAGNOSTIC_ORDER = ("ACT_1", "ACT_0", "ACT_2", "ACT_NEG", "RESET", "MEASURE")
HIDDEN = {"task_id", "family", "mechanism", "split", "gold", "in_language"}
REDUNDANT_MASK_ORIGIN = "programmer_supplied"
SUPPORT_RULE_ORIGIN = "programmer_supplied"


def public_view(task: dict[str, Any]) -> dict[str, Any]:
    return dict(
        interface="act(x) observes the hidden mechanism; RESET clears state; MEASURE is exact and costs 3.",
        actions=list(ACTIONS),
        language=list(LANGUAGE),
        max_steps=MAX_STEPS,
        instance_seed=int(task["instance_seed"]),
        redundant_mask=REDUNDANT_MASK_ORIGIN,
    )


def filter_language(transcript: list[dict[str, Any]]) -> list[str]:
    remain = []
    for name in LANGUAGE:
        state = dict(s=0, prev=0)
        ok = True
        for row in transcript:
            action = row["action"]
            if action.startswith("STOP"):
                continue
            predicted = candidate_observation(name, state, action)
            state = advance_candidate(name, state, action)
            if predicted is None:
                continue
            if int(row["observation"]) not in predicted:
                ok = False
                break
        if ok:
            remain.append(name)
    return remain


def used_since_reset(transcript: list[dict[str, Any]], action: str) -> bool:
    for row in reversed(transcript):
        if row["action"] == "RESET":
            return False
        if row["action"] == action:
            return True
    return False


def score_information_gain(remaining: list[str], transcript: list[dict[str, Any]],
                           action: str) -> dict[str, Any]:
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
    expected = sum(len(group) ** 2 for group in groups.values()) / float(max(len(remaining), 1))
    return dict(score=float(expected), work=work, groups=groups)


def query_is_informative(remaining: list[str], transcript: list[dict[str, Any]],
                         action: str) -> dict[str, Any]:
    """True when remaining hypotheses do not all predict the same observation."""
    scored = score_information_gain(remaining, transcript, action)
    informative = bool(remaining) and scored["score"] < float(len(remaining)) - 1e-12
    return dict(informative=informative, work=int(scored["work"]), groups=scored["groups"])


def is_redundant(action: str, transcript: list[dict[str, Any]],
                 remaining: list[str]) -> dict[str, Any]:
    """Repeat of a deterministic query that cannot change the version space.

    Programmer-supplied. Shared by every method. Repeats stay legal when any
    remaining hypothesis still disagrees or would change under another act
    (stateful / cheap-vs-exact).
    """
    if action.startswith("STOP") or action == "RESET":
        return dict(redundant=False, work=0, informative=True)
    checked = query_is_informative(remaining, transcript, action)
    if not used_since_reset(transcript, action):
        return dict(redundant=False, work=checked["work"], informative=checked["informative"])
    return dict(
        redundant=not checked["informative"],
        work=checked["work"],
        informative=checked["informative"],
    )


def first_singleton_index(transcript: list[dict[str, Any]]) -> int | None:
    prefix: list[dict[str, Any]] = []
    for index, row in enumerate(transcript):
        prefix.append(row)
        if len(filter_language(prefix)) == 1:
            return index
    return None


def identification_supported(remaining: list[str], transcript: list[dict[str, Any]]) -> bool:
    """Catalogue singleton is not identification. Need one later probe that held."""
    if len(remaining) != 1:
        return False
    start = first_singleton_index(transcript)
    if start is None:
        return False
    later = [
        row for row in transcript[start + 1:]
        if not str(row["action"]).startswith("STOP")
    ]
    return bool(later) and len(filter_language(transcript)) == 1


def available_actions(_view: dict[str, Any], transcript: list[dict[str, Any]],
                      remaining: list[str]) -> dict[str, Any]:
    """Shared mask. STOP_IDENTIFY is legal only after a post-singleton probe."""
    kept = []
    work = 0
    supported = identification_supported(remaining, transcript)
    for action in ACTIONS:
        checked = is_redundant(action, transcript, remaining)
        work += int(checked["work"])
        if checked["redundant"]:
            continue
        if action == "STOP_IDENTIFY" and not supported:
            continue
        kept.append(action)
    return dict(
        actions=kept, score_work=work, mask=REDUNDANT_MASK_ORIGIN,
        support_rule=SUPPORT_RULE_ORIGIN, identification_supported=supported,
    )


def features(transcript: list[dict[str, Any]], remaining: list[str],
             score_work: int, steps_left: int) -> dict[str, Any]:
    last = next((row for row in reversed(transcript) if row.get("observation") is not None), None)
    last_y = None if last is None else int(last["observation"])
    last_act = transcript[-1]["action"] if transcript else None
    work = 0
    informative = {}
    used = {}
    for action in QUERY_ACTIONS:
        used[action] = used_since_reset(transcript, action)
        checked = query_is_informative(remaining, transcript, action)
        informative[action] = checked["informative"]
        work += int(checked["work"])
    feats = dict(
        n_remaining_frac=len(remaining) / float(len(LANGUAGE)),
        n_remaining=float(len(remaining)),
        log_remaining=math.log2(len(remaining) + 1),
        n_actions=float(len(transcript)),
        budget_left_frac=steps_left / float(MAX_STEPS),
        vs_empty=float(not remaining),
        vs_singleton=float(len(remaining) == 1),
        identification_supported=float(identification_supported(remaining, transcript)),
        last_obs_scaled=0.0 if last_y is None else max(-8, min(8, last_y)) / 8.0,
        last_obs_missing=float(last_y is None),
    )
    for action in QUERY_ACTIONS:
        feats[f"used_{action}"] = float(used[action])
        feats[f"informative_{action}"] = float(informative[action])
        feats[f"last_{action}"] = float(last_act == action)
    return dict(features=feats, score_work=work)


def feature_vector(feats: dict[str, float]) -> list[float]:
    return [float(feats[name]) for name in FEATURE_NAMES]


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
    if len(remaining) == 1 and "STOP_IDENTIFY" in available:
        return dict(action="STOP_IDENTIFY", score_work=work, reason="unique")
    if not remaining and "STOP_UNRESOLVED" in available:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="empty")
    if not scored:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="no_query")
    best = min(value for value, _action in scored)
    tied = [action for value, action in scored if value == best]
    return dict(action=rng.choice(tied), score_work=work, reason="ig_tie" if len(tied) > 1 else "ig")


def probe_charge(action: str) -> int:
    """Oracle cost, or one step when the oracle charge is zero (RESET)."""
    return int(ORACLE_COST.get(action) or ACTION_COST.get(action) or 1)


def choose_cost_aware_ig(remaining: list[str], transcript: list[dict[str, Any]],
                         available: list[str], rng: random.Random) -> dict[str, Any]:
    """Information gain per charged cost. MEASURE is used only if it pays."""
    if len(remaining) == 1 and "STOP_IDENTIFY" in available:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    scored = []
    work = 0
    for action in available:
        if action.startswith("STOP"):
            continue
        row = score_information_gain(remaining, transcript, action)
        work += int(row["work"])
        gain = float(len(remaining)) - float(row["score"])
        scored.append((gain / float(probe_charge(action)), gain, action))
    if len(remaining) == 1:
        cheap = [action for action in available if not action.startswith("STOP")]
        if not cheap:
            return dict(action="STOP_UNRESOLVED", score_work=work, reason="no_confirm")
        charged = [(probe_charge(action), action) for action in cheap]
        best = min(cost for cost, _action in charged)
        tied = [action for cost, action in charged if cost == best]
        return dict(action=rng.choice(tied), score_work=work, reason="confirm_cheap")
    if not scored or max(gain for _ratio, gain, _action in scored) < 1e-12:
        return dict(action="STOP_UNRESOLVED", score_work=work, reason="no_split")
    best = max(ratio for ratio, _gain, _action in scored)
    tied = [action for ratio, _gain, action in scored if abs(ratio - best) < 1e-12]
    return dict(action=rng.choice(tied), score_work=work,
                reason="cost_ig_tie" if len(tied) > 1 else "cost_ig")


def choose_diagnostic_measure(remaining: list[str], transcript: list[dict[str, Any]],
                              available: list[str]) -> dict[str, Any]:
    """Diagnostic order, then a confirmation MEASURE charged at full cost."""
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    if len(remaining) == 1:
        if "MEASURE" in available and not used_since_reset(transcript, "MEASURE"):
            return dict(action="MEASURE", score_work=0, reason="confirm_measure")
        if "STOP_IDENTIFY" in available:
            return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    for action in DIAGNOSTIC_ORDER:
        if action in available:
            return dict(action=action, score_work=0, reason="diagnostic_measure")
    return dict(action="STOP_UNRESOLVED", score_work=0, reason="diagnostic_measure_exhausted")


def choose_diagnostic(remaining: list[str], transcript: list[dict[str, Any]],
                      available: list[str]) -> dict[str, Any]:
    if len(remaining) == 1 and "STOP_IDENTIFY" in available:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    for action in DIAGNOSTIC_ORDER:
        if action in available:
            return dict(action=action, score_work=0, reason="diagnostic")
    return dict(action="STOP_UNRESOLVED", score_work=0, reason="diagnostic_exhausted")


def choose_frequency(remaining: list[str], available: list[str], order: list[str],
                     transcript: list[dict[str, Any]]) -> dict[str, Any]:
    if len(remaining) == 1 and "STOP_IDENTIFY" in available:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    for action in order:
        if action in available and not action.startswith("STOP"):
            return dict(action=action, score_work=0, reason="frequency")
    return dict(action="STOP_UNRESOLVED", score_work=0, reason="frequency_exhausted")


def choose_random(remaining: list[str], available: list[str], rng: random.Random) -> dict[str, Any]:
    if len(remaining) == 1 and "STOP_IDENTIFY" in available:
        return dict(action="STOP_IDENTIFY", score_work=0, reason="unique")
    if not remaining:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="empty")
    choices = [action for action in available if not action.startswith("STOP")]
    if not choices:
        return dict(action="STOP_UNRESOLVED", score_work=0, reason="random_empty")
    return dict(action=rng.choice(choices), score_work=0, reason="random")


def outcome(task: dict[str, Any], remaining: list[str], stopped: str | None,
            identified: str | None, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    gold = task["mechanism"]
    in_language = gold in LANGUAGE
    unresolved = stopped == "STOP_UNRESOLVED" or identified is None
    unique = len(remaining) == 1
    supported = identification_supported(remaining, transcript)
    correct_id = bool(identified == gold and unique and supported)
    correct_unresolved = bool(unresolved and not in_language)
    premature = stopped == "STOP_IDENTIFY" and not supported
    wrong_id = bool(identified is not None and identified != gold)
    demonstrated_inconsistency = bool(not remaining) and unresolved
    unresolved_uncertainty = bool(remaining) and unresolved
    success = correct_id or correct_unresolved
    return dict(
        success=success,
        correct_id=correct_id,
        correct_unresolved=correct_unresolved,
        premature=premature,
        wrong_id=wrong_id,
        unresolved=unresolved,
        demonstrated_inconsistency=demonstrated_inconsistency,
        unresolved_uncertainty=unresolved_uncertainty,
        identified=identified,
        gold_in_language=in_language,
        remaining=list(remaining),
        identification_supported=supported,
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
    redundant_taken = 0
    for step in range(MAX_STEPS):
        remaining = filter_language(transcript)
        built = features(transcript, remaining, score_work, MAX_STEPS - step)
        feats = built["features"]
        score_work += int(built["score_work"])
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        avail = available_actions(view, transcript, remaining)
        score_work += int(avail["score_work"])
        choice = chooser(dict(
            remaining=remaining, transcript=transcript, available=avail["actions"],
            features=feats, rng=rng, view=view,
        ))
        action = choice["action"]
        if action not in avail["actions"]:
            raise ValueError("chose_masked_action:" + action)
        checked = is_redundant(action, transcript, remaining)
        score_work += int(checked["work"])
        if checked["redundant"]:
            redundant_taken += 1
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
    scored = outcome(task, remaining, stopped, identified, transcript)
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
        redundant_taken=redundant_taken,
        redundant_mask=REDUNDANT_MASK_ORIGIN,
        **scored,
        measured=any(step["action"] == "MEASURE" for step in transcript),
        language_hash=digest(list(LANGUAGE)),
        instance_seed=task["instance_seed"],
    )
