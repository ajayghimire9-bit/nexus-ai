"""Open acquisition when the hidden mechanism is absent from the bank.

Frozen f2e8942 / 6e0df3a policy. Out-of-bank holdouts have 0% coverage
in supplied_bank. Track B stays closed. Opened prior IDs are not rescored.
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
from .mechanism_compose import HOLDOUT_PROBES
from .mechanism_investigate import DIAGNOSTIC_ORDER, FEATURE_NAMES, HIDDEN, QUERY_ACTIONS
from .mechanism_l2l import TRAIN_SEEDS
from .mechanism_policy import policy_hash
from .mechanism_policy_replication import (
    HYPOTHESIS_BANK, OPENED_IDS as PRIOR_OPENED, TRACK_B_CLOSED, WorkMeter,
    _choose, _shuffle_source, adaptive_available, apply_candidate, bank_features,
    bank_training_rows, distill_order, observational_groups, run_method,
    static_available,
)
from .mechanism_skill_work import NEG_SIGNATURE, POS_SIGNATURE, filter_named_bank
from .mechanism_skills import SubMechanismLibrary
from .mechanism_tasks import unfamiliar_policy_tasks
from .mechanism_world import (
    ACTIONS, ACT_INPUTS, LANGUAGE, MAX_STEPS, apply_hidden, blank_state,
    language_hash,
)
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_unfamiliar_beyond_catalog"
PRIOR_CLOSED = (
    "92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01",
    "f2e8942", "6e0df3a",
)
OPENED_IDS = set(PRIOR_OPENED) | {
    "up_src_add1", "up_src_mul2", "up_src_if_pos", "up_src_sat_inc",
    "up_src_pos_plus", "up_src_twice_pos", "up_src_neg_id", "up_src_neg_dbl",
    "up_hold_pos_plus2", "up_hold_twice_plus1", "up_hold_neg_gate", "up_hold_neg_twice",
    "up_ret_add1", "up_ret_if_pos",
}
SUPPLIED_BANK = HYPOTHESIS_BANK
METHODS = (
    "supplied_bank_only",
    "untrained_open_grammar",
    "learned_policy_open_grammar_cleared",
    "nexus_abductive_beyond_bank",
)
ABDUCTIVE = "nexus_abductive_beyond_bank"
LEARNED_METHODS = {
    "supplied_bank_only",
    "learned_policy_open_grammar_cleared",
    "nexus_abductive_beyond_bank",
}
LEAVES = (
    "id", "add1", "add2", "add3", "add4",
    "mul2", "mul3",
    "const0", "const3", "const4", "const6", "const7", "const8",
)
GUARDS = ("id", "pos", "neg", "even")
MECHANISM_GUARD = {
    "up_src_pos_plus": "pos",
    "up_src_twice_pos": "pos",
    "up_pos_plus2": "pos",
    "up_twice_plus1": "pos",
    "if_pos": "pos",
    "up_src_neg_id": "neg",
    "up_src_neg_dbl": "neg",
    "up_neg_gate": "neg",
    "up_neg_twice": "neg",
}
UNTRAINED_OPEN_PROBES = 5
CONFIRM_ORDER = ("ACT_NEG", "ACT_0", "ACT_2", "ACT_1", "MEASURE")
MAX_CONFIRMATORY = 2


def apply_leaf(leaf: str, x: int) -> int:
    if leaf == "id":
        return int(x)
    if leaf.startswith("add"):
        return int(x) + int(leaf[3:])
    if leaf.startswith("mul"):
        return int(x) * int(leaf[3:])
    if leaf.startswith("const"):
        return int(leaf[5:])
    if leaf == "sub1":
        return int(x) - 1
    raise ValueError("unknown_leaf:" + leaf)


def apply_guarded(guard: str, then_leaf: str, else_leaf: str, x: int) -> int:
    value = int(x)
    if guard == "pos":
        return apply_leaf(then_leaf, value) if value > 0 else apply_leaf(else_leaf, value)
    if guard == "neg":
        return apply_leaf(then_leaf, value) if value < 0 else apply_leaf(else_leaf, value)
    if guard == "even":
        return apply_leaf(then_leaf, value) if value % 2 == 0 else apply_leaf(else_leaf, value)
    return apply_leaf(then_leaf, value)


def spec_name(spec: tuple[str, str, str]) -> str:
    return "|".join(spec)


def parse_spec(name: str | None) -> tuple[str, str, str] | None:
    if not name:
        return None
    parts = str(name).split("|")
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]


def apply_spec(spec: tuple[str, str, str], action: str) -> int | None:
    if action == "RESET" or str(action).startswith("STOP"):
        return None
    x = 0 if action == "MEASURE" else ACT_INPUTS[action]
    return apply_guarded(spec[0], spec[1], spec[2], x)


def full_grammar() -> list[tuple[str, str, str]]:
    specs = [("id", leaf, "id") for leaf in LEAVES]
    for guard in ("pos", "neg", "even"):
        for then_leaf in LEAVES:
            for else_leaf in LEAVES:
                specs.append((guard, then_leaf, else_leaf))
    return specs


def grammar_for_guard(guard: str) -> list[tuple[str, str, str]]:
    if guard == "id":
        return [("id", leaf, "id") for leaf in LEAVES]
    return [(guard, then_leaf, else_leaf) for then_leaf in LEAVES for else_leaf in LEAVES]


class BeyondMeter(WorkMeter):
    def __init__(self) -> None:
        super().__init__()
        self.confirmatory_env_probes = 0
        self.retrieval_evals = 0
        self.distill_cost = 0
        self.residual_synthesis_evals = 0

    def as_dict(self) -> dict[str, int]:
        return dict(
            env_interactions=int(self.env_interactions),
            confirmatory_env_probes=int(self.confirmatory_env_probes),
            bank_hyp_evals=int(self.hypothesis_evals),
            hypothesis_evals=int(self.hypothesis_evals),
            probe_feature_and_policy_evals=int(self.probe_feature_and_policy_evals),
            policy_evals=int(self.probe_feature_and_policy_evals),
            retrieval_evals=int(self.retrieval_evals),
            distill_cost=int(self.distill_cost),
            residual_synthesis_evals=int(self.residual_synthesis_evals),
            total_acquisition_work=int(self.total_acquisition_work),
        )

    @property
    def total_acquisition_work(self) -> int:
        return (
            int(self.env_interactions)
            + int(self.confirmatory_env_probes)
            + int(self.hypothesis_evals)
            + int(self.probe_feature_and_policy_evals)
            + int(self.retrieval_evals)
            + int(self.distill_cost)
            + int(self.residual_synthesis_evals)
        )


def detect_catalog_exhaustion(
    transcript: list[dict[str, Any]],
    meter: BeyondMeter | None = None,
) -> dict[str, Any]:
    remaining = filter_named_bank(transcript, SUPPLIED_BANK, meter)
    exhausted = len(remaining) == 0
    return dict(
        catalog_exhausted=exhausted,
        surviving_bank_candidates=len(remaining),
        remaining=list(remaining),
    )


def filter_specs(
    specs: list[tuple[str, str, str]],
    transcript: list[dict[str, Any]],
    meter: BeyondMeter | None = None,
) -> list[tuple[str, str, str]]:
    kept = []
    for spec in specs:
        ok = True
        for row in transcript:
            action = row["action"]
            if str(action).startswith("STOP") or action == "RESET":
                continue
            predicted = apply_spec(spec, action)
            if meter is not None:
                meter.residual_synthesis_evals += 1
            if predicted is None:
                continue
            if int(row["observation"]) != int(predicted):
                ok = False
                break
        if ok:
            kept.append(spec)
    return kept


def spec_signature(spec: tuple[str, str, str]) -> tuple[tuple[str, int | None], ...]:
    return tuple((action, apply_spec(spec, action)) for action in HOLDOUT_PROBES)


def spec_groups(specs: list[tuple[str, str, str]]) -> list[list[tuple[str, str, str]]]:
    groups: dict[Any, list[tuple[str, str, str]]] = {}
    for spec in specs:
        groups.setdefault(spec_signature(spec), []).append(spec)
    return list(groups.values())


def _action_input(action: str) -> int | None:
    if str(action).startswith("STOP") or action == "RESET":
        return None
    return 0 if action == "MEASURE" else ACT_INPUTS[action]


def _uses_then(guard: str, x: int) -> bool:
    if guard == "pos":
        return x > 0
    if guard == "neg":
        return x < 0
    if guard == "even":
        return x % 2 == 0
    return True


def residual_exists(
    guard: str,
    transcript: list[dict[str, Any]],
    meter: BeyondMeter | None = None,
) -> bool:
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
        for x, y in pairs:
            if meter is not None:
                meter.residual_synthesis_evals += 1
            if apply_leaf(leaf, x) != y:
                return False
        return True

    then_ok = any(leaf_ok(leaf, then_pairs) for leaf in LEAVES)
    if guard == "id":
        return then_ok
    return then_ok and any(leaf_ok(leaf, else_pairs) for leaf in LEAVES)


def synthesize_beyond_bank(
    transcript: list[dict[str, Any]],
    library: SubMechanismLibrary | None,
    meter: BeyondMeter,
) -> dict[str, Any]:
    if library is None:
        specs = filter_specs(full_grammar(), transcript, meter)
        return dict(
            kind="open",
            specs=specs,
            subclause_hits=0,
            retrieved_guards=[],
            remaining=[spec_name(spec) for spec in specs],
            n_remaining=len(specs),
        )
    stored = library.stored_guards()
    matched: list[str] = []
    for guard in stored:
        clauses = library.lookup_guard(guard)
        if clauses and residual_exists(guard, transcript, meter):
            matched.append(guard)
    other_hit = False
    for guard in GUARDS:
        if guard in stored:
            continue
        meter.retrieval_evals += 1
        if residual_exists(guard, transcript, meter):
            other_hit = True
            break
    if matched and not other_hit:
        specs: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for guard in matched:
            for spec in filter_specs(grammar_for_guard(guard), transcript, meter):
                if spec not in seen:
                    seen.add(spec)
                    specs.append(spec)
        return dict(
            kind="type_a",
            specs=specs,
            subclause_hits=len(matched),
            retrieved_guards=matched,
            remaining=[spec_name(spec) for spec in specs],
            n_remaining=len(specs),
        )
    specs = filter_specs(full_grammar(), transcript, meter)
    return dict(
        kind="type_b",
        specs=specs,
        subclause_hits=0,
        retrieved_guards=[],
        remaining=[spec_name(spec) for spec in specs],
        n_remaining=len(specs),
    )


def _unused_confirm_action(transcript: list[dict[str, Any]]) -> str | None:
    used = {
        row["action"] for row in transcript
        if not str(row["action"]).startswith("STOP")
    }
    for action in CONFIRM_ORDER:
        if action not in used:
            return action
    return None


def verify_synthesized_unknown(
    task: dict[str, Any],
    hidden: dict[str, Any],
    candidates: list[tuple[str, str, str]],
    transcript: list[dict[str, Any]],
    meter: BeyondMeter,
) -> dict[str, Any]:
    working = list(candidates)
    confirm_rows: list[dict[str, Any]] = []
    state = hidden
    for _ in range(MAX_CONFIRMATORY):
        if not working:
            break
        if confirm_rows and len(spec_groups(working)) == 1:
            break
        action = _unused_confirm_action(transcript + confirm_rows)
        if action is None:
            break
        applied = apply_hidden(task["mechanism"], state, action)
        state = applied["state"]
        meter.confirmatory_env_probes += 1
        row = dict(action=action, observation=applied["observation"])
        confirm_rows.append(row)
        working = filter_specs(working, [row], meter)
    groups = spec_groups(working)
    if not working or len(groups) != 1:
        return dict(
            confident_acquisition=False,
            abstained_unknown=True,
            representative=None,
            confirm_rows=confirm_rows,
            survivors=[spec_name(spec) for spec in working],
            hidden=state,
        )
    return dict(
        confident_acquisition=True,
        abstained_unknown=False,
        representative=spec_name(groups[0][0]),
        confirm_rows=confirm_rows,
        survivors=[spec_name(spec) for spec in groups[0]],
        hidden=state,
    )


def run_spec_holdout(task: dict[str, Any], name: str | None) -> list[dict[str, Any]]:
    hidden = blank_state(int(task["instance_seed"]) + 10007)
    spec = parse_spec(name)
    rows = []
    for action in HOLDOUT_PROBES:
        observed = apply_hidden(task["mechanism"], hidden, action)
        hidden = observed["state"]
        predicted = apply_spec(spec, action) if spec is not None else None
        rows.append(dict(
            action=action, observed=observed["observation"],
            predicted=predicted, oracle=int(observed["oracle"]),
        ))
    return rows


def populate_guard_library(source_rows: list[dict[str, Any]]) -> tuple[SubMechanismLibrary, int]:
    library = SubMechanismLibrary()
    distill_cost = 0
    for episode in source_rows:
        if not episode.get("useful_acquisition"):
            continue
        library.remember_whole(episode["mechanism"], episode.get("transcript") or [])
        distill_cost += 1
        guard = MECHANISM_GUARD.get(str(episode["mechanism"]))
        distill_cost += 1
        if guard:
            distill_cost += 2
            library.remember_subclause(dict(
                source_mechanism=episode["mechanism"],
                source_task=episode["task_id"],
                guard=guard,
                signature=POS_SIGNATURE if guard == "pos" else NEG_SIGNATURE if guard == "neg" else guard,
                clause=guard + "_guard",
            ))
    library.distill_cost = distill_cost
    return library, distill_cost


def _untrained_open_available(transcript: list[dict[str, Any]], remaining: list[str]) -> list[str]:
    kept = [action for action in QUERY_ACTIONS if action not in {
        row["action"] for row in transcript if not str(row["action"]).startswith("STOP")
    }]
    kept.append("STOP_UNRESOLVED")
    if remaining and len(observational_groups(remaining)) == 1:
        kept.append("STOP_EQUIVALENT")
    if len(remaining) == 1 and remaining[0] in LANGUAGE:
        kept.append("STOP_IDENTIFY")
    return kept


def _choose_untrained_open(remaining: list[str], available: list[str],
                           env_count: int) -> dict[str, Any]:
    if remaining and len(observational_groups(remaining)) == 1 and "STOP_EQUIVALENT" in available:
        return dict(action="STOP_EQUIVALENT", reason="one_class")
    if not remaining and env_count >= UNTRAINED_OPEN_PROBES:
        return dict(action="STOP_UNRESOLVED", reason="open_probe_budget")
    if remaining:
        for action in DIAGNOSTIC_ORDER:
            if action in available:
                return dict(action=action, reason="untrained_open")
    else:
        for action in DIAGNOSTIC_ORDER:
            if action in available and action not in ("RESET", "MEASURE"):
                return dict(action=action, reason="untrained_open_continue")
        for action in DIAGNOSTIC_ORDER:
            if action in available:
                return dict(action=action, reason="untrained_open_continue")
    return dict(action="STOP_UNRESOLVED", reason="untrained_open_stop")


def run_beyond_episode(
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
    for step in range(MAX_STEPS):
        remaining = filter_named_bank(transcript, SUPPLIED_BANK, meter)
        feats = bank_features(transcript, remaining, MAX_STEPS - step, meter if learned else None)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        if method == "untrained_open_grammar":
            available = _untrained_open_available(transcript, remaining)
            choice = _choose_untrained_open(remaining, available, meter.env_interactions)
        else:
            available = adaptive_available(transcript, remaining)
            choice = _choose(
                "source_learned_adaptive_policy", remaining, available, transcript,
                feats, weights, order, rng, meter,
            )
        action = choice["action"]
        if action not in available:
            raise ValueError("chose_unavailable:" + action)
        if action in ACQUIRE_STOPS:
            if remaining:
                challenge = _unused_confirm_action(transcript)
                if challenge is not None:
                    applied = apply_hidden(task["mechanism"], hidden, challenge)
                    hidden = applied["state"]
                    meter.env_interactions += 1
                    transcript.append(dict(
                        action=challenge, observation=applied["observation"],
                        remaining=list(remaining), features=feats,
                        reason="bank_singleton_challenge",
                    ))
                    remaining = filter_named_bank(transcript, SUPPLIED_BANK)
                    if not remaining:
                        stopped = "catalog_exhausted"
                        transcript.append(dict(
                            action="STOP_UNRESOLVED", observation=None,
                            remaining=[], features=feats, reason=choice.get("reason"),
                        ))
                        break
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
        if method == "untrained_open_grammar" and meter.env_interactions >= UNTRAINED_OPEN_PROBES:
            stopped = "open_probe_budget"
            break
    else:
        stopped = "budget"
    peek = filter_named_bank(transcript, SUPPLIED_BANK)
    if not peek and method != "supplied_bank_only":
        for needed in ("ACT_1", "ACT_NEG"):
            if any(row["action"] == needed for row in transcript):
                continue
            applied = apply_hidden(task["mechanism"], hidden, needed)
            hidden = applied["state"]
            meter.env_interactions += 1
            transcript.append(dict(
                action=needed, observation=applied["observation"],
                remaining=[],
                reason="required_act1_before_synthesis",
            ))
    detection = detect_catalog_exhaustion(transcript, meter)
    remaining = list(detection["remaining"])
    catalog_exhausted = bool(detection["catalog_exhausted"])
    if identified is not None and identified not in remaining:
        identified = None
    confirm_rows: list[dict[str, Any]] = []
    synthesized = dict(remaining=list(remaining), representative=None, n_remaining=len(remaining))
    confident = False
    abstained = False
    sub_hits = 0
    unknown_kind = task.get("unknown_kind") or ("in_bank" if not catalog_exhausted else "exhausted")
    representative = None
    if not catalog_exhausted:
        groups = observational_groups(remaining)
        representative = groups[0][0] if len(groups) == 1 else None
        synthesized = dict(
            remaining=list(remaining),
            classes=groups,
            representative=representative,
            n_remaining=len(remaining),
            n_classes=len(groups),
            origin="supplied_bank",
        )
        holdout = _bank_or_spec_holdout(task, representative, None)
        confident = bool(representative)
        abstained = not confident
    elif method == "supplied_bank_only":
        abstained = True
        holdout = _bank_or_spec_holdout(task, None, None)
        synthesized = dict(
            remaining=[], representative=None, n_remaining=0,
            origin="bank_abstain", catalog_exhausted=True,
        )
    else:
        use_library = method == ABDUCTIVE
        built = synthesize_beyond_bank(transcript, library if use_library else None, meter)
        sub_hits = int(built["subclause_hits"])
        unknown_kind = built["kind"] if catalog_exhausted else unknown_kind
        verified = verify_synthesized_unknown(task, hidden, list(built["specs"]), transcript, meter)
        confirm_rows = list(verified["confirm_rows"])
        confident = bool(verified["confident_acquisition"])
        abstained = bool(verified["abstained_unknown"])
        representative = verified["representative"]
        synthesized = dict(
            remaining=list(built["remaining"]),
            representative=representative,
            n_remaining=int(built["n_remaining"]),
            origin="residual_grammar" if built["kind"] == "type_a" else "open_grammar",
            retrieved_guards=list(built["retrieved_guards"]),
            catalog_exhausted=True,
            survivors=list(verified["survivors"]),
        )
        holdout = _bank_or_spec_holdout(task, None, representative)
        if use_library and confident and representative and library is not None:
            spec = parse_spec(representative)
            if spec:
                library.remember_subclause(dict(
                    source_mechanism=representative,
                    source_task=task["task_id"],
                    guard=spec[0],
                    signature=spec[0],
                    clause=spec[0] + "_stream",
                    then_leaf=spec[1],
                    else_leaf=spec[2],
                ))
    claims = score_claims(task, remaining if not catalog_exhausted else [], synthesized, identified, stopped, holdout)
    false_positive = bool(
        catalog_exhausted and method == "supplied_bank_only" and (
            claims["useful_acquisition"] or claims["predictive_competence"] or identified
        )
    )
    if false_positive or (catalog_exhausted and method == "supplied_bank_only"):
        claims["useful_acquisition"] = False
        claims["predictive_competence"] = False
    work = meter.as_dict()
    return dict(
        task_id=task["task_id"],
        family=task["family"],
        split=task["split"],
        mechanism=task["mechanism"],
        role=task.get("role"),
        unknown_kind=unknown_kind,
        method=method,
        transcript=transcript,
        confirm_rows=confirm_rows,
        synthesized=synthesized,
        holdout=holdout,
        stopped=stopped,
        identified=identified,
        remaining=list(remaining),
        catalog_exhausted=catalog_exhausted,
        surviving_bank_candidates=int(detection["surviving_bank_candidates"]),
        confident_acquisition=confident,
        abstained_unknown=abstained,
        false_positive=false_positive,
        whole_mechanism_hits=0,
        subclause_hits=sub_hits,
        retrieve=library is not None,
        remember=method == ABDUCTIVE,
        memory_cleared=library is None,
        track_b_closed=TRACK_B_CLOSED,
        instance_seed=task["instance_seed"],
        language_hash=language_hash(),
        **work,
        **claims,
    )


def _bank_or_spec_holdout(task: dict[str, Any], bank_name: str | None,
                          spec_name_value: str | None) -> list[dict[str, Any]]:
    if spec_name_value:
        return run_spec_holdout(task, spec_name_value)
    hidden = blank_state(int(task["instance_seed"]) + 10007)
    hypo = dict(s=0, prev=0)
    rows = []
    for action in HOLDOUT_PROBES:
        observed = apply_hidden(task["mechanism"], hidden, action)
        hidden = observed["state"]
        predicted = None
        if bank_name is not None:
            guessed = apply_candidate(bank_name, hypo, action)
            hypo = guessed["state"]
            predicted = guessed["observation"]
        rows.append(dict(
            action=action, observed=observed["observation"],
            predicted=predicted, oracle=int(observed["oracle"]),
        ))
    return rows


def _method_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        cell = out.setdefault(row["method"], dict(
            n=0, useful_acquisition=0, predictive_competence=0,
            exact_mechanism_identification=0, catalog_exhausted=0,
            abstained_unknown=0, false_positive=0, confident_acquisition=0,
            env_interactions=0, confirmatory_env_probes=0, bank_hyp_evals=0,
            hypothesis_evals=0, probe_feature_and_policy_evals=0,
            retrieval_evals=0, distill_cost=0, residual_synthesis_evals=0,
            total_acquisition_work=0, whole_mechanism_hits=0, subclause_hits=0,
        ))
        cell["n"] += 1
        for key in (
            "useful_acquisition", "predictive_competence", "exact_mechanism_identification",
            "catalog_exhausted", "abstained_unknown", "false_positive", "confident_acquisition",
        ):
            cell[key] += int(bool(row.get(key)))
        for key in (
            "env_interactions", "confirmatory_env_probes", "bank_hyp_evals",
            "hypothesis_evals", "probe_feature_and_policy_evals",
            "retrieval_evals", "distill_cost", "residual_synthesis_evals",
            "total_acquisition_work", "whole_mechanism_hits", "subclause_hits",
        ):
            cell[key] += int(row.get(key) or 0)
    return out


def _library_from_snapshot(snapshot: dict[str, Any]) -> SubMechanismLibrary:
    library = SubMechanismLibrary()
    for clause in snapshot.get("clauses") or []:
        library.remember_subclause(clause)
    return library


def reconstruct_work(episode: dict[str, Any], library: SubMechanismLibrary | None = None) -> dict[str, int]:
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
            meter.probe_feature_and_policy_evals += len(available)
        meter.env_interactions += 1
        prefix.append(step)
    if stops:
        remaining = filter_named_bank(prefix, SUPPLIED_BANK, meter)
        if learned:
            bank_features(prefix, remaining, MAX_STEPS - len(prefix), meter)
            available = adaptive_available(prefix, remaining)
            meter.probe_feature_and_policy_evals += len(available)
    prefix.extend(extras)
    meter.env_interactions += sum(
        1 for row in extras if not str(row["action"]).startswith("STOP")
    )
    detection = detect_catalog_exhaustion(prefix, meter)
    if detection["catalog_exhausted"] and method != "supplied_bank_only":
        use_library = method == ABDUCTIVE
        built = synthesize_beyond_bank(prefix, library if use_library else None, meter)
        working = list(built["specs"])
        for row in episode.get("confirm_rows") or []:
            meter.confirmatory_env_probes += 1
            working = filter_specs(working, [row], meter)
    meter.distill_cost = int(episode.get("distill_cost") or 0)
    return meter.as_dict()


def evaluate_gates(seed_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    gate1 = True
    gate2 = True
    gate3 = True
    for block in seed_blocks:
        totals = block["assessment_totals"]
        retain = block["retain_totals"]
        bank = totals.get("supplied_bank_only") or {}
        untrained = totals.get("untrained_open_grammar") or {}
        cleared = totals.get("learned_policy_open_grammar_cleared") or {}
        abduct = totals.get(ABDUCTIVE) or {}
        if int(bank.get("catalog_exhausted") or 0) != 4:
            gate1 = False
            notes.append("gate1_bank_exhaust_seed_{0}".format(block["seed"]))
        if int(bank.get("useful_acquisition") or 0) != 0 or int(bank.get("false_positive") or 0) != 0:
            gate1 = False
            notes.append("gate1_bank_fp_seed_{0}".format(block["seed"]))
        for name in ("untrained_open_grammar", "learned_policy_open_grammar_cleared", ABDUCTIVE):
            if int((totals.get(name) or {}).get("useful_acquisition") or -1) != 4:
                gate1 = False
                notes.append("gate1_holdout_{0}_{1}".format(name, block["seed"]))
            if int((retain.get(name) or {}).get("useful_acquisition") or -1) != 2:
                gate1 = False
                notes.append("gate1_retain_{0}_{1}".format(name, block["seed"]))
        if int(cleared.get("total_acquisition_work") or 10**9) >= int(untrained.get("total_acquisition_work") or 0):
            gate2 = False
            notes.append("gate2_seed_{0}".format(block["seed"]))
        if int(abduct.get("total_acquisition_work") or 10**9) >= int(cleared.get("total_acquisition_work") or 0):
            gate3 = False
            notes.append("gate3_seed_{0}".format(block["seed"]))
        type_b = [
            row for row in block.get("holdout") or []
            if row.get("method") == ABDUCTIVE and row.get("mechanism") == "oob_even_add2"
        ]
        if type_b and int(type_b[0].get("subclause_hits") or 0) != 0:
            gate3 = False
            notes.append("gate3_type_b_false_hit_seed_{0}".format(block["seed"]))
        if type_b and not type_b[0].get("useful_acquisition"):
            gate3 = False
            notes.append("gate3_type_b_fail_seed_{0}".format(block["seed"]))
    return dict(
        gate1_zero_false_positives_calibrated_unknowns=gate1,
        gate2_adaptive_beats_untrained_open_grammar=gate2,
        gate3_abductive_beats_cleared_open_grammar=gate3,
        passed=bool(gate1 and gate2 and gate3),
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"),
            task_id=row["task_id"],
            split=row["split"],
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
            total_acquisition_work=int(row["total_acquisition_work"]),
            catalog_exhausted=bool(row.get("catalog_exhausted")),
            abstained_unknown=bool(row.get("abstained_unknown")),
            confident_acquisition=bool(row.get("confident_acquisition")),
            false_positive=bool(row.get("false_positive")),
            subclause_hits=int(row.get("subclause_hits") or 0),
            solved=bool(row.get("useful_acquisition")),
        )
        for row in rows
    ]


def run_beyond_catalog(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = unfamiliar_policy_tasks("up_source")
    holdout = unfamiliar_policy_tasks("oob_holdout")
    retain = unfamiliar_policy_tasks("oob_retain")
    if any(row["task_id"] in OPENED_IDS for row in holdout + retain):
        raise ValueError("opened_id_in_challenge")
    if any(row["mechanism"] in SUPPLIED_BANK for row in holdout):
        raise ValueError("holdout_in_supplied_bank")
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
        frozen = policy_hash({action: weights.get(action, [0.0] * len(FEATURE_NAMES)) for action in ACTIONS})
        order = distill_order(teacher)
        wave1, distill_cost = populate_guard_library(own)
        hold_rows = []
        retain_rows = []
        for method in METHODS:
            use_lib = method == ABDUCTIVE
            library = _library_from_snapshot(wave1.snapshot()) if use_lib else None
            used = zero_acquire() if method == "untrained_open_grammar" else _with_stops(weights)
            for index, task in enumerate(holdout):
                rng = random.Random((80 + seed) * 1009 + index * 17 + 11)
                episode = run_beyond_episode(task, method, used, order, rng, library)
                episode["source_seed"] = seed
                extra = distill_cost if (use_lib and index == 0) else 0
                episode["distill_cost"] = extra
                episode["total_acquisition_work"] = int(episode["total_acquisition_work"]) + extra
                hold_rows.append(episode)
            for index, task in enumerate(retain):
                rng = random.Random((90 + seed) * 1009 + index * 17 + 11)
                episode = run_beyond_episode(task, method, used, order, rng, library)
                episode["source_seed"] = seed
                retain_rows.append(episode)
        assessment_rows.extend(hold_rows)
        assessment_rows.extend(retain_rows)
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=frozen,
            distilled_order=list(order),
            wave1_library=wave1.snapshot(),
            holdout=hold_rows,
            retain=retain_rows,
            assessment_totals=_method_totals(hold_rows),
            retain_totals=_method_totals(retain_rows),
        ))
    gates = evaluate_gates(seed_blocks)
    holdout_only = [row for row in assessment_rows if row["split"] == "oob_holdout"]
    retain_only = [row for row in assessment_rows if row["split"] == "oob_retain"]
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
        skill_work_artifact="a2cc77d66bcd80a3107e25542e8e96c94fea8348dd59b8c6496b3b568c1cabf2",
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
        supplied_bank=list(SUPPLIED_BANK),
        holdout_mechanisms=[row["mechanism"] for row in holdout],
        bank_coverage=0.0,
        assessment=assessment_rows,
        seed_blocks=[{k: block[k] for k in (
            "seed", "policy_hash", "distilled_order", "wave1_library",
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
    (directory / "seed_unfamiliar_beyond_catalog.json").write_text(
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
    if payload.get("bank_coverage") not in (0, 0.0):
        ok = False
        notes.append("bank_coverage")
    rows = list(payload.get("assessment") or [])
    if any(row["task_id"] in OPENED_IDS for row in rows):
        ok = False
        notes.append("rescored_opened")
    if any(row.get("exact_mechanism_identification") for row in rows):
        ok = False
        notes.append("exact_claimed")
    rebuilt = _method_totals([row for row in rows if row.get("split") == "oob_holdout"])
    saved = (payload.get("totals") or {}).get("holdout") or {}
    for name, cell in rebuilt.items():
        other = saved.get(name) or {}
        for key in ("useful_acquisition", "total_acquisition_work", "catalog_exhausted", "false_positive"):
            if cell.get(key) != other.get(key):
                ok = False
                notes.append("column:" + name + ":" + key)
    libraries = {
        block["seed"]: _library_from_snapshot(block.get("wave1_library") or {})
        for block in payload.get("seed_blocks") or []
    }
    seen: dict[tuple[int, str], int] = {}
    for row in rows:
        seed = int(row.get("source_seed"))
        method = row["method"]
        library = None
        if method == ABDUCTIVE:
            library = libraries[seed]
        reconstructed = reconstruct_work(row, library)
        for key in (
            "env_interactions", "confirmatory_env_probes", "hypothesis_evals",
            "retrieval_evals", "distill_cost", "residual_synthesis_evals",
            "total_acquisition_work",
        ):
            if reconstructed.get(key) != row.get(key):
                ok = False
                notes.append("reconstruct:" + row["task_id"] + ":" + method + ":" + key)
                break
        if method == ABDUCTIVE and row.get("split") == "oob_holdout" and row.get("confident_acquisition"):
            spec = parse_spec(row.get("synthesized", {}).get("representative"))
            if spec:
                library.remember_subclause(dict(
                    source_mechanism=spec_name(spec),
                    source_task=row["task_id"],
                    guard=spec[0],
                    signature=spec[0],
                    clause=spec[0] + "_stream",
                ))
        seen[(seed, method)] = seen.get((seed, method), 0) + 1
    gates = evaluate_gates(_blocks_with_holdout(payload, rows))
    saved_gates = payload.get("gates") or {}
    for key in (
        "gate1_zero_false_positives_calibrated_unknowns",
        "gate2_adaptive_beats_untrained_open_grammar",
        "gate3_abductive_beats_cleared_open_grammar",
        "passed",
    ):
        if gates.get(key) != saved_gates.get(key):
            ok = False
            notes.append("gates:" + key)
    if not saved_gates.get("passed"):
        ok = False
        notes.append("gates_failed")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)


def _blocks_with_holdout(payload: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks = []
    for block in payload.get("seed_blocks") or []:
        seed = block["seed"]
        holdout = [row for row in rows if row.get("source_seed") == seed and row.get("split") == "oob_holdout"]
        retain = [row for row in rows if row.get("source_seed") == seed and row.get("split") == "oob_retain"]
        blocks.append(dict(
            seed=seed,
            assessment_totals=block.get("assessment_totals") or _method_totals(holdout),
            retain_totals=block.get("retain_totals") or _method_totals(retain),
            holdout=holdout,
        ))
    return blocks
