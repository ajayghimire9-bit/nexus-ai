"""Completeness-preserving investigation fallback on the existing v2 engine.

Reuses EqualizedInvestigationEngineV2 ranking, EpisodeCallLedger, public task
view and Mechanism B oracles. Learned priors may reorder candidates; they do
not change evidence access, stopping, or privileged shortcuts.

Observational equivalence is reported only over explicitly identified evidence
(support demonstrations + asked oracle answers + constructed probes that were
actually evaluated). It is not a claim of universal program identity.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

Candidate = tuple[str, tuple[str, ...], Callable[[Any], Any]]


def _key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _budget_exhausted(ledger, ctrl_cfg, started: float) -> bool:
    if ctrl_cfg.max_episode_candidate_calls is not None:
        if ledger.n_candidate_calls >= ctrl_cfg.max_episode_candidate_calls:
            return True
    if ctrl_cfg.max_episode_wall_s is not None:
        if (time.perf_counter() - started) >= ctrl_cfg.max_episode_wall_s:
            return True
    return False


def _agree_on_input(survivors: list[Candidate], ledger, inp: Any, phase: str) -> tuple[bool, dict[str, Any]]:
    outcomes: dict[str, Any] = {}
    for cid, _ops, fn in survivors:
        outcomes[cid] = ledger.invoke_candidate(cid, fn, inp, phase=phase)
    partitions = {_key(out) for out in outcomes.values()}
    return len(partitions) <= 1, outcomes


def _consistent_with_evidence(
    cid: str,
    fn: Callable[[Any], Any],
    ledger,
    support_examples: list,
    oracle_log: list[dict[str, Any]],
    phase: str,
) -> bool:
    for inp, expected in support_examples:
        if ledger.invoke_candidate(cid, fn, inp, phase=phase) != expected:
            return False
    for row in oracle_log:
        actual = ledger.invoke_candidate(cid, fn, row["probe_input"], phase=phase)
        if actual != row["oracle_answer"]:
            return False
    return True


def construct_probe_candidates(task, used_inputs: set[str]) -> list[Any]:
    """Build unused distinguishing inputs from support values and boundary templates.

    Assessment rows are never used. Templates that collide with already-used
    support or probe inputs are skipped.
    """
    values: list[int] = []
    for inp, _expected in getattr(task, "support_examples", []):
        if isinstance(inp, list):
            values.extend(int(v) for v in inp if type(v) is int)
    if not values:
        values = [0, 1, -1, 2]
    uniq = list(dict.fromkeys(values))
    templates = [
        [uniq[0], uniq[0]],
        [0],
        [-1, 0, 1],
        [-3, 0, 2, 2, 5],
        [-4, -1, 0, 3, 3],
        [uniq[-1], 0, uniq[0], uniq[0], -abs(uniq[-1] or 1)],
        [v * 2 for v in uniq[:4]] + [0],
        uniq + uniq[:1],
        [x - 1 for x in uniq[:5]],
        [7, -7, 0, 7],
    ]
    out: list[Any] = []
    seen = set(used_inputs)
    for item in templates:
        token = _key(item)
        if token in seen:
            continue
        seen.add(token)
        out.append(item)
    return out


def apply_completeness_preserving_fallback(
    *,
    task,
    ranked: list[Candidate],
    survivors: list[Candidate],
    used_probe_indices: set[int],
    ledger,
    active_env,
    ctrl_cfg,
    started: float,
) -> dict[str, Any]:
    """Widen after shortlist agreement; never claim certainty on truncated evidence.

    Returns an updated survivor list plus an auditable widening record. When
    widening is disabled the record labels the historical shortlist stop.
    """
    record: dict[str, Any] = {
        "enabled": bool(ctrl_cfg.enable_widening),
        "shortlist_agreement": False,
        "observational_equivalence_on_identified_evidence": False,
        "stopping_reason": "legacy_shortlist_stop",
        "expansions": [],
        "candidates_checked": [],
        "constructed_probes": [],
        "unresolved_alternatives": [],
        "certainty_claimed": True,
        "oracle_unavailable": False,
        "identified_evidence_count": len(task.support_examples) + ledger.n_questions,
    }
    if not ctrl_cfg.enable_widening:
        if survivors:
            record["candidates_checked"] = [cid for cid, _ops, _fn in survivors]
        elif ranked:
            record["candidates_checked"] = [ranked[0][0]]
            record["stopping_reason"] = "legacy_empty_shortlist_fallback"
        return {"survivors": survivors, "record": record}

    checked_ids: set[str] = {cid for cid, _ops, _fn in survivors}
    record["candidates_checked"] = list(checked_ids)
    used_inputs = {_key(inp) for inp, _expected in task.support_examples}
    used_inputs.update(_key(row["probe_input"]) for row in ledger.oracle_question_log)
    for idx in used_probe_indices:
        if 0 <= idx < len(task.probe_pool_inputs):
            used_inputs.add(_key(task.probe_pool_inputs[idx]))

    def remaining_ranked() -> list[Candidate]:
        return [item for item in ranked if item[0] not in checked_ids]

    def shortlist_splits_on_remaining_probes() -> bool:
        if len(survivors) <= 1:
            return False
        for p_idx, probe_inp in enumerate(task.probe_pool_inputs):
            if p_idx in used_probe_indices or _key(probe_inp) in used_inputs:
                continue
            if _budget_exhausted(ledger, ctrl_cfg, started):
                return False
            agree, _outcomes = _agree_on_input(survivors, ledger, probe_inp, "probe_construction")
            if not agree:
                return True
        return False

    if survivors and not shortlist_splits_on_remaining_probes() and (
        len(survivors) > 1 or remaining_ranked()
    ):
        record["shortlist_agreement"] = True

    constructed_used = 0

    def try_question(probe_inp: Any, source: str) -> str | None:
        nonlocal survivors
        if not ctrl_cfg.allow_questions:
            return "questions_disabled"
        if ledger.n_questions >= ctrl_cfg.max_questions_per_task:
            return "question_budget"
        if _budget_exhausted(ledger, ctrl_cfg, started):
            return "budget_exhausted"
        try:
            answer = ledger.invoke_oracle(active_env, task.task_id, probe_inp)
        except KeyError:
            record["oracle_unavailable"] = True
            return "no_answer_source"
        used_inputs.add(_key(probe_inp))
        survivors = [
            (cid, ops, fn)
            for cid, ops, fn in survivors
            if ledger.invoke_candidate(cid, fn, probe_inp, phase="probe_filter") == answer
        ]
        record["expansions"].append({
            "kind": "oracle",
            "source": source,
            "probe": probe_inp,
            "answer": answer,
            "survivors_after": [cid for cid, _ops, _fn in survivors],
        })
        return None

    def distinguish() -> str | None:
        nonlocal constructed_used
        if len(survivors) <= 1:
            return None
        for p_idx, probe_inp in enumerate(task.probe_pool_inputs):
            if p_idx in used_probe_indices or _key(probe_inp) in used_inputs:
                continue
            if _budget_exhausted(ledger, ctrl_cfg, started):
                return "budget_exhausted"
            agree, _outcomes = _agree_on_input(survivors, ledger, probe_inp, "probe_construction")
            used_probe_indices.add(p_idx)
            if agree:
                continue
            reason = try_question(probe_inp, "unused_pool")
            if reason:
                return reason
            return None
        if constructed_used >= ctrl_cfg.max_constructed_probes:
            return None
        for probe_inp in construct_probe_candidates(task, used_inputs):
            if constructed_used >= ctrl_cfg.max_constructed_probes:
                break
            if _budget_exhausted(ledger, ctrl_cfg, started):
                return "budget_exhausted"
            agree, _outcomes = _agree_on_input(survivors, ledger, probe_inp, "constructed_probe")
            constructed_used += 1
            record["constructed_probes"].append({"input": probe_inp, "agreed": agree})
            used_inputs.add(_key(probe_inp))
            if agree:
                continue
            reason = try_question(probe_inp, "constructed")
            if reason:
                return reason
            return None
        return None

    halt: str | None = None
    while True:
        if _budget_exhausted(ledger, ctrl_cfg, started):
            halt = "budget_exhausted"
            break
        if len(checked_ids) >= ctrl_cfg.max_candidates_checked and remaining_ranked():
            halt = "budget_exhausted"
            break

        batch = remaining_ranked()[: max(1, ctrl_cfg.widen_batch_size)]
        if batch:
            added: list[str] = []
            rejected: list[str] = []
            for cid, ops, fn in batch:
                if _budget_exhausted(ledger, ctrl_cfg, started):
                    halt = "budget_exhausted"
                    break
                if len(checked_ids) >= ctrl_cfg.max_candidates_checked:
                    halt = "budget_exhausted"
                    break
                ok = _consistent_with_evidence(
                    cid, fn, ledger, task.support_examples, ledger.oracle_question_log,
                    phase="widening_support",
                )
                checked_ids.add(cid)
                record["candidates_checked"].append(cid)
                if ok:
                    survivors.append((cid, ops, fn))
                    added.append(cid)
                else:
                    rejected.append(cid)
            record["expansions"].append({
                "kind": "shortlist_expansion",
                "added": added,
                "rejected": rejected,
                "survivors_after": [cid for cid, _ops, _fn in survivors],
            })
            if halt:
                break

        halt = distinguish()
        if halt:
            break
        if len(survivors) <= 1 and not remaining_ranked():
            break
        if not remaining_ranked() and (len(survivors) <= 1 or constructed_used >= ctrl_cfg.max_constructed_probes):
            break
        if not batch and halt is None and constructed_used >= ctrl_cfg.max_constructed_probes:
            break
        if not batch and len(survivors) <= 1:
            break
        if not batch and ledger.n_questions >= ctrl_cfg.max_questions_per_task:
            break

    unique_checked = list(dict.fromkeys(record["candidates_checked"]))
    record["candidates_checked"] = unique_checked
    record["identified_evidence_count"] = len(task.support_examples) + ledger.n_questions

    if record["oracle_unavailable"] or halt == "no_answer_source":
        record["stopping_reason"] = "no_answer_source"
        record["certainty_claimed"] = False
    elif halt == "budget_exhausted" or (
        remaining_ranked() and len(checked_ids) >= ctrl_cfg.max_candidates_checked
    ):
        record["stopping_reason"] = "budget_exhausted"
        record["certainty_claimed"] = False
    elif not survivors:
        record["stopping_reason"] = "unresolved_out_of_grammar"
        record["certainty_claimed"] = False
    elif len(survivors) == 1 and not remaining_ranked():
        record["stopping_reason"] = "identified"
        record["certainty_claimed"] = True
    elif len(survivors) > 1:
        equivalent = True
        identified = [inp for inp, _expected in task.support_examples]
        identified.extend(row["probe_input"] for row in ledger.oracle_question_log)
        for inp in identified:
            agree, _outcomes = _agree_on_input(survivors, ledger, inp, "equivalence_check")
            if not agree:
                equivalent = False
                break
        record["observational_equivalence_on_identified_evidence"] = equivalent
        record["stopping_reason"] = "unresolved_equivalent" if equivalent else "unresolved"
        record["certainty_claimed"] = False
        record["unresolved_alternatives"] = [cid for cid, _ops, _fn in survivors]
    else:
        record["stopping_reason"] = "unresolved"
        record["certainty_claimed"] = False

    if not record["certainty_claimed"]:
        record["unresolved_alternatives"] = record["unresolved_alternatives"] or [
            cid for cid, _ops, _fn in survivors
        ]
    return {"survivors": survivors, "record": record}
