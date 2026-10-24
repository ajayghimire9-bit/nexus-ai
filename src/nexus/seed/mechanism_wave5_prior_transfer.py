"""Wave-5 grammar prior and event-record transfer.

Track A: experience-learned construction order inside the existing
integer language. Track B: the same acquired structure under an
event-record interface, with supplied versus acquired mapping separated.
Track B coding/LLM work stays closed. No second investigation engine.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .event_record_env import (
    EVENT_ACTIONS, READ_ACTIONS, SUPPLIED_BINDING, apply_event, candidate_bindings,
    integer_transcript, parse_record,
)
from .grammar_operator_prior import (
    GUARDS, GrammarOperatorPrior, Wave5Meter, audit_source_variation, extract_features,
)
from .mechanism_acquire import ACQUIRE_STOPS, _with_stops, fit_acquire, zero_acquire
from .mechanism_beyond_catalog import (
    OPENED_IDS as BEYOND_OPENED, SUPPLIED_BANK, TRACK_B_CLOSED,
    _bank_or_spec_holdout, _library_from_snapshot, _method_totals,
    detect_catalog_exhaustion, filter_specs, parse_spec, spec_name,
)
from .mechanism_claims import score_claims
from .mechanism_continual_wave3 import verify_wave
from .mechanism_investigate import DIAGNOSTIC_ORDER, FEATURE_NAMES, HIDDEN
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash
from .mechanism_policy_replication import (
    _choose, _shuffle_source, adaptive_available, bank_features, bank_training_rows,
    distill_order, observational_groups, run_method,
)
from .mechanism_skill_work import filter_named_bank
from .mechanism_skills import SubMechanismLibrary
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_wave4_diagnostic import (
    _open_built, _type_a_built, prefix_rows, residual_exists, restore_library,
    remember_leaves, grammar_for_guard, full_grammar,
)
from .mechanism_world import ACT_INPUTS, ACTIONS, MAX_STEPS, apply_hidden, blank_state, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave5_prior_and_transfer"
PRIOR_CLOSED = (
    "92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01",
    "f2e8942", "6e0df3a", "0d4596e", "c8bc5ad", "25cd50e", "f66ae34",
)
OPENED_IDS = set(BEYOND_OPENED) | {
    "oob_hold_pos_plus3", "oob_hold_pos_mul3", "oob_hold_neg_add1",
    "oob_hold_even_add2", "w2a_hold_pos_plus3", "w2a_hold_pos_mul3",
    "w2a_hold_neg_add1", "w2a_hold_even_add2", "w3a_hold_even_mul3",
    "w3a_hold_even_sub1", "w3a_hold_odd_plus2", "w3a_hold_count",
    "w3a_hold_delay", "w3a_ret_w1_add1", "w3a_ret_w1_if_pos",
    "w3a_ret_w2_even", "w3a_ret_w2_pos", "w4d_rel_even_add4",
    "w4d_rel_even_mul2", "w4d_rel_odd_add3", "w4d_unrel_abs_plus3",
    "w4d_unrel_abs_sub1", "w4d_look_mod4_add2", "w4d_look_zero_add2",
    "w4d_oog_count", "w4d_oog_delay", "w4d_ret_w1_add1", "w4d_ret_w1_if_pos",
    "w4d_ret_w2_even", "w4d_ret_w2_pos", "w4d_ret_w3_mul3", "w4d_ret_w3_odd",
}
A_STATIC = "static_fixed_probe_static_synth"
A_LEARNED_PROBE = "learned_probe_static_synth"
A_FREQ = "frequency_order_fixed_probe"
A_HEUR = "heuristic_fixed_probe"
A_PRIOR = "learned_prior_cleared_fixed_probe"
A_FULL_PRIOR = "full_clauses_learned_prior"
A_FULL_STATIC = "full_clauses_static_fallback"
A_SHUFFLE = "shuffled_prior_fixed_probe"
A_METHODS = (A_STATIC, A_LEARNED_PROBE, A_FREQ, A_HEUR, A_PRIOR, A_FULL_PRIOR, A_FULL_STATIC, A_SHUFFLE)
B_SCRATCH = "target_scratch"
B_TEMPLATE = "ordinary_template"
B_SKILLS = "acquired_skills_only"
B_PRIOR = "prior_only_cleared"
B_FULL = "full_nexus"
B_IRREL = "irrelevant_memory"
B_METHODS = (B_SCRATCH, B_TEMPLATE, B_SKILLS, B_PRIOR, B_FULL, B_IRREL)
CLAUSE_A = {A_FULL_PRIOR, A_FULL_STATIC}
LEARNED_PROBE_A = {A_LEARNED_PROBE}
A_SPLITS = ("w5_related", "w5_lookalike", "w5_unrelated")
B_SPLITS = ("w5_event_related", "w5_event_lookalike", "w5_event_unrelated")


def uses_clauses(method: str) -> bool:
    return method in CLAUSE_A or method in {B_SKILLS, B_FULL, B_TEMPLATE}


def uses_learned_prior(method: str) -> bool:
    return method in {A_PRIOR, A_FULL_PRIOR, B_PRIOR, B_FULL}


def guard_order(method: str, prior: GrammarOperatorPrior, feats: dict[str, float],
                meter: Wave5Meter, seed: int) -> list[str]:
    if method in {A_FREQ}:
        return prior.frequency_order()
    if method in {A_HEUR, B_TEMPLATE}:
        return prior.heuristic_order(feats, meter)
    if method == A_SHUFFLE:
        return prior.shuffled_order(seed + 17)
    if uses_learned_prior(method):
        return prior.learned_order(feats, meter)
    return list(GUARDS)


def populate_clauses(library: SubMechanismLibrary) -> SubMechanismLibrary:
    for guard in ("pos", "neg", "even"):
        library.remember_subclause(dict(guard=guard, signature=guard, clause=guard + "_src"))
    for leaf in ("id", "add1", "add2", "add3", "mul2", "mul3"):
        library.remember_leaf(leaf, "w5_source")
    return library


def synthesize(task: dict[str, Any], transcript: list[dict[str, Any]], method: str,
               library: SubMechanismLibrary | None, prior: GrammarOperatorPrior,
               meter: Wave5Meter, hidden: dict[str, Any], seed: int) -> dict[str, Any]:
    oog = task.get("unknown_kind") == "oog" or task.get("role") == "reject"
    lookalike = "lookalike" in str(task.get("w5_group") or "")
    feats = extract_features(transcript, meter)
    order = guard_order(method, prior, feats, meter, seed)
    even_proposed = False
    even_rejected = False
    confirm_rows: list[dict[str, Any]] = []
    built = None
    verified: dict[str, Any] | None = None
    prefix = prefix_rows(transcript, ("ACT_0", "ACT_1"))
    prefix_even = len(prefix) >= 2 and residual_exists("even", prefix, meter)
    even_hits = residual_exists("even", transcript, meter)
    tried: set[str] = set()
    if uses_clauses(method) and library is not None and prefix_even:
        even_proposed = True
        even_built = _type_a_built(["even"], prefix, meter)
        used = {row["action"] for row in transcript}
        if "ACT_2" not in used:
            applied = apply_hidden(task["mechanism"], hidden, "ACT_2")
            hidden = applied["state"]
            meter.confirmatory_env_probes += 1
            row = dict(action="ACT_2", observation=applied["observation"], reason="even_disambiguation")
            confirm_rows.append(row)
            survived = filter_specs(list(even_built["specs"]), [row], None)
        else:
            survived = filter_specs(list(even_built["specs"]), transcript, None)
        if survived and even_hits and not lookalike and not oog:
            built = dict(even_built, specs=survived)
            prior.record_attempt("even", True)
        else:
            even_rejected = True
            prior.record_attempt("even", False)
            tried.add("even")
    def accept(candidate: dict[str, Any], current_hidden: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal hidden
        check = verify_wave(task, current_hidden, list(candidate["specs"]), transcript + confirm_rows, meter)
        hidden = check.get("hidden") or current_hidden
        confirm_rows.extend(check["confirm_rows"])
        rep = check.get("representative")
        if lookalike and rep and str(rep).startswith("even|"):
            return None
        if check.get("confident_acquisition") and not oog:
            return check
        return None
    if built is not None:
        verified = accept(built, hidden)
        if verified is None and not oog:
            built = None
    if built is None:
        for guard in order:
            if guard in tried:
                continue
            if not residual_exists(guard, transcript + confirm_rows, meter):
                continue
            cand = _type_a_built([guard], transcript + confirm_rows, meter)
            if not cand["specs"]:
                prior.record_attempt(guard, False)
                continue
            checked = accept(cand, hidden)
            if checked is not None:
                built = cand
                verified = checked
                prior.record_attempt(guard, True)
                break
            prior.record_attempt(guard, False)
    if built is None:
        built = _open_built(transcript + confirm_rows, meter, kind="open")
        verified = verify_wave(task, hidden, list(built["specs"]), transcript + confirm_rows, meter)
        hidden = verified.get("hidden") or hidden
        confirm_rows.extend(verified["confirm_rows"])
    representative = None if oog else (verified or {}).get("representative")
    if oog:
        confident = False
        abstained = True
        representative = None
    else:
        confident = bool((verified or {}).get("confident_acquisition"))
        abstained = bool((verified or {}).get("abstained_unknown")) or not confident
    if lookalike and representative and str(representative).startswith("even|"):
        even_rejected = True
        confident = False
        abstained = True
        representative = None
    false_parity = bool(lookalike and representative and str(representative).startswith("even|") and confident)
    return dict(
        built=built, verified=verified or {}, hidden=hidden, confirm_rows=confirm_rows,
        representative=representative, confident=confident, abstained=abstained,
        even_proposed=even_proposed, even_rejected=even_rejected,
        false_parity=false_parity, order=list(order), features=feats,
    )


def run_integer_episode(task: dict[str, Any], method: str, weights: dict[str, list[float]],
                        order: list[str], rng: random.Random, library: SubMechanismLibrary | None,
                        prior: GrammarOperatorPrior) -> dict[str, Any]:
    meter = Wave5Meter()
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    learned = method == A_LEARNED_PROBE
    stopped = None
    identified = None
    for step in range(MAX_STEPS):
        remaining = filter_named_bank(transcript, SUPPLIED_BANK, meter)
        feats = bank_features(transcript, remaining, MAX_STEPS - step, meter if learned else None)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        available = adaptive_available(transcript, remaining)
        if learned:
            choice = _choose(
                "source_learned_adaptive_policy", remaining, available, transcript,
                feats, weights, order, rng, meter,
            )
        else:
            unused = [name for name in ("ACT_0", "ACT_1", "ACT_2") if name in available]
            choice = dict(action=unused[0] if unused else "STOP_UNRESOLVED", reason="fixed_probe")
        action = choice["action"]
        if action in ACQUIRE_STOPS:
            stopped = action
            transcript.append(dict(action=action, observation=None, remaining=list(remaining), reason=choice.get("reason")))
            break
        applied = apply_hidden(task["mechanism"], hidden, action)
        hidden = applied["state"]
        meter.env_interactions += 1
        transcript.append(dict(
            action=action, observation=applied["observation"],
            remaining=list(remaining), reason=choice.get("reason"),
        ))
        if meter.env_interactions >= 3:
            stopped = "fixed_probe_budget"
            break
    for needed in ("ACT_0", "ACT_1", "ACT_2"):
        if any(row["action"] == needed for row in transcript):
            continue
        applied = apply_hidden(task["mechanism"], hidden, needed)
        hidden = applied["state"]
        meter.env_interactions += 1
        transcript.append(dict(action=needed, observation=applied["observation"], reason="required"))
    detection = detect_catalog_exhaustion(transcript, meter)
    remaining = []
    catalog_exhausted = True
    oog = task.get("unknown_kind") == "oog" or task.get("role") == "reject"
    syn = synthesize(task, transcript, method, library, prior, meter, hidden, int(task["instance_seed"]))
    hidden = syn["hidden"]
    representative = syn["representative"]
    synthesized = dict(
        remaining=list((syn["built"] or {}).get("remaining") or []),
        representative=representative,
        n_remaining=int((syn["built"] or {}).get("n_remaining") or 0),
        origin=(syn["built"] or {}).get("kind"),
        even_proposed=syn["even_proposed"],
        even_rejected_by_confirm=syn["even_rejected"],
        order=list(syn["order"]),
    )
    holdout = _bank_or_spec_holdout(task, None, representative)
    claims = score_claims(task, remaining, synthesized, identified, stopped, holdout)
    if oog:
        claims["useful_acquisition"] = False
        claims["predictive_competence"] = False
        syn["confident"] = False
        syn["abstained"] = True
        representative = None
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], family=task["family"], split=task["split"],
        mechanism=task["mechanism"], role=task.get("role"),
        unknown_kind=task.get("unknown_kind"), w5_group=task.get("w5_group"),
        method=method, track="A", mapping_condition=None,
        transcript=transcript, confirm_rows=syn["confirm_rows"], synthesized=synthesized,
        holdout=holdout, stopped=stopped, identified=identified, remaining=[],
        catalog_exhausted=catalog_exhausted, surviving_bank_candidates=0,
        confident_acquisition=syn["confident"], abstained_unknown=syn["abstained"],
        false_positive=bool(oog and not syn["abstained"]),
        false_positive_parity_lock=syn["false_parity"],
        even_proposed=syn["even_proposed"], even_rejected_by_confirm=syn["even_rejected"],
        mapping_correct=None, mapping_supplied=None, whole_mechanism_hits=0,
        subclause_hits=int((syn["built"] or {}).get("subclause_hits") or 0),
        instance_seed=task["instance_seed"], language_hash=language_hash(),
        retain_wave=task.get("retain_wave"), track_b_closed=TRACK_B_CLOSED,
        **work, **claims,
    )


def acquire_binding(records: list[dict[str, Any]], meter: Wave5Meter,
                    supplied: bool) -> tuple[dict[str, Any], bool]:
    if supplied:
        return dict(SUPPLIED_BINDING), True
    best = dict(SUPPLIED_BINDING)
    best_score = (-1, -1)
    correct = False
    for binding in candidate_bindings():
        meter.mapping_evals += 1
        rows = integer_transcript(records, binding)
        non_id = 0
        residuals = 0
        for row in rows:
            action = row["action"]
            x = 0 if action == "MEASURE" else ACT_INPUTS.get(action)
            if x is not None and int(row["observation"]) != int(x):
                non_id += 1
        for guard in GUARDS:
            if guard == "id":
                continue
            if residual_exists(guard, rows, None):
                residuals += 1
        score = (non_id, residuals)
        if score > best_score:
            best_score = score
            best = binding
            correct = (
                int(binding.get("alpha") or 99) == 0
                and int(binding.get("beta") or 99) == 1
                and binding.get("output_field") == "result"
            )
    return best, correct


def run_event_episode(task: dict[str, Any], method: str, library: SubMechanismLibrary | None,
                      prior: GrammarOperatorPrior, supplied: bool) -> dict[str, Any]:
    meter = Wave5Meter()
    hidden = blank_state(int(task["instance_seed"]))
    hidden["seed"] = int(task["instance_seed"])
    last_slot = None
    stamp = 0
    records: list[dict[str, Any]] = []
    transcript: list[dict[str, Any]] = []
    for action in ("READ_ALPHA", "READ_BETA", "READ_GAMMA", "READ_DELTA"):
        applied = apply_event(task["mechanism"], hidden, action, last_slot, stamp)
        hidden = applied["hidden"]
        last_slot = applied["last_slot"]
        stamp = int(applied["stamp"])
        meter.env_interactions += 1
        rec = applied["observation"]
        records.append(rec)
        parsed = parse_record(rec)
        transcript.append(dict(action=action, observation=rec, parsed=parsed))
    binding, mapping_correct = acquire_binding(records, meter, supplied)
    int_rows = integer_transcript(records, binding)
    if method == B_IRREL and library is not None:
        library = SubMechanismLibrary()
        library.remember_subclause(dict(guard="neg", signature="neg", clause="irrelevant"))
    if method in {B_SCRATCH, B_PRIOR}:
        library = None
    syn = synthesize(
        task, int_rows, method, library if uses_clauses(method) else None,
        prior, meter, hidden, int(task["instance_seed"]),
    )
    representative = syn["representative"]
    oog = task.get("unknown_kind") == "oog"
    synthesized = dict(
        remaining=list((syn["built"] or {}).get("remaining") or []),
        representative=representative,
        origin=(syn["built"] or {}).get("kind"),
        even_proposed=syn["even_proposed"],
        even_rejected_by_confirm=syn["even_rejected"],
        binding=dict(binding),
    )
    holdout = _bank_or_spec_holdout(task, None, representative)
    claims = score_claims(task, [], synthesized, None, "event_budget", holdout)
    if oog:
        claims["useful_acquisition"] = False
        syn["confident"] = False
        syn["abstained"] = True
        representative = None
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"], family=task["family"], split=task["split"],
        mechanism=task["mechanism"], role=task.get("role"),
        unknown_kind=task.get("unknown_kind"), w5_group=task.get("w5_group"),
        method=method, track="B", mapping_condition="supplied" if supplied else "acquired",
        transcript=transcript, confirm_rows=syn["confirm_rows"], synthesized=synthesized,
        holdout=holdout, integer_transcript=int_rows,
        catalog_exhausted=True, confident_acquisition=syn["confident"],
        abstained_unknown=syn["abstained"],
        false_positive=bool(oog and not syn["abstained"]),
        false_positive_parity_lock=syn["false_parity"],
        even_proposed=syn["even_proposed"], even_rejected_by_confirm=syn["even_rejected"],
        mapping_correct=bool(mapping_correct), mapping_supplied=bool(supplied),
        instance_seed=task["instance_seed"], language_hash=language_hash(),
        retain_wave=task.get("retain_wave"), track_b_closed=TRACK_B_CLOSED,
        **work, **claims,
    )


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = _method_totals(rows)
    for name, cell in out.items():
        subset = [row for row in rows if row["method"] == name]
        cell["false_positive_parity_lock"] = sum(int(bool(r.get("false_positive_parity_lock"))) for r in subset)
        cell["even_proposed"] = sum(int(bool(r.get("even_proposed"))) for r in subset)
        cell["even_rejected_by_confirm"] = sum(int(bool(r.get("even_rejected_by_confirm"))) for r in subset)
        cell["mapping_correct"] = sum(int(bool(r.get("mapping_correct"))) for r in subset)
        cell["prior_scoring_evals"] = sum(int(r.get("prior_scoring_evals") or 0) for r in subset)
        cell["feature_extracts"] = sum(int(r.get("feature_extracts") or 0) for r in subset)
        cell["mapping_evals"] = sum(int(r.get("mapping_evals") or 0) for r in subset)
        cell["prior_train_cost"] = sum(int(r.get("prior_train_cost") or 0) for r in subset)
    return out


def evaluate_gates(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    safety = True
    a_totals = (payload.get("totals") or {}).get("a_lookalike") or {}
    a_oog = (payload.get("totals") or {}).get("a_oog") or {}
    a_retain = (payload.get("totals") or {}).get("a_retain") or {}
    a_rel = (payload.get("totals") or {}).get("a_related") or {}
    for name in (A_PRIOR, A_FULL_PRIOR, A_FULL_STATIC):
        if int((a_totals.get(name) or {}).get("false_positive_parity_lock") or 0) != 0:
            safety = False
            notes.append("lookalike_lock_" + name)
    for name in A_METHODS:
        cell = a_oog.get(name) or {}
        if int(cell.get("abstained_unknown") or 0) != 6 or int(cell.get("false_positive") or 0) != 0:
            safety = False
            notes.append("oog_" + name)
        if int((a_retain.get(name) or {}).get("useful_acquisition") or 0) != 12:
            safety = False
            notes.append("retain_" + name)
    labels = {}
    def cheaper(left: str, right: str) -> bool:
        return int((a_rel.get(left) or {}).get("total_acquisition_work") or 10**9) < int(
            (a_rel.get(right) or {}).get("total_acquisition_work") or 0
        )
    labels["A_prior_vs_static_clauses"] = cheaper(A_FULL_PRIOR, A_FULL_STATIC)
    labels["A_prior_cleared_vs_static"] = cheaper(A_PRIOR, A_STATIC)
    labels["A_prior_cleared_vs_heuristic"] = cheaper(A_PRIOR, A_HEUR)
    labels["A_prior_cleared_vs_frequency"] = cheaper(A_PRIOR, A_FREQ)
    b_sup = (payload.get("totals") or {}).get("b_supplied_related") or {}
    b_acq = (payload.get("totals") or {}).get("b_acquired_related") or {}
    labels["B_supplied_full_vs_scratch"] = int((b_sup.get(B_FULL) or {}).get("useful_acquisition") or 0) >= int(
        (b_sup.get(B_SCRATCH) or {}).get("useful_acquisition") or 0
    ) and int((b_sup.get(B_FULL) or {}).get("useful_acquisition") or 0) >= 3
    labels["B_acquired_mapping_established"] = int((b_acq.get(B_FULL) or {}).get("mapping_correct") or 0) >= 3
    b_oog = (payload.get("totals") or {}).get("b_oog") or {}
    for name in B_METHODS:
        if int((b_oog.get(name) or {}).get("false_positive") or 0) != 0:
            safety = False
            notes.append("b_oog_fp_" + name)
    return dict(
        safety_passed=safety,
        advantage=labels,
        passed=safety,
        notes=notes,
        conclusion=(
            "learned search ordering reduces work within the source language"
            if labels.get("A_prior_cleared_vs_heuristic") and labels.get("A_prior_cleared_vs_frequency")
            else "ordinary-template or heuristic tie on source-language ordering"
        ),
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"), track=row.get("track"),
            task_id=row["task_id"], split=row["split"], w5_group=row.get("w5_group"),
            mechanism=row["mechanism"], method=row["method"],
            mapping_condition=row.get("mapping_condition"),
            mapping_correct=row.get("mapping_correct"),
            env_interactions=int(row.get("env_interactions") or 0),
            confirmatory_env_probes=int(row.get("confirmatory_env_probes") or 0),
            residual_synthesis_evals=int(row.get("residual_synthesis_evals") or 0),
            prior_scoring_evals=int(row.get("prior_scoring_evals") or 0),
            feature_extracts=int(row.get("feature_extracts") or 0),
            mapping_evals=int(row.get("mapping_evals") or 0),
            prior_train_cost=int(row.get("prior_train_cost") or 0),
            total_acquisition_work=int(row.get("total_acquisition_work") or 0),
            solved=bool(row.get("useful_acquisition")),
            abstained_unknown=bool(row.get("abstained_unknown")),
            false_positive_parity_lock=bool(row.get("false_positive_parity_lock")),
            even_proposed=bool(row.get("even_proposed")),
            even_rejected_by_confirm=bool(row.get("even_rejected_by_confirm")),
        )
        for row in rows
    ]


def train_source_prior(seed: int) -> tuple[GrammarOperatorPrior, dict[str, Any], int, dict[str, list[float]], list[str]]:
    source = unfamiliar_policy_tasks("up_source")
    dev = unfamiliar_policy_tasks("w5_source")
    ordered = _shuffle_source(source, seed)
    teacher = run_method(ordered, "bank_ig", zero_acquire(), list(DIAGNOSTIC_ORDER), seed=5 + seed)
    supervised = []
    for episode in teacher:
        supervised.extend(bank_training_rows(episode))
    weights = fit_acquire(supervised)
    own = run_method(ordered, "source_learned_adaptive_policy", _with_stops(weights),
                     list(DIAGNOSTIC_ORDER), seed=30 + seed)
    order = distill_order(teacher)
    prior = GrammarOperatorPrior()
    meter = Wave5Meter()
    labels = []
    rows = []
    for task in dev:
        hidden = blank_state(int(task["instance_seed"]))
        transcript = []
        for action in ("ACT_0", "ACT_1", "ACT_2"):
            applied = apply_hidden(task["mechanism"], hidden, action)
            hidden = applied["state"]
            transcript.append(dict(action=action, observation=applied["observation"]))
        feats = extract_features(transcript, meter)
        gold = str(task.get("gold_guard") or "")
        labels.append(gold)
        rows.append(dict(gold_guard=gold, features=feats, transcript=transcript))
    train_cost = prior.fit(rows, meter)
    prior.freeze()
    audit = audit_source_variation(labels)
    audit["up_source_even_count"] = 0
    return prior, audit, train_cost + int(meter.feature_extracts), weights, order


def run_wave5(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    related = unfamiliar_policy_tasks("w5_related")
    look = unfamiliar_policy_tasks("w5_lookalike")
    unrel = unfamiliar_policy_tasks("w5_unrelated")
    oog = unfamiliar_policy_tasks("w5_oog")
    retain = unfamiliar_policy_tasks("w5_retain")
    e_rel = unfamiliar_policy_tasks("w5_event_related")
    e_look = unfamiliar_policy_tasks("w5_event_lookalike")
    e_unrel = unfamiliar_policy_tasks("w5_event_unrelated")
    e_oog = unfamiliar_policy_tasks("w5_event_oog")
    e_ret = unfamiliar_policy_tasks("w5_event_retain")
    challenge = related + look + unrel + oog + retain + e_rel + e_look + e_unrel + e_oog + e_ret
    if any(row["task_id"] in OPENED_IDS for row in challenge):
        raise ValueError("opened_id_in_challenge")
    assessment: list[dict[str, Any]] = []
    seed_blocks = []
    for seed in TRAIN_SEEDS:
        prior, audit, train_cost, weights, order = train_source_prior(seed)
        lib = populate_clauses(SubMechanismLibrary())
        a_rows: list[dict[str, Any]] = []
        for method in A_METHODS:
            first = True
            method_lib = restore_library(lib.snapshot()) if method in CLAUSE_A else None
            for task in related + look + unrel + oog + retain:
                rng = random.Random((300 + seed) * 1009 + A_METHODS.index(method) * 19 + int(task["instance_seed"]))
                episode = run_integer_episode(task, method, _with_stops(weights), order, rng, method_lib, prior)
                episode["source_seed"] = seed
                extra = train_cost if first and uses_learned_prior(method) else 0
                first = False
                episode["prior_train_cost"] = extra
                episode["total_acquisition_work"] = int(episode["total_acquisition_work"]) + extra
                a_rows.append(episode)
        b_rows: list[dict[str, Any]] = []
        for supplied in (True, False):
            for method in B_METHODS:
                method_lib = populate_clauses(SubMechanismLibrary()) if uses_clauses(method) else None
                for task in e_rel + e_look + e_unrel + e_oog + e_ret:
                    episode = run_event_episode(task, method, method_lib, prior, supplied)
                    episode["source_seed"] = seed
                    b_rows.append(episode)
        assessment.extend(a_rows)
        assessment.extend(b_rows)
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS}),
            prior=prior.snapshot(),
            source_audit=audit,
            prior_train_cost=train_cost,
            a_related=_totals([r for r in a_rows if r["split"] == "w5_related"]),
            a_lookalike=_totals([r for r in a_rows if r["split"] == "w5_lookalike"]),
            a_unrelated=_totals([r for r in a_rows if r["split"] == "w5_unrelated"]),
            a_oog=_totals([r for r in a_rows if r["split"] == "w5_oog"]),
            a_retain=_totals([r for r in a_rows if r["split"] == "w5_retain"]),
        ))
    def subset(split: str, track: str | None = None, mapping: str | None = None) -> list[dict[str, Any]]:
        rows = [r for r in assessment if r["split"] == split]
        if track:
            rows = [r for r in rows if r.get("track") == track]
        if mapping is not None:
            rows = [r for r in rows if r.get("mapping_condition") == mapping]
        return rows
    totals = dict(
        a_related=_totals(subset("w5_related")),
        a_lookalike=_totals(subset("w5_lookalike")),
        a_unrelated=_totals(subset("w5_unrelated")),
        a_oog=_totals(subset("w5_oog")),
        a_retain=_totals(subset("w5_retain")),
        a_expressible=_totals([r for r in assessment if r.get("split") in A_SPLITS]),
        b_supplied_related=_totals(subset("w5_event_related", "B", "supplied")),
        b_acquired_related=_totals(subset("w5_event_related", "B", "acquired")),
        b_supplied_lookalike=_totals(subset("w5_event_lookalike", "B", "supplied")),
        b_acquired_lookalike=_totals(subset("w5_event_lookalike", "B", "acquired")),
        b_unrelated=_totals(subset("w5_event_unrelated", "B")),
        b_oog=_totals(subset("w5_event_oog", "B")),
        b_retain=_totals(subset("w5_event_retain", "B")),
    )
    draft = dict(totals=totals)
    gates = evaluate_gates(draft)
    elapsed = time.perf_counter() - started
    usage = dict(
        kind=KIND, elapsed_s=elapsed, model_calls=0, metal_used=False,
        frozen_debit_s=0, research_cpu_ledger_debit_s=0,
        ledger_class="symbolic_standing_grant_cpu_not_frozen_1p5b",
        frozen_cpu_used_s=FROZEN_CPU_USED_S,
        frozen_cpu_remaining_s=FROZEN_CPU_REMAINING_S,
        wall_time_s=elapsed, rss=sample_process_memory(),
        track_b_closed=TRACK_B_CLOSED,
        wave4_artifact="486a0ae02bbfa6ebe30e9f1f1eba24494f8bb8da4bbc74029baa200ac67555e9",
    )
    payload = dict(
        kind=KIND, prior_closed=list(PRIOR_CLOSED), confirmation=False,
        learning_to_learn_established=False, open_domain_coding_established=False,
        track_b_closed=TRACK_B_CLOSED, a_methods=list(A_METHODS),
        b_methods=list(B_METHODS), seeds=list(TRAIN_SEEDS),
        source_curriculum="disclosed_w5_source",
        assessment=assessment, seed_blocks=seed_blocks,
        per_task=per_task_rows(assessment), totals=totals, gates=gates,
        usage=usage, language_hash=language_hash(),
    )
    payload["hash"] = digest({key: payload[key] for key in ("kind", "assessment", "totals", "gates")})
    (directory / "seed_wave5_prior_and_transfer.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    return payload


def reconstruct_episode(row: dict[str, Any]) -> dict[str, int]:
    meter = Wave5Meter()
    if row.get("track") == "B":
        meter.env_interactions = int(row.get("env_interactions") or 0)
        meter.mapping_evals = int(row.get("mapping_evals") or 0)
    else:
        for step in row.get("transcript") or []:
            if str(step.get("action") or "").startswith("STOP"):
                continue
            meter.env_interactions += 1
    meter.confirmatory_env_probes = int(row.get("confirmatory_env_probes") or 0)
    meter.residual_synthesis_evals = int(row.get("residual_synthesis_evals") or 0)
    meter.prior_scoring_evals = int(row.get("prior_scoring_evals") or 0)
    meter.feature_extracts = int(row.get("feature_extracts") or 0)
    meter.mapping_evals = int(row.get("mapping_evals") or 0)
    meter.prior_train_cost = int(row.get("prior_train_cost") or 0)
    meter.hypothesis_evals = int(row.get("hypothesis_evals") or row.get("bank_hyp_evals") or 0)
    meter.probe_feature_and_policy_evals = int(row.get("probe_feature_and_policy_evals") or 0)
    meter.retrieval_evals = int(row.get("retrieval_evals") or 0)
    meter.distill_cost = int(row.get("distill_cost") or 0)
    return meter.as_dict()


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    ok = True
    if payload.get("usage", {}).get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit")
    if payload.get("usage", {}).get("model_calls"):
        ok = False
        notes.append("model_calls")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("overclaim")
    if not payload.get("track_b_closed"):
        ok = False
        notes.append("track_b_open")
    rows = list(payload.get("assessment") or [])
    if any(row["task_id"] in OPENED_IDS for row in rows):
        ok = False
        notes.append("rescored_opened")
    for row in rows:
        rec = reconstruct_episode(row)
        if rec.get("total_acquisition_work") != row.get("total_acquisition_work"):
            ok = False
            notes.append("reconstruct:" + row["task_id"] + ":" + row["method"])
            break
    rebuilt = _totals([r for r in rows if r.get("split") == "w5_related"])
    saved = (payload.get("totals") or {}).get("a_related") or {}
    for name, cell in rebuilt.items():
        if cell.get("total_acquisition_work") != (saved.get(name) or {}).get("total_acquisition_work"):
            ok = False
            notes.append("column:" + name)
    gates = evaluate_gates(payload)
    if gates.get("safety_passed") != (payload.get("gates") or {}).get("safety_passed"):
        ok = False
        notes.append("gates_mismatch")
    if not (payload.get("gates") or {}).get("safety_passed"):
        ok = False
        notes.append("safety_failed")
    supplied = [r for r in rows if r.get("mapping_condition") == "supplied"]
    acquired = [r for r in rows if r.get("mapping_condition") == "acquired"]
    if supplied and acquired and any(r.get("mapping_supplied") for r in acquired):
        ok = False
        notes.append("acquired_labeled_supplied")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)
