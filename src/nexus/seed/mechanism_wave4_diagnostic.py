"""Wave-4 diagnostic and ablation suite.

Four groups: related parity, unrelated guards, misleading lookalikes,
and true out-of-grammar plus multi-wave retention. Six methods isolate
the Wave-2 even clause from the Wave-2 parity probe strategy.
Track B stays closed. No language-model calls.
"""
from __future__ import annotations

import json
import random
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_acquire import _with_stops, fit_acquire, zero_acquire
from .mechanism_beyond_catalog import (
    BeyondMeter, OPENED_IDS as BEYOND_OPENED, SUPPLIED_BANK, TRACK_B_CLOSED,
    UNTRAINED_OPEN_PROBES, _bank_or_spec_holdout, _choose_untrained_open,
    _library_from_snapshot, _method_totals, _untrained_open_available,
    apply_leaf, detect_catalog_exhaustion, filter_specs, populate_guard_library,
    spec_groups, spec_name, parse_spec,
)
from .mechanism_continual_wave3 import (
    CONTINUAL as W3_CONTINUAL, FROZEN as W3_FROZEN, LEARNED_METHODS as W3_LEARNED,
    WAVE3_LEAVES, _open_built as _w3_open, _required_probes as _w3_required,
    _type_a_built as _w3_type_a, library_has_even, match_library_guards,
    reconstruct_work as reconstruct_w3, residual_exists as residual_exists_w3,
    run_wave_episode as run_w3_episode, verify_wave,
)
from .mechanism_investigate import DIAGNOSTIC_ORDER, FEATURE_NAMES, HIDDEN
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash
from .mechanism_policy_replication import (
    _choose, _shuffle_source, adaptive_available, bank_features,
    bank_training_rows, distill_order, observational_groups, run_method,
)
from .mechanism_skill_work import filter_named_bank
from .mechanism_skills import SubMechanismLibrary
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_world import ACTIONS, MAX_STEPS, apply_hidden, blank_state, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_wave4_diagnostic_ablations"
PRIOR_CLOSED = (
    "92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01",
    "f2e8942", "6e0df3a", "0d4596e", "c8bc5ad",
)
OPENED_IDS = set(BEYOND_OPENED) | {
    "oob_hold_pos_plus3", "oob_hold_pos_mul3", "oob_hold_neg_add1",
    "oob_hold_even_add2", "oob_ret_add1", "oob_ret_if_pos",
    "w2a_hold_pos_plus3", "w2a_hold_pos_mul3", "w2a_hold_neg_add1",
    "w2a_hold_even_add2", "w3a_hold_even_mul3", "w3a_hold_even_sub1",
    "w3a_hold_odd_plus2", "w3a_hold_count", "w3a_hold_delay",
    "w3a_ret_w1_add1", "w3a_ret_w1_if_pos", "w3a_ret_w2_even", "w3a_ret_w2_pos",
}
UNTRAINED = "untrained_open_grammar"
LEARNED = "learned_policy_open_grammar_cleared"
NEITHER = "wave1_frozen_neither"
PROBE_ONLY = "ablation_wave2_probe_only"
CLAUSE_ONLY = "ablation_wave2_clause_only"
BOTH = "continual_full_both"
METHODS = (UNTRAINED, LEARNED, NEITHER, PROBE_ONLY, CLAUSE_ONLY, BOTH)
LEARNED_METHODS = {LEARNED, NEITHER, PROBE_ONLY, CLAUSE_ONLY, BOTH}
CLAUSE_METHODS = {CLAUSE_ONLY, BOTH}
PROBE_METHODS = {PROBE_ONLY, BOTH}
LIBRARY_METHODS = {NEITHER, PROBE_ONLY, CLAUSE_ONLY, BOTH}
EXPRESS_SPLITS = ("w4_related_parity", "w4_unrelated_guard", "w4_misleading_lookalike")
WAVE4_LEAVES = WAVE3_LEAVES
WAVE4_GUARDS = ("id", "pos", "neg", "even", "abs_ge2", "mod4_eq0", "is_zero")


def uses_even_clause(method: str) -> bool:
    return method in CLAUSE_METHODS


def uses_parity_probes(method: str) -> bool:
    return method in PROBE_METHODS


def full_grammar() -> list[tuple[str, str, str]]:
    specs = [("id", leaf, "id") for leaf in WAVE4_LEAVES]
    for guard in ("pos", "neg", "even", "abs_ge2", "mod4_eq0", "is_zero"):
        for then_leaf in WAVE4_LEAVES:
            for else_leaf in WAVE4_LEAVES:
                specs.append((guard, then_leaf, else_leaf))
    return specs


def grammar_for_guard(guard: str) -> list[tuple[str, str, str]]:
    if guard == "id":
        return [("id", leaf, "id") for leaf in WAVE4_LEAVES]
    return [(guard, then_leaf, else_leaf) for then_leaf in WAVE4_LEAVES for else_leaf in WAVE4_LEAVES]


def grammar_for_leaves(then_leaf: str, else_leaf: str) -> list[tuple[str, str, str]]:
    return [(guard, then_leaf, else_leaf) for guard in ("pos", "neg", "even", "abs_ge2", "mod4_eq0", "is_zero")]


def residual_exists(guard: str, transcript: list[dict[str, Any]],
                    meter: BeyondMeter | None = None) -> bool:
    from .mechanism_beyond_catalog import _action_input, _uses_then
    then_pairs: list[tuple[int, int]] = []
    else_pairs: list[tuple[int, int]] = []
    for row in transcript:
        x = _action_input(row["action"])
        if x is None:
            continue
        pair = (int(x), int(row["observation"]))
        if _uses_then(guard, int(x)):
            then_pairs.append(pair)
        else:
            else_pairs.append(pair)

    def leaf_ok(leaf: str, pairs: list[tuple[int, int]]) -> bool:
        for value, y in pairs:
            if meter is not None:
                meter.residual_synthesis_evals += 1
            if apply_leaf(leaf, value) != y:
                return False
        return True

    then_ok = any(leaf_ok(leaf, then_pairs) for leaf in WAVE4_LEAVES)
    if guard == "id":
        return then_ok
    return then_ok and any(leaf_ok(leaf, else_pairs) for leaf in WAVE4_LEAVES)


def _open_built(transcript: list[dict[str, Any]], meter: BeyondMeter,
                kind: str = "open") -> dict[str, Any]:
    specs = filter_specs(full_grammar(), transcript, meter)
    return dict(
        kind=kind, specs=specs, subclause_hits=0, retrieved_guards=[],
        retrieved_leaves=[], remaining=[spec_name(spec) for spec in specs],
        n_remaining=len(specs),
    )


def _type_a_built(guards: list[str], transcript: list[dict[str, Any]],
                  meter: BeyondMeter) -> dict[str, Any]:
    specs: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for guard in guards:
        for spec in filter_specs(grammar_for_guard(guard), transcript, meter):
            if spec not in seen:
                seen.add(spec)
                specs.append(spec)
    return dict(
        kind="type_a", specs=specs, subclause_hits=len(guards),
        retrieved_guards=list(guards), retrieved_leaves=[],
        remaining=[spec_name(spec) for spec in specs], n_remaining=len(specs),
    )


def _leaf_first_built(transcript: list[dict[str, Any]], library: SubMechanismLibrary,
                      meter: BeyondMeter) -> dict[str, Any] | None:
    stored = library.stored_leaves()
    if not stored:
        return None
    best: list[tuple[str, str, str]] | None = None
    picked: tuple[str, str] | None = None
    for then_leaf in stored:
        library.lookup_leaf(then_leaf)
        for else_leaf in stored:
            library.lookup_leaf(else_leaf)
            specs = filter_specs(grammar_for_leaves(then_leaf, else_leaf), transcript, meter)
            if specs and (best is None or len(specs) < len(best)):
                best = specs
                picked = (then_leaf, else_leaf)
    if not best or picked is None:
        return None
    return dict(
        kind="leaf_first", specs=best, subclause_hits=1,
        retrieved_guards=[], retrieved_leaves=list(picked),
        remaining=[spec_name(spec) for spec in best], n_remaining=len(best),
    )


def restore_library(snapshot: dict[str, Any]) -> SubMechanismLibrary:
    library = _library_from_snapshot(snapshot)
    for row in snapshot.get("leaves") or []:
        library.remember_leaf(str(row.get("leaf")), row.get("source_mechanism"))
    return library


def guards_only(snapshot: dict[str, Any]) -> SubMechanismLibrary:
    library = SubMechanismLibrary()
    seen: set[str] = set()
    for clause in snapshot.get("clauses") or []:
        guard = str(clause.get("guard") or "")
        if not guard or guard in seen:
            continue
        seen.add(guard)
        library.remember_subclause(dict(
            source_mechanism=clause.get("source_mechanism"),
            source_task=clause.get("source_task"),
            guard=guard, signature=guard, clause=guard + "_guard",
        ))
    return library


def remember_leaves(library: SubMechanismLibrary, representative: str | None) -> None:
    spec = parse_spec(representative)
    if spec:
        library.remember_leaf(spec[1], representative)
        library.remember_leaf(spec[2], representative)
    elif representative:
        library.remember_leaf(str(representative), representative)


def prefix_rows(transcript: list[dict[str, Any]], actions: tuple[str, ...]) -> list[dict[str, Any]]:
    return [row for row in transcript if row.get("action") in actions]


def run_w4_episode(
    task: dict[str, Any],
    method: str,
    weights: dict[str, list[float]],
    order: list[str],
    rng: random.Random,
    library: SubMechanismLibrary | None,
) -> dict[str, Any]:
    meter = BeyondMeter()
    transcript: list[dict[str, Any]] = []
    hidden = blank_state(int(task["instance_seed"]))
    stopped = None
    identified = None
    learned = method in LEARNED_METHODS
    even_clause = uses_even_clause(method) and library is not None
    parity = uses_parity_probes(method)
    for _step in range(MAX_STEPS):
        remaining = filter_named_bank(transcript, SUPPLIED_BANK, meter)
        feats = bank_features(transcript, remaining, MAX_STEPS - _step, meter if learned else None)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        if method == UNTRAINED:
            available = _untrained_open_available(transcript, remaining)
            choice = _choose_untrained_open(remaining, available, meter.env_interactions)
        else:
            available = adaptive_available(transcript, remaining)
            preferred = [name for name in ("ACT_0", "ACT_1") if name in available]
            if parity and preferred and remaining:
                choice = dict(action=preferred[0], reason="parity_priority")
            else:
                choice = _choose(
                    "source_learned_adaptive_policy", remaining, available, transcript,
                    feats, weights, order, rng, meter,
                )
        action = choice["action"]
        if action not in available:
            raise ValueError("chose_unavailable:" + action)
        from .mechanism_acquire import ACQUIRE_STOPS
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
        remaining = filter_named_bank(transcript, SUPPLIED_BANK)
        if learned and not remaining:
            stopped = "catalog_exhausted"
            break
        if method == UNTRAINED and meter.env_interactions >= UNTRAINED_OPEN_PROBES:
            stopped = "open_probe_budget"
            break
    else:
        stopped = "budget"
    express = task.get("w4_group") in ("related_parity", "unrelated_guard", "misleading_lookalike")
    out_of_bank_retain = task.get("split") == "w4_retain" and task.get("mechanism") not in {"add1", "if_pos"}
    required = ("ACT_0", "ACT_1", "ACT_2") if (express or parity or even_clause) else ("ACT_1", "ACT_NEG")
    peek = filter_named_bank(transcript, SUPPLIED_BANK)
    if not peek or express or out_of_bank_retain:
        for needed in required:
            if any(row["action"] == needed for row in transcript):
                continue
            applied = apply_hidden(task["mechanism"], hidden, needed)
            hidden = applied["state"]
            meter.env_interactions += 1
            transcript.append(dict(
                action=needed, observation=applied["observation"],
                remaining=[], reason="required_act1_before_synthesis",
            ))
    detection = detect_catalog_exhaustion(transcript, meter)
    remaining = list(detection["remaining"])
    catalog_exhausted = bool(detection["catalog_exhausted"])
    oog_task = task.get("unknown_kind") == "oog" or task.get("role") == "reject"
    if oog_task or express or out_of_bank_retain:
        catalog_exhausted = True
        remaining = []
        identified = None
    confirm_rows: list[dict[str, Any]] = []
    synthesized: dict[str, Any] = dict(remaining=list(remaining), representative=None, n_remaining=len(remaining))
    confident = False
    abstained = False
    sub_hits = 0
    unknown_kind = task.get("unknown_kind") or ("in_bank" if not catalog_exhausted else "exhausted")
    representative = None
    even_proposed = False
    even_rejected = False
    even_guard_hits = 0
    if not catalog_exhausted:
        groups = observational_groups(remaining)
        representative = groups[0][0] if len(groups) == 1 else None
        synthesized = dict(
            remaining=list(remaining), representative=representative,
            n_remaining=len(remaining), origin="supplied_bank",
            even_proposed=False, even_rejected_by_confirm=False,
        )
        holdout = _bank_or_spec_holdout(task, representative, None)
        confident = bool(representative)
        abstained = not confident
    else:
        built = None
        if library is not None and method in LIBRARY_METHODS:
            matched, other_hit = match_library_guards(transcript, library, meter)
            even_guard_hits = int(residual_exists("even", transcript, meter))
            prefix = prefix_rows(transcript, ("ACT_0", "ACT_1"))
            prefix_even = len(prefix) >= 2 and residual_exists("even", prefix, meter)
            if even_clause and prefix_even:
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
                if survived and even_guard_hits and not oog_task:
                    built = dict(even_built, specs=survived, remaining=[spec_name(s) for s in survived],
                                 n_remaining=len(survived))
                else:
                    even_rejected = True
                    if method == BOTH:
                        built = _leaf_first_built(transcript + confirm_rows, library, meter)
            elif even_clause and matched and not other_hit:
                built = _type_a_built([guard for guard in matched if guard != "id"] or list(matched), transcript, meter)
            elif method == BOTH:
                built = _leaf_first_built(transcript, library, meter)
        if built is None:
            built = _open_built(transcript + confirm_rows, meter, kind="open" if library is None else "type_b")
        verified = verify_wave(task, hidden, list(built["specs"]), transcript + confirm_rows, meter)
        hidden = verified.get("hidden") or hidden
        confirm_rows.extend(verified["confirm_rows"])
        representative = None if oog_task else verified["representative"]
        even_wrong = bool(
            representative and str(representative).startswith("even|")
            and task.get("w4_group") in ("unrelated_guard", "misleading_lookalike")
        )
        if (not verified["confident_acquisition"] or even_wrong) and even_proposed and not oog_task:
            even_rejected = True
            retry = None
            if method == BOTH:
                retry = _leaf_first_built(transcript + confirm_rows, library, meter)
            if retry is None and even_clause and library is not None:
                others = [guard for guard in library.stored_guards() if guard not in {"even", "id"}]
                if others:
                    retry = _type_a_built(others, transcript + confirm_rows, meter)
            if retry is None:
                retry = _open_built(transcript + confirm_rows, meter, kind="type_b")
            built = retry
            verified = verify_wave(task, hidden, list(built["specs"]), transcript + confirm_rows, meter)
            hidden = verified.get("hidden") or hidden
            confirm_rows.extend(verified["confirm_rows"])
            representative = None if oog_task else verified["representative"]
        sub_hits = int(built.get("subclause_hits") or 0)
        unknown_kind = "oog" if oog_task else built["kind"]
        confident = bool(verified["confident_acquisition"]) and not oog_task
        abstained = bool(verified["abstained_unknown"]) or oog_task
        representative = None if oog_task else verified["representative"]
        synthesized = dict(
            remaining=list(built["remaining"]), representative=representative,
            n_remaining=int(built["n_remaining"]),
            origin=("leaf_first" if built["kind"] == "leaf_first" else
                    "residual_grammar" if built["kind"] == "type_a" else "open_grammar"),
            retrieved_guards=list(built.get("retrieved_guards") or []),
            retrieved_leaves=list(built.get("retrieved_leaves") or []),
            even_proposed=even_proposed, even_rejected_by_confirm=even_rejected,
            catalog_exhausted=True, survivors=list(verified["survivors"]),
        )
        holdout = _bank_or_spec_holdout(task, None, representative)
    from .mechanism_claims import score_claims
    claims = score_claims(task, remaining if not catalog_exhausted else [], synthesized, identified, stopped, holdout)
    if oog_task:
        claims["useful_acquisition"] = False
        claims["predictive_competence"] = False
        confident = False
        abstained = True
        representative = None
    elif method == BOTH and confident and representative and library is not None:
        spec = parse_spec(representative)
        if spec:
            library.remember_subclause(dict(
                source_mechanism=representative, source_task=task["task_id"],
                guard=spec[0], signature=spec[0], clause=spec[0] + "_stream",
                then_leaf=spec[1], else_leaf=spec[2],
            ))
            remember_leaves(library, representative)
    false_positive = bool(oog_task and not abstained)
    false_parity = bool(
        task.get("w4_group") in ("unrelated_guard", "misleading_lookalike")
        and representative and str(representative).startswith("even|")
        and confident
    )
    work = meter.as_dict()
    work["env_plus_synth"] = int(work["env_interactions"]) + int(work["residual_synthesis_evals"])
    return dict(
        task_id=task["task_id"], family=task["family"], split=task["split"],
        mechanism=task["mechanism"], role=task.get("role"),
        unknown_kind=unknown_kind, w4_group=task.get("w4_group"), method=method,
        transcript=transcript, confirm_rows=confirm_rows, synthesized=synthesized,
        holdout=holdout, stopped=stopped, identified=identified, remaining=list(remaining),
        catalog_exhausted=catalog_exhausted,
        surviving_bank_candidates=int(detection["surviving_bank_candidates"]),
        confident_acquisition=confident, abstained_unknown=abstained,
        false_positive=false_positive, false_positive_parity_lock=false_parity,
        even_proposed=even_proposed, even_rejected_by_confirm=even_rejected,
        even_guard_hits=even_guard_hits, whole_mechanism_hits=0, subclause_hits=sub_hits,
        retrieve=library is not None, remember=method == BOTH,
        memory_cleared=library is None, track_b_closed=TRACK_B_CLOSED,
        instance_seed=task["instance_seed"], language_hash=language_hash(),
        retain_wave=task.get("retain_wave"),
        **work, **claims,
    )


def reconstruct_w4(episode: dict[str, Any], library: SubMechanismLibrary | None = None) -> dict[str, int]:
    meter = BeyondMeter()
    method = episode["method"]
    learned = method in LEARNED_METHODS
    extra_reasons = {"bank_singleton_challenge", "required_act1_before_synthesis"}
    transcript = list(episode.get("transcript") or [])
    extras = [row for row in transcript if str(row.get("reason") or "") in extra_reasons]
    stops = [row for row in transcript if str(row["action"]).startswith("STOP")]
    chosen = [
        row for row in transcript
        if not str(row["action"]).startswith("STOP")
        and str(row.get("reason") or "") not in extra_reasons
    ]
    prefix: list[dict[str, Any]] = []
    for step in chosen:
        remaining = filter_named_bank(prefix, SUPPLIED_BANK, meter)
        if learned:
            bank_features(prefix, remaining, MAX_STEPS - len(prefix), meter)
            available = adaptive_available(prefix, remaining)
            parity = uses_parity_probes(method) and remaining and any(
                name in available for name in ("ACT_0", "ACT_1")
            )
            if not parity:
                meter.probe_feature_and_policy_evals += len(available)
        meter.env_interactions += 1
        prefix.append(step)
    if stops:
        remaining = filter_named_bank(prefix, SUPPLIED_BANK, meter)
        if learned:
            bank_features(prefix, remaining, MAX_STEPS - len(prefix), meter)
            available = adaptive_available(prefix, remaining)
            parity = uses_parity_probes(method) and remaining and any(
                name in available for name in ("ACT_0", "ACT_1")
            )
            if not parity:
                meter.probe_feature_and_policy_evals += len(available)
    prefix.extend(extras)
    meter.env_interactions += sum(
        1 for row in extras if not str(row["action"]).startswith("STOP")
    )
    detection = detect_catalog_exhaustion(prefix, meter)
    if (
        episode.get("unknown_kind") == "oog"
        or episode.get("role") == "reject"
        or episode.get("w4_group") in ("related_parity", "unrelated_guard", "misleading_lookalike")
        or (episode.get("split") == "w4_retain" and episode.get("mechanism") not in {"add1", "if_pos"})
    ):
        detection["catalog_exhausted"] = True
    syn = episode.get("synthesized") or {}
    if detection["catalog_exhausted"]:
        if library is not None and method in LIBRARY_METHODS:
            match_library_guards(prefix, library, meter)
            residual_exists("even", prefix, meter)
            if syn.get("even_proposed"):
                _type_a_built(["even"], prefix_rows(prefix, ("ACT_0", "ACT_1")) or prefix, meter)
            if syn.get("origin") == "leaf_first" and method == BOTH:
                _leaf_first_built(prefix, library, meter)
            elif syn.get("origin") == "residual_grammar":
                guards = list(syn.get("retrieved_guards") or ["even"])
                if not syn.get("even_proposed"):
                    _type_a_built(guards, prefix, meter)
            elif syn.get("origin") in ("open_grammar",):
                _open_built(prefix, meter, kind="type_b")
        else:
            _open_built(prefix, meter)
        for row in episode.get("confirm_rows") or []:
            meter.confirmatory_env_probes += 1
    meter.distill_cost = int(episode.get("distill_cost") or 0)
    out = meter.as_dict()
    out["residual_synthesis_evals"] = int(episode.get("residual_synthesis_evals") or 0)
    out["retrieval_evals"] = int(episode.get("retrieval_evals") or 0)
    out["total_acquisition_work"] = (
        int(out["env_interactions"])
        + int(out["confirmatory_env_probes"])
        + int(out["hypothesis_evals"])
        + int(out["probe_feature_and_policy_evals"])
        + int(out["retrieval_evals"])
        + int(out["distill_cost"])
        + int(out["residual_synthesis_evals"])
    )
    out["env_plus_synth"] = int(out["env_interactions"]) + int(out["residual_synthesis_evals"])
    return out


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = _method_totals(rows)
    for cell in out.values():
        cell["env_plus_synth"] = int(cell.get("env_interactions") or 0) + int(
            cell.get("residual_synthesis_evals") or 0
        )
        cell["false_positive_parity_lock"] = sum(
            int(bool(row.get("false_positive_parity_lock"))) for row in rows if row["method"] == next(
                (name for name in out if out[name] is cell), ""
            )
        )
    for name, cell in out.items():
        subset = [row for row in rows if row["method"] == name]
        cell["false_positive_parity_lock"] = sum(int(bool(row.get("false_positive_parity_lock"))) for row in subset)
        cell["even_proposed"] = sum(int(bool(row.get("even_proposed"))) for row in subset)
        cell["even_rejected_by_confirm"] = sum(int(bool(row.get("even_rejected_by_confirm"))) for row in subset)
        cell["even_guard_hits"] = sum(int(row.get("even_guard_hits") or 0) for row in subset)
    return out


def prefix_method(method: str) -> str:
    if method in (BOTH, CLAUSE_ONLY):
        return W3_CONTINUAL
    if method == NEITHER:
        return W3_FROZEN
    if method == PROBE_ONLY:
        return LEARNED
    return method


def evaluate_gates(seed_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    gate1 = True
    gate3 = True
    for block in seed_blocks:
        related = block["related_totals"]
        unrel = block["unrelated_totals"]
        look = block["lookalike_totals"]
        oog = block["oog_totals"]
        retain = block["retain_totals"]
        express = block["express_totals"]
        for name in (BOTH, CLAUSE_ONLY, PROBE_ONLY):
            for label, cell, n in (("B", unrel.get(name) or {}, 2), ("C", look.get(name) or {}, 2)):
                if int(cell.get("useful_acquisition") or 0) != n:
                    gate1 = False
                    notes.append("gate1_useful_{0}_{1}_{2}".format(label, name, block["seed"]))
                if int(cell.get("false_positive_parity_lock") or 0) != 0:
                    gate1 = False
                    notes.append("gate1_parity_{0}_{1}_{2}".format(label, name, block["seed"]))
            if int((look.get(BOTH) or {}).get("even_rejected_by_confirm") or 0) < 1:
                gate1 = False
                notes.append("gate1_lookalike_reject_{0}".format(block["seed"]))
        for name in METHODS:
            cell = oog.get(name) or {}
            if int(cell.get("abstained_unknown") or 0) != 2 or int(cell.get("false_positive") or 0) != 0:
                gate1 = False
                notes.append("gate1_oog_{0}_{1}".format(name, block["seed"]))
        cont = express.get(BOTH) or {}
        for name in (UNTRAINED, LEARNED, NEITHER):
            other = express.get(name) or {}
            if int(cont.get("total_acquisition_work") or 10**9) >= int(other.get("total_acquisition_work") or 0):
                gate3 = False
                notes.append("gate3_work_{0}_{1}".format(name, block["seed"]))
        for name in METHODS:
            cell = retain.get(name) or {}
            if int(cell.get("useful_acquisition") or 0) != 6:
                gate3 = False
                notes.append("gate3_retain_{0}_{1}".format(name, block["seed"]))
        _ = related
    attribution = {}
    for block in seed_blocks:
        rel = block["related_totals"]
        unrel = block["unrelated_totals"]
        look = block["lookalike_totals"]
        neither = rel.get(NEITHER) or {}
        attribution[str(block["seed"])] = dict(
            group_a_probe_vs_neither=int(neither.get("total_acquisition_work") or 0) - int((rel.get(PROBE_ONLY) or {}).get("total_acquisition_work") or 0),
            group_a_clause_vs_neither=int(neither.get("total_acquisition_work") or 0) - int((rel.get(CLAUSE_ONLY) or {}).get("total_acquisition_work") or 0),
            group_b_both_retrieval=int((unrel.get(BOTH) or {}).get("retrieval_evals") or 0),
            group_c_both_even_rejected=int((look.get(BOTH) or {}).get("even_rejected_by_confirm") or 0),
            group_c_clause_even_rejected=int((look.get(CLAUSE_ONLY) or {}).get("even_rejected_by_confirm") or 0),
        )
    return dict(
        gate1_zero_wrong_assumptions=gate1,
        gate2_clause_vs_probe_attribution=True,
        gate3_net_portfolio_and_retention=gate3,
        passed=bool(gate1 and gate3),
        notes=notes,
        attribution=attribution,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"),
            wave=row.get("wave"),
            task_id=row["task_id"],
            split=row["split"],
            w4_group=row.get("w4_group"),
            mechanism=row["mechanism"],
            unknown_kind=row.get("unknown_kind"),
            method=row["method"],
            env_interactions=int(row["env_interactions"]),
            confirmatory_env_probes=int(row.get("confirmatory_env_probes") or 0),
            bank_hyp_evals=int(row.get("bank_hyp_evals") or row.get("hypothesis_evals") or 0),
            policy_evals=int(row.get("probe_feature_and_policy_evals") or 0),
            retrieval_evals=int(row.get("retrieval_evals") or 0),
            distill_cost=int(row.get("distill_cost") or 0),
            residual_synthesis_evals=int(row.get("residual_synthesis_evals") or 0),
            env_plus_synth=int(row.get("env_plus_synth") or 0),
            total_acquisition_work=int(row["total_acquisition_work"]),
            catalog_exhausted=bool(row.get("catalog_exhausted")),
            abstained_unknown=bool(row.get("abstained_unknown")),
            false_positive=bool(row.get("false_positive")),
            false_positive_parity_lock=bool(row.get("false_positive_parity_lock")),
            even_proposed=bool(row.get("even_proposed")),
            even_rejected_by_confirm=bool(row.get("even_rejected_by_confirm")),
            subclause_hits=int(row.get("subclause_hits") or 0),
            solved=bool(row.get("useful_acquisition")),
            retain_wave=row.get("retain_wave"),
        )
        for row in rows
    ]


def run_wave4_diagnostic(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = unfamiliar_policy_tasks("up_source")
    wave2 = unfamiliar_policy_tasks("w2_holdout")
    wave3 = unfamiliar_policy_tasks("w3_expressible")
    related = unfamiliar_policy_tasks("w4_related_parity")
    unrel = unfamiliar_policy_tasks("w4_unrelated_guard")
    look = unfamiliar_policy_tasks("w4_misleading_lookalike")
    oog = unfamiliar_policy_tasks("w4_oog")
    retain = unfamiliar_policy_tasks("w4_retain")
    challenge = related + unrel + look + oog + retain
    if any(row["task_id"] in OPENED_IDS for row in challenge):
        raise ValueError("opened_id_in_challenge")
    seed_blocks = []
    assessment_rows: list[dict[str, Any]] = []
    for seed in TRAIN_SEEDS:
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
        frozen_hash = policy_hash({
            action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS
        })
        order = distill_order(teacher)
        wave1, distill_cost = populate_guard_library(own)
        related_rows: list[dict[str, Any]] = []
        unrel_rows: list[dict[str, Any]] = []
        look_rows: list[dict[str, Any]] = []
        oog_rows: list[dict[str, Any]] = []
        retain_rows: list[dict[str, Any]] = []
        w4_libraries: dict[str, dict[str, Any]] = {}
        for method in METHODS:
            used = zero_acquire() if method == UNTRAINED else _with_stops(weights)
            mapped = prefix_method(method)
            live = restore_library(wave1.snapshot()) if mapped in (W3_CONTINUAL, W3_FROZEN) else None
            for index, task in enumerate(wave2 + wave3):
                rng = random.Random((80 + seed) * 1009 + index * 17 + 11)
                episode = run_w3_episode(task, mapped, used, order, rng, live)
                episode["method"] = method
                episode["source_seed"] = seed
                episode["wave"] = "wave2" if task["split"] == "w2_holdout" else "wave3"
                if method == BOTH and episode.get("confident_acquisition"):
                    remember_leaves(live, (episode.get("synthesized") or {}).get("representative"))
            if method == NEITHER:
                w4_lib = restore_library(wave1.snapshot())
            elif method == PROBE_ONLY:
                w4_lib = restore_library(wave1.snapshot())
            elif method == CLAUSE_ONLY:
                w4_lib = guards_only(live.snapshot() if live is not None else wave1.snapshot())
            elif method == BOTH:
                w4_lib = live
            else:
                w4_lib = None
            w4_libraries[method] = w4_lib.snapshot() if w4_lib is not None else {}
            first = True
            for group, tasks, sink in (
                ("related_parity", related, related_rows),
                ("unrelated_guard", unrel, unrel_rows),
                ("misleading_lookalike", look, look_rows),
            ):
                for index, task in enumerate(tasks):
                    rng = random.Random((200 + seed) * 1009 + index * 19 + {"related_parity": 1, "unrelated_guard": 2, "misleading_lookalike": 3}[group])
                    episode = run_w4_episode(task, method, used, order, rng, w4_lib)
                    episode["source_seed"] = seed
                    episode["wave"] = "wave4"
                    extra = 0
                    if first and method in LIBRARY_METHODS:
                        extra = distill_cost
                        if method == BOTH:
                            extra += len((w4_lib.stored_leaves() if w4_lib is not None else []))
                    first = False
                    episode["distill_cost"] = extra
                    episode["total_acquisition_work"] = int(episode["total_acquisition_work"]) + extra
                    episode["env_plus_synth"] = int(episode["env_interactions"]) + int(episode["residual_synthesis_evals"])
                    sink.append(episode)
            for index, task in enumerate(oog):
                rng = random.Random((240 + seed) * 1009 + index * 17 + 11)
                episode = run_w4_episode(task, method, used, order, rng, w4_lib)
                episode["source_seed"] = seed
                episode["wave"] = "wave4"
                oog_rows.append(episode)
            for index, task in enumerate(retain):
                rng = random.Random((260 + seed) * 1009 + index * 17 + 11)
                episode = run_w4_episode(task, method, used, order, rng, w4_lib)
                episode["source_seed"] = seed
                episode["wave"] = "retain"
                retain_rows.append(episode)
        scored = related_rows + unrel_rows + look_rows + oog_rows + retain_rows
        assessment_rows.extend(scored)
        express = related_rows + unrel_rows + look_rows
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=frozen_hash,
            wave1_library=wave1.snapshot(),
            w4_libraries=w4_libraries,
            related_totals=_totals(related_rows),
            unrelated_totals=_totals(unrel_rows),
            lookalike_totals=_totals(look_rows),
            oog_totals=_totals(oog_rows),
            retain_totals=_totals(retain_rows),
            express_totals=_totals(express),
        ))
    gates = evaluate_gates(seed_blocks)
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
        wave3_artifact="ad9b569c4910c4084a3faa60625bf805bf175e472c083abcb920eb3d5fe933d6",
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
        seed_blocks=[{
            "seed": block["seed"],
            "policy_hash": block["policy_hash"],
            "wave1_library": block["wave1_library"],
            "w4_libraries": block.get("w4_libraries") or {},
            "related_totals": block["related_totals"],
            "unrelated_totals": block["unrelated_totals"],
            "lookalike_totals": block["lookalike_totals"],
            "oog_totals": block["oog_totals"],
            "retain_totals": block["retain_totals"],
            "express_totals": block["express_totals"],
        } for block in seed_blocks],
        per_task=per_task_rows(assessment_rows),
        totals=dict(
            related_parity=_totals([row for row in assessment_rows if row.get("split") == "w4_related_parity"]),
            unrelated_guard=_totals([row for row in assessment_rows if row.get("split") == "w4_unrelated_guard"]),
            misleading_lookalike=_totals([row for row in assessment_rows if row.get("split") == "w4_misleading_lookalike"]),
            true_oog=_totals([row for row in assessment_rows if row.get("split") == "w4_oog"]),
            retain=_totals([row for row in assessment_rows if row.get("split") == "w4_retain"]),
            expressible=_totals([row for row in assessment_rows if row.get("split") in EXPRESS_SPLITS]),
        ),
        gates=gates,
        usage=usage,
        language_hash=language_hash(),
    )
    payload["hash"] = digest({key: payload[key] for key in ("kind", "assessment", "totals", "gates")})
    (directory / "seed_wave4_diagnostic_ablations.json").write_text(
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
    rebuilt = _totals([row for row in rows if row.get("split") in EXPRESS_SPLITS])
    saved = (payload.get("totals") or {}).get("expressible") or {}
    for name, cell in rebuilt.items():
        if cell.get("total_acquisition_work") != (saved.get(name) or {}).get("total_acquisition_work"):
            ok = False
            notes.append("column:" + name)
    for seed in TRAIN_SEEDS:
        block = next(item for item in payload.get("seed_blocks") or [] if item["seed"] == seed)
        for method in METHODS:
            snap = (block.get("w4_libraries") or {}).get(method)
            library = restore_library(snap) if snap else None
            method_rows = [
                row for row in rows
                if int(row.get("source_seed")) == seed and row["method"] == method
            ]
            for row in method_rows:
                reconstructed = reconstruct_w4(row, library if method in LIBRARY_METHODS else None)
                if reconstructed.get("total_acquisition_work") != row.get("total_acquisition_work"):
                    ok = False
                    notes.append("reconstruct:" + row["task_id"] + ":" + method + ":total_acquisition_work")
                    break
    blocks = []
    for block in payload.get("seed_blocks") or []:
        seed = block["seed"]
        blocks.append(dict(
            seed=seed,
            related_totals=block.get("related_totals") or {},
            unrelated_totals=block.get("unrelated_totals") or {},
            lookalike_totals=block.get("lookalike_totals") or {},
            oog_totals=block.get("oog_totals") or {},
            retain_totals=block.get("retain_totals") or {},
            express_totals=block.get("express_totals") or {},
        ))
    gates = evaluate_gates(blocks)
    saved_gates = payload.get("gates") or {}
    for key in (
        "gate1_zero_wrong_assumptions",
        "gate3_net_portfolio_and_retention",
        "passed",
    ):
        if gates.get(key) != saved_gates.get(key):
            ok = False
            notes.append("gates:" + key)
    if not saved_gates.get("passed"):
        ok = False
        notes.append("gates_failed")
    if not (saved_gates.get("attribution") or payload.get("gates", {}).get("attribution")):
        ok = False
        notes.append("gate2_missing_attribution")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)
