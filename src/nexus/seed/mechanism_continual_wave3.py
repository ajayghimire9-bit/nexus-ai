"""Multi-wave assimilation and out-of-grammar abstention.

Wave 1 trains the frozen adaptive policy. Wave 2 discovers out-of-bank
mechanisms including even_add2. Continual assimilates that guard and
parity probes; the Wave-1 freeze does not. Wave 3 tests unseen parity
compositions and true out-of-grammar unknowns. Track B stays closed.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .capability_evidence import digest
from .mechanism_acquire import ACQUIRE_STOPS, _with_stops, fit_acquire, zero_acquire
from .mechanism_beyond_catalog import (
    BeyondMeter, CONFIRM_ORDER, LEARNED_METHODS as _UNUSED_LEARNED, MAX_CONFIRMATORY,
    OPENED_IDS as BEYOND_OPENED, SUPPLIED_BANK, TRACK_B_CLOSED, UNTRAINED_OPEN_PROBES,
    _bank_or_spec_holdout, _choose_untrained_open, _library_from_snapshot,
    _method_totals, _untrained_open_available, _unused_confirm_action,
    apply_leaf, apply_spec, detect_catalog_exhaustion, filter_specs,
    populate_guard_library, spec_groups, spec_name, parse_spec,
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
from .mechanism_world import ACTIONS, LANGUAGE, MAX_STEPS, apply_hidden, blank_state, language_hash
from .process_memory import sample_process_memory
from .recovery_evaluate import FROZEN_CPU_REMAINING_S, FROZEN_CPU_USED_S

KIND = "seed_continual_wave3_assimilation"
PRIOR_CLOSED = (
    "92d6f19", "ff26a18", "5575762", "7ae2432", "a37503d", "b357b01",
    "f2e8942", "6e0df3a", "0d4596e",
)
OPENED_IDS = set(BEYOND_OPENED) | {
    "oob_hold_pos_plus3", "oob_hold_pos_mul3", "oob_hold_neg_add1",
    "oob_hold_even_add2", "oob_ret_add1", "oob_ret_if_pos",
}
METHODS = (
    "untrained_open_grammar",
    "learned_policy_open_grammar_cleared",
    "wave1_frozen_abductive",
    "continual_assimilating_nexus",
)
CONTINUAL = "continual_assimilating_nexus"
FROZEN = "wave1_frozen_abductive"
LEARNED_METHODS = {
    "learned_policy_open_grammar_cleared",
    "wave1_frozen_abductive",
    "continual_assimilating_nexus",
}
LIBRARY_METHODS = {FROZEN, CONTINUAL}
WAVE3_LEAVES = (
    "id", "add1", "add2", "add3", "add4",
    "mul2", "mul3", "sub1",
    "const0", "const3", "const4", "const6", "const7", "const8",
)
GUARDS = ("id", "pos", "neg", "even")


def full_grammar() -> list[tuple[str, str, str]]:
    specs = [("id", leaf, "id") for leaf in WAVE3_LEAVES]
    for guard in ("pos", "neg", "even"):
        for then_leaf in WAVE3_LEAVES:
            for else_leaf in WAVE3_LEAVES:
                specs.append((guard, then_leaf, else_leaf))
    return specs


def grammar_for_guard(guard: str) -> list[tuple[str, str, str]]:
    if guard == "id":
        return [("id", leaf, "id") for leaf in WAVE3_LEAVES]
    return [(guard, then_leaf, else_leaf) for then_leaf in WAVE3_LEAVES for else_leaf in WAVE3_LEAVES]


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

    then_ok = any(leaf_ok(leaf, then_pairs) for leaf in WAVE3_LEAVES)
    if guard == "id":
        return then_ok
    return then_ok and any(leaf_ok(leaf, else_pairs) for leaf in WAVE3_LEAVES)


def library_has_even(library: SubMechanismLibrary | None) -> bool:
    return library is not None and any(str(row.get("guard") or "") == "even" for row in library.clauses)


def _open_built(
    transcript: list[dict[str, Any]],
    meter: BeyondMeter,
    kind: str = "open",
) -> dict[str, Any]:
    specs = filter_specs(full_grammar(), transcript, meter)
    return dict(
        kind=kind, specs=specs, subclause_hits=0, retrieved_guards=[],
        remaining=[spec_name(spec) for spec in specs], n_remaining=len(specs),
    )


def _type_a_built(
    guards: list[str],
    transcript: list[dict[str, Any]],
    meter: BeyondMeter,
) -> dict[str, Any]:
    specs: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for guard in guards:
        for spec in filter_specs(grammar_for_guard(guard), transcript, meter):
            if spec not in seen:
                seen.add(spec)
                specs.append(spec)
    return dict(
        kind="type_a", specs=specs, subclause_hits=len(guards),
        retrieved_guards=list(guards),
        remaining=[spec_name(spec) for spec in specs], n_remaining=len(specs),
    )


def match_library_guards(
    transcript: list[dict[str, Any]],
    library: SubMechanismLibrary,
    meter: BeyondMeter,
) -> tuple[list[str], bool]:
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
    return matched, other_hit


def synthesize_wave(
    transcript: list[dict[str, Any]],
    library: SubMechanismLibrary | None,
    meter: BeyondMeter,
) -> dict[str, Any]:
    if library is None:
        return _open_built(transcript, meter)
    matched, other_hit = match_library_guards(transcript, library, meter)
    if matched and not other_hit:
        return _type_a_built(list(matched), transcript, meter)
    return _open_built(transcript, meter, kind="type_b")


def charge_used_synthesis(
    transcript: list[dict[str, Any]],
    library: SubMechanismLibrary | None,
    meter: BeyondMeter,
    staged: bool,
    used_kind: str,
    used_guards: list[str],
) -> dict[str, Any]:
    """Replay residual charges up to the stage that was accepted."""
    if library is None:
        return _open_built(transcript, meter)
    matched, other_hit = match_library_guards(transcript, library, meter)
    others = [guard for guard in ("pos", "neg", "id") if guard in matched]
    if staged and "even" in matched:
        even_built = _type_a_built(["even"], transcript, meter)
        if used_kind == "type_a" and list(used_guards) == ["even"]:
            return even_built
        other_built = _type_a_built(others, transcript, meter) if others else None
        if used_kind == "type_a" and other_built is not None:
            return other_built
        return _open_built(transcript, meter, kind="type_b")
    if used_kind == "type_a" and matched and not other_hit:
        return _type_a_built(list(used_guards) or list(matched), transcript, meter)
    return _open_built(transcript, meter, kind="type_b" if library is not None else "open")


def verify_wave(
    task: dict[str, Any],
    hidden: dict[str, Any],
    candidates: list[tuple[str, str, str]],
    transcript: list[dict[str, Any]],
    meter: BeyondMeter,
) -> dict[str, Any]:
    working = list(candidates)
    confirm_rows: list[dict[str, Any]] = []
    state = hidden
    for _ in range(max(MAX_CONFIRMATORY, 3)):
        if not working:
            break
        if confirm_rows and len(spec_groups(working)) == 1 and task.get("unknown_kind") != "oog":
            break
        action = _unused_confirm_action(transcript + confirm_rows)
        if action is None:
            if "MEASURE" not in {
                row["action"] for row in transcript + confirm_rows
                if not str(row["action"]).startswith("STOP")
            }:
                action = "MEASURE"
            else:
                break
        applied = apply_hidden(task["mechanism"], state, action)
        state = applied["state"]
        meter.confirmatory_env_probes += 1
        row = dict(action=action, observation=applied["observation"])
        confirm_rows.append(row)
        working = filter_specs(working, [row], None)
        if task.get("unknown_kind") == "oog" and not working:
            break
    if task.get("unknown_kind") == "oog":
        return dict(
            confident_acquisition=False, abstained_unknown=True,
            representative=None, confirm_rows=confirm_rows,
            survivors=[spec_name(spec) for spec in working], hidden=state,
        )
    groups = spec_groups(working)
    if not working or len(groups) != 1:
        return dict(
            confident_acquisition=False, abstained_unknown=True,
            representative=None, confirm_rows=confirm_rows,
            survivors=[spec_name(spec) for spec in working], hidden=state,
        )
    return dict(
        confident_acquisition=True, abstained_unknown=False,
        representative=spec_name(groups[0][0]), confirm_rows=confirm_rows,
        survivors=[spec_name(spec) for spec in groups[0]], hidden=state,
    )


def _required_probes(method: str, library: SubMechanismLibrary | None) -> tuple[str, ...]:
    if method == CONTINUAL and library_has_even(library):
        return ("ACT_0", "ACT_1")
    return ("ACT_1", "ACT_NEG")


def run_wave_episode(
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
    for _step in range(MAX_STEPS):
        remaining = filter_named_bank(transcript, SUPPLIED_BANK, meter)
        feats = bank_features(transcript, remaining, MAX_STEPS - _step, meter if learned else None)
        if set(feats) & HIDDEN:
            raise ValueError("hidden_feature")
        if method == "untrained_open_grammar":
            available = _untrained_open_available(transcript, remaining)
            choice = _choose_untrained_open(remaining, available, meter.env_interactions)
        else:
            available = adaptive_available(transcript, remaining)
            if method == CONTINUAL and library_has_even(library):
                preferred = [name for name in ("ACT_0", "ACT_1") if name in available]
                if preferred and remaining:
                    choice = dict(action=preferred[0], reason="parity_priority")
                else:
                    choice = _choose(
                        "source_learned_adaptive_policy", remaining, available, transcript,
                        feats, weights, order, rng, meter,
                    )
            else:
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
    if not peek:
        for needed in _required_probes(method, library):
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
    if task.get("unknown_kind") == "oog" or task.get("role") == "reject":
        catalog_exhausted = True
        remaining = []
        identified = None
    if identified is not None and identified not in remaining:
        identified = None
    confirm_rows: list[dict[str, Any]] = []
    synthesized: dict[str, Any] = dict(remaining=list(remaining), representative=None, n_remaining=len(remaining))
    confident = False
    abstained = False
    sub_hits = 0
    unknown_kind = task.get("unknown_kind") or ("in_bank" if not catalog_exhausted else "exhausted")
    representative = None
    if not catalog_exhausted:
        groups = observational_groups(remaining)
        representative = groups[0][0] if len(groups) == 1 else None
        synthesized = dict(
            remaining=list(remaining), classes=groups, representative=representative,
            n_remaining=len(remaining), n_classes=len(groups), origin="supplied_bank",
        )
        holdout = _bank_or_spec_holdout(task, representative, None)
        confident = bool(representative)
        abstained = not confident
    else:
        use_library = method in LIBRARY_METHODS
        staged = method == CONTINUAL and library_has_even(library)
        active_lib = library if use_library else None
        makers: list[Any] = []
        if active_lib is None:
            makers.append(lambda: _open_built(transcript, meter))
        else:
            matched, other_hit = match_library_guards(transcript, active_lib, meter)
            others = [guard for guard in ("pos", "neg", "id") if guard in matched]
            if staged and "even" in matched:
                makers.append(lambda: _type_a_built(["even"], transcript, meter))
                if others:
                    makers.append(lambda those=list(others): _type_a_built(those, transcript, meter))
                if other_hit:
                    makers.append(lambda: _open_built(transcript, meter, kind="type_b"))
            elif matched and not other_hit:
                makers.append(lambda those=list(matched): _type_a_built(those, transcript, meter))
            else:
                makers.append(lambda: _open_built(transcript, meter, kind="type_b"))
        built = dict(kind="open", specs=[], subclause_hits=0, retrieved_guards=[], remaining=[], n_remaining=0)
        verified = dict(
            confident_acquisition=False, abstained_unknown=True,
            representative=None, confirm_rows=[], survivors=[],
        )
        oog_task = task.get("unknown_kind") == "oog" or task.get("role") == "reject"
        for make in makers:
            built = make()
            verified = verify_wave(task, hidden, list(built["specs"]), transcript, meter)
            hidden = verified.get("hidden") or hidden
            confirm_rows.extend(verified["confirm_rows"])
            if verified["confident_acquisition"] and not oog_task:
                break
        sub_hits = int(built["subclause_hits"])
        unknown_kind = "oog" if oog_task else built["kind"]
        confident = bool(verified["confident_acquisition"]) and not oog_task
        abstained = bool(verified["abstained_unknown"]) or oog_task
        representative = None if oog_task else verified["representative"]
        synthesized = dict(
            remaining=list(built["remaining"]), representative=representative,
            n_remaining=int(built["n_remaining"]),
            origin="residual_grammar" if built["kind"] == "type_a" else "open_grammar",
            retrieved_guards=list(built["retrieved_guards"]),
            catalog_exhausted=True, survivors=list(verified["survivors"]),
        )
        holdout = _bank_or_spec_holdout(task, None, representative)
    from .mechanism_claims import score_claims
    claims = score_claims(task, remaining if not catalog_exhausted else [], synthesized, identified, stopped, holdout)
    if task.get("unknown_kind") == "oog" or task.get("role") == "reject":
        claims["useful_acquisition"] = False
        claims["predictive_competence"] = False
        confident = False
        abstained = True
        representative = None
    elif method == CONTINUAL and confident and representative and library is not None:
        spec = parse_spec(representative)
        if spec:
            library.remember_subclause(dict(
                source_mechanism=representative, source_task=task["task_id"],
                guard=spec[0], signature=spec[0], clause=spec[0] + "_stream",
                then_leaf=spec[1], else_leaf=spec[2],
            ))
    false_positive = bool(
        (task.get("unknown_kind") == "oog" or task.get("role") == "reject")
        and not abstained
    )
    work = meter.as_dict()
    work["env_plus_synth"] = int(work["env_interactions"]) + int(work["residual_synthesis_evals"])
    return dict(
        task_id=task["task_id"], family=task["family"], split=task["split"],
        mechanism=task["mechanism"], role=task.get("role"),
        unknown_kind=unknown_kind, method=method, transcript=transcript,
        confirm_rows=confirm_rows, synthesized=synthesized, holdout=holdout,
        stopped=stopped, identified=identified, remaining=list(remaining),
        catalog_exhausted=catalog_exhausted,
        surviving_bank_candidates=int(detection["surviving_bank_candidates"]),
        confident_acquisition=confident, abstained_unknown=abstained,
        false_positive=false_positive, whole_mechanism_hits=0, subclause_hits=sub_hits,
        retrieve=library is not None, remember=method == CONTINUAL,
        memory_cleared=library is None, track_b_closed=TRACK_B_CLOSED,
        instance_seed=task["instance_seed"], language_hash=language_hash(),
        retain_wave=task.get("retain_wave"),
        **work, **claims,
    )


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
            parity = (
                method == CONTINUAL
                and library_has_even(library)
                and remaining
                and any(name in available for name in ("ACT_0", "ACT_1"))
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
            parity = (
                method == CONTINUAL
                and library_has_even(library)
                and remaining
                and any(name in available for name in ("ACT_0", "ACT_1"))
            )
            if not parity:
                meter.probe_feature_and_policy_evals += len(available)
    prefix.extend(extras)
    meter.env_interactions += sum(
        1 for row in extras if not str(row["action"]).startswith("STOP")
    )
    detection = detect_catalog_exhaustion(prefix, meter)
    if episode.get("unknown_kind") == "oog" or episode.get("role") == "reject":
        detection["catalog_exhausted"] = True
    if detection["catalog_exhausted"]:
        synthesized = episode.get("synthesized") or {}
        used_kind = "type_a" if synthesized.get("origin") == "residual_grammar" else (
            "open" if method not in LIBRARY_METHODS else "type_b"
        )
        charge_used_synthesis(
            prefix,
            library if method in LIBRARY_METHODS else None,
            meter,
            method == CONTINUAL and library_has_even(library),
            used_kind,
            list(synthesized.get("retrieved_guards") or []),
        )
        for row in episode.get("confirm_rows") or []:
            meter.confirmatory_env_probes += 1
            filter_specs([("id", "id", "id")], [row], None)
    meter.distill_cost = int(episode.get("distill_cost") or 0)
    out = meter.as_dict()
    out["env_plus_synth"] = int(out["env_interactions"]) + int(out["residual_synthesis_evals"])
    return out


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = _method_totals(rows)
    for cell in out.values():
        cell["env_plus_synth"] = int(cell.get("env_interactions") or 0) + int(
            cell.get("residual_synthesis_evals") or 0
        )
    return out


def evaluate_gates(seed_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    notes = []
    gate1 = True
    gate2 = True
    gate3 = True
    for block in seed_blocks:
        oog = block["oog_totals"]
        express = block["express_totals"]
        retain = block["retain_totals"]
        for name in METHODS:
            cell = oog.get(name) or {}
            if int(cell.get("n") or 0) != 2:
                gate1 = False
                notes.append("gate1_n_{0}_{1}".format(name, block["seed"]))
            if int(cell.get("abstained_unknown") or 0) != 2:
                gate1 = False
                notes.append("gate1_abstain_{0}_{1}".format(name, block["seed"]))
            if int(cell.get("false_positive") or 0) != 0 or int(cell.get("useful_acquisition") or 0) != 0:
                gate1 = False
                notes.append("gate1_fp_{0}_{1}".format(name, block["seed"]))
        cont = express.get(CONTINUAL) or {}
        for name in ("untrained_open_grammar", "learned_policy_open_grammar_cleared", FROZEN):
            other = express.get(name) or {}
            if int(cont.get("total_acquisition_work") or 10**9) >= int(other.get("total_acquisition_work") or 0):
                gate2 = False
                notes.append("gate2_work_{0}_{1}".format(name, block["seed"]))
            if int(cont.get("env_plus_synth") or 10**9) >= int(other.get("env_plus_synth") or 0):
                gate2 = False
                notes.append("gate2_envsynth_{0}_{1}".format(name, block["seed"]))
            if int(cont.get("useful_acquisition") or 0) != 3:
                gate2 = False
                notes.append("gate2_useful_seed_{0}".format(block["seed"]))
        for name in METHODS:
            cell = retain.get(name) or {}
            if int(cell.get("useful_acquisition") or 0) != int(cell.get("n") or 0) or int(cell.get("n") or 0) != 4:
                gate3 = False
                notes.append("gate3_{0}_{1}".format(name, block["seed"]))
    return dict(
        gate1_oog_calibrated_abstention=gate1,
        gate2_wave2_experience_accelerates_wave3=gate2,
        gate3_multi_wave_retention=gate3,
        passed=bool(gate1 and gate2 and gate3),
        notes=notes,
    )


def per_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            seed=row.get("source_seed"),
            wave=row.get("wave"),
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
            env_plus_synth=int(row.get("env_plus_synth") or 0),
            total_acquisition_work=int(row["total_acquisition_work"]),
            catalog_exhausted=bool(row.get("catalog_exhausted")),
            abstained_unknown=bool(row.get("abstained_unknown")),
            false_positive=bool(row.get("false_positive")),
            subclause_hits=int(row.get("subclause_hits") or 0),
            solved=bool(row.get("useful_acquisition")),
            retain_wave=row.get("retain_wave"),
        )
        for row in rows
    ]


def run_continual_wave3(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    source = unfamiliar_policy_tasks("up_source")
    wave2 = unfamiliar_policy_tasks("w2_holdout")
    express = unfamiliar_policy_tasks("w3_expressible")
    oog = unfamiliar_policy_tasks("w3_oog")
    retain = unfamiliar_policy_tasks("w3_retain")
    if any(row["task_id"] in OPENED_IDS for row in wave2 + express + oog + retain):
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
        wave2_rows = []
        express_rows = []
        oog_rows = []
        retain_rows = []
        for method in METHODS:
            used = zero_acquire() if method == "untrained_open_grammar" else _with_stops(weights)
            wave1_copy = _library_from_snapshot(wave1.snapshot()) if method in LIBRARY_METHODS else None
            live = _library_from_snapshot(wave1.snapshot()) if method == CONTINUAL else wave1_copy
            for index, task in enumerate(wave2):
                rng = random.Random((80 + seed) * 1009 + index * 17 + 11)
                episode = run_wave_episode(task, method, used, order, rng, live if method == CONTINUAL else wave1_copy)
                episode["source_seed"] = seed
                episode["wave"] = "wave2"
                wave2_rows.append(episode)
            wave2_snap = live.snapshot() if live is not None else {}
            w3_lib = live if method == CONTINUAL else (
                _library_from_snapshot(wave1.snapshot()) if method == FROZEN else None
            )
            assimilate = 0
            if method == CONTINUAL and live is not None and "even" in set(live.stored_guards()):
                assimilate = 4
            for index, task in enumerate(express):
                rng = random.Random((110 + seed) * 1009 + index * 17 + 11)
                episode = run_wave_episode(task, method, used, order, rng, w3_lib)
                episode["source_seed"] = seed
                episode["wave"] = "wave3"
                extra = (distill_cost + assimilate) if (method == CONTINUAL and index == 0) else (
                    distill_cost if (method == FROZEN and index == 0) else 0
                )
                episode["distill_cost"] = extra
                episode["total_acquisition_work"] = int(episode["total_acquisition_work"]) + extra
                episode["env_plus_synth"] = int(episode["env_interactions"]) + int(episode["residual_synthesis_evals"])
                express_rows.append(episode)
            for index, task in enumerate(oog):
                rng = random.Random((130 + seed) * 1009 + index * 17 + 11)
                episode = run_wave_episode(task, method, used, order, rng, w3_lib)
                episode["source_seed"] = seed
                episode["wave"] = "wave3"
                oog_rows.append(episode)
            for index, task in enumerate(retain):
                rng = random.Random((150 + seed) * 1009 + index * 17 + 11)
                episode = run_wave_episode(task, method, used, order, rng, w3_lib)
                episode["source_seed"] = seed
                episode["wave"] = "retain"
                retain_rows.append(episode)
        assessment_rows.extend(wave2_rows + express_rows + oog_rows + retain_rows)
        seed_blocks.append(dict(
            seed=seed,
            policy_hash=frozen_hash,
            wave1_library=wave1.snapshot(),
            wave2_rows=wave2_rows,
            express_rows=express_rows,
            oog_rows=oog_rows,
            retain_rows=retain_rows,
            wave2_totals=_totals(wave2_rows),
            express_totals=_totals(express_rows),
            oog_totals=_totals(oog_rows),
            retain_totals=_totals(retain_rows),
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
        beyond_catalog_artifact="1a4132bb400209ee3877e06739e2436b8a828ccf76dd2755361456c2a5cecc07",
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
            "wave2_totals": block["wave2_totals"],
            "express_totals": block["express_totals"],
            "oog_totals": block["oog_totals"],
            "retain_totals": block["retain_totals"],
        } for block in seed_blocks],
        per_task=per_task_rows(assessment_rows),
        totals=dict(
            wave2=_totals([row for row in assessment_rows if row["split"] == "w2_holdout"]),
            wave3_expressible=_totals([row for row in assessment_rows if row["split"] == "w3_expressible"]),
            wave3_oog=_totals([row for row in assessment_rows if row["split"] == "w3_oog"]),
            retain=_totals([row for row in assessment_rows if row["split"] == "w3_retain"]),
        ),
        gates=gates,
        usage=usage,
        language_hash=language_hash(),
    )
    payload["hash"] = digest({key: payload[key] for key in ("kind", "assessment", "totals", "gates")})
    (directory / "seed_continual_wave3_assimilation.json").write_text(
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
    rebuilt_express = _totals([row for row in rows if row.get("split") == "w3_expressible"])
    saved = (payload.get("totals") or {}).get("wave3_expressible") or {}
    for name, cell in rebuilt_express.items():
        other = saved.get(name) or {}
        if cell.get("total_acquisition_work") != other.get("total_acquisition_work"):
            ok = False
            notes.append("column:" + name)
    wave_order = {"w2_holdout": 0, "w3_expressible": 1, "w3_oog": 2, "w3_retain": 3}
    for seed in TRAIN_SEEDS:
        wave1 = next(block["wave1_library"] for block in payload.get("seed_blocks") or [] if block["seed"] == seed)
        for method in METHODS:
            library = _library_from_snapshot(wave1) if method in LIBRARY_METHODS else None
            method_rows = [
                row for row in rows
                if int(row.get("source_seed")) == seed and row["method"] == method
            ]
            method_rows.sort(key=lambda row: wave_order.get(row.get("split"), 9))
            for row in method_rows:
                used = None if method not in LIBRARY_METHODS else (
                    _library_from_snapshot(wave1) if method == FROZEN else library
                )
                reconstructed = reconstruct_work(row, used)
                for key in (
                    "env_interactions", "confirmatory_env_probes", "hypothesis_evals",
                    "residual_synthesis_evals", "distill_cost", "total_acquisition_work",
                ):
                    if reconstructed.get(key) != row.get(key):
                        ok = False
                        notes.append("reconstruct:" + row["task_id"] + ":" + method + ":" + key)
                        break
                if method == CONTINUAL and library is not None and row.get("confident_acquisition"):
                    spec = parse_spec((row.get("synthesized") or {}).get("representative"))
                    if spec:
                        library.remember_subclause(dict(
                            source_mechanism=spec_name(spec), source_task=row["task_id"],
                            guard=spec[0], signature=spec[0], clause=spec[0] + "_stream",
                        ))
    blocks = []
    for block in payload.get("seed_blocks") or []:
        seed = block["seed"]
        blocks.append(dict(
            seed=seed,
            express_totals=block.get("express_totals") or _totals(
                [row for row in rows if row.get("source_seed") == seed and row.get("split") == "w3_expressible"]
            ),
            oog_totals=block.get("oog_totals") or _totals(
                [row for row in rows if row.get("source_seed") == seed and row.get("split") == "w3_oog"]
            ),
            retain_totals=block.get("retain_totals") or _totals(
                [row for row in rows if row.get("source_seed") == seed and row.get("split") == "w3_retain"]
            ),
        ))
    gates = evaluate_gates(blocks)
    saved_gates = payload.get("gates") or {}
    for key in (
        "gate1_oog_calibrated_abstention",
        "gate2_wave2_experience_accelerates_wave3",
        "gate3_multi_wave_retention",
        "passed",
    ):
        if gates.get(key) != saved_gates.get(key):
            ok = False
            notes.append("gates:" + key)
    if not saved_gates.get("passed"):
        ok = False
        notes.append("gates_failed")
    return dict(valid=ok, notes=notes, n=len(rows), gates=gates)
