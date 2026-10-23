"""Step-wise residual invariant search on the locked v3_headroom grammar.

Reuses apply_v3 / execute_v3 / support_io_invariant / EventMeter.
Does not edit apply_primitive_op or local_model_runtime. No neural calls.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .capability_evidence import EventMeter, digest
from .v3_headroom import (
    ALL_SPECS, CALL_BUDGET, CLUSTER_IDS, SIGNATURE_CLASS, SPECIALIST_PROBES,
    apply_v3, automatic_signature, execute_v3, names, support_io_invariant,
)
from .v3_headroom_transfer import (
    CONTROLLER, build_b_task, freeze_phi, method_order, pair, phi_hash,
    register_signatures, run_episode, train_set_a,
)


FLAT_METHODS = (
    "untrained_default",
    "simple_frequency_interleaved",
    "invariant_phi_frozen",
)
METHODS = FLAT_METHODS + ("stepwise_residual_phi_frozen",)
MAX_DEPTH = 4
BEAM_WIDTH = 3
OPS_PER_STEP = 3
RESIDUAL_CLUSTER = {
    "length_contracting": "filter",
    "residue_or_map": "mod",
    "order_changed": "order",
    "structure_changed": "group",
}


def residual_io_invariant(x_t: list[int], y_final: list[int]) -> str:
    return support_io_invariant([(list(x_t), list(y_final))])


def _payload(xs: list[int]) -> list[int]:
    return list(xs[1:]) if xs else []


def _filter_profile(inp: list[int], out: list[int]) -> str:
    if out and out == inp[: len(out)] and len(out) < len(inp):
        return "positional_slice"
    if out and out == inp[-len(out) :] and len(out) < len(inp):
        return "positional_slice"
    if out and all(x > 0 for x in out) and all((x > 0) == (x in out) for x in inp):
        return "sign_select"
    if out and all(x < 0 for x in out) and all((x < 0) == (x in out) for x in inp):
        return "sign_select"
    if out and all(x % 2 == 0 for x in out) and all((x % 2 == 0) == (x in out) for x in inp):
        return "parity_select"
    if out and all(x % 2 != 0 for x in out) and all((x % 2 != 0) == (x in out) for x in inp):
        return "parity_select"
    return "select_other"


def _mod_profile(inp: list[int], out: list[int]) -> str:
    if len(inp) != len(out):
        return "len_mismatch"
    for modulus in range(2, 13):
        if all(o == (i % modulus) for i, o in zip(inp, out)):
            return "pure_residue"
    for modulus in range(2, 13):
        for addend in range(1, modulus):
            if all(o == ((i + addend) % modulus) for i, o in zip(inp, out)):
                return "add_residue"
    for modulus in range(2, 13):
        for factor in range(2, modulus):
            if all(o == ((i * factor) % modulus) for i, o in zip(inp, out)):
                return "mul_residue"
    return "residue_other"


def _order_profile(inp: list[int], out: list[int]) -> str:
    if out == list(reversed(inp)):
        return "reverse"
    if out == inp[1:] + inp[:1] or out == inp[-1:] + inp[:-1]:
        return "rotate"
    if out == sorted(inp) or out == sorted(inp, reverse=True):
        return "sort"
    return "permute_other"


def _group_profile(inp: list[int], out: list[int]) -> str:
    if out and all(x >= 0 for x in out) and sum(out) == len(inp):
        return "count_bins"
    if out and all(x in inp for x in out) and len(out) <= 3:
        return "rep_per_key"
    return "sum_bins"


def operator_probe_signature(op: str) -> str:
    """Fine-grained specialist-probe profile. Never an operator name."""
    cls = automatic_signature(op)
    if cls in ALL_SPECS:
        raise ValueError("probe_signature_is_operator_name:" + cls)
    spec = ALL_SPECS[op]
    probe = SPECIALIST_PROBES[spec.cluster]
    out = apply_v3(op, probe)
    inp_p, out_p = _payload(probe), _payload(out)
    if cls == SIGNATURE_CLASS["filter"]:
        profile = _filter_profile(inp_p, out_p)
    elif cls == SIGNATURE_CLASS["mod"]:
        profile = _mod_profile(inp_p, out_p)
    elif cls == SIGNATURE_CLASS["order"]:
        profile = _order_profile(inp_p, out_p)
    elif cls == SIGNATURE_CLASS["group"]:
        profile = _group_profile(inp_p, out_p)
    else:
        profile = "unknown"
    sig = f"{cls}:{profile}"
    if sig in ALL_SPECS or profile in ALL_SPECS:
        raise ValueError("probe_signature_is_operator_name:" + sig)
    return sig


def residual_phi_key(residual: str, signature: str) -> tuple[str, str]:
    if signature in ALL_SPECS:
        raise ValueError("phi_step_key_must_not_be_operator_name:" + signature)
    return (residual, signature)


def train_phi_step(config: dict) -> dict:
    weights: dict[tuple[str, str], float] = {}
    train_calls = 0
    for spec in config["set_a_tasks"]:
        target = tuple(spec["target"])
        x, y = pair(spec["cluster"], target, config["support_payloads"][spec["cluster"]])
        for op in target:
            residual = residual_io_invariant(x, y)
            key = residual_phi_key(residual, operator_probe_signature(op))
            weights[key] = weights.get(key, 0.0) + 1.0
            train_calls += 1
            x = apply_v3(op, x)
    frozen = freeze_phi(weights)
    return dict(phi_step=weights, train_calls=train_calls, frozen=frozen)


class StepwiseResidualInvestigator:
    """Bounded beam over single-step residuals. φ_step is frozen before Set B."""

    def __init__(
        self,
        phi_step: dict[tuple[str, str], float],
        meter: EventMeter,
        *,
        set_id: str = "B",
        beam_width: int = BEAM_WIDTH,
        ops_per_step: int = OPS_PER_STEP,
        max_depth: int = MAX_DEPTH,
        budget: int = CALL_BUDGET,
    ):
        self.phi_step = phi_step
        self.meter = meter
        self.set_id = set_id
        self.beam_width = beam_width
        self.ops_per_step = ops_per_step
        self.max_depth = max_depth
        self.budget = budget
        self.ops = names(set_id)

    def step_score(self, op: str, residual: str) -> float:
        return float(self.phi_step.get(residual_phi_key(residual, operator_probe_signature(op)), 0.0))

    def rank_ops(self, residual: str) -> list[str]:
        cluster = RESIDUAL_CLUSTER.get(residual)
        pool = [op for op in self.ops if cluster is None or ALL_SPECS[op].cluster == cluster]
        if not pool:
            pool = list(self.ops)
        return sorted(pool, key=lambda op: (-self.step_score(op, residual), self.ops.index(op)))

    def _invoke(
        self, scope: str, identity: str, phase: str, prog: tuple[str, ...], inp: list[int], log: list[dict],
    ) -> list[int] | None:
        if len(log) >= self.budget:
            return None
        out = self.meter.call(
            scope, "candidate", identity,
            lambda payload: execute_v3(tuple(payload["program"]), payload["input"]),
            dict(program=list(prog), input=list(inp), phase=phase),
        )
        if isinstance(out, str) and out.startswith("ERR:"):
            return None
        log.append(dict(phase=phase, program=list(prog), input=list(inp), output=list(out)))
        return list(out)

    def run(self, task: dict, scope: str) -> dict:
        support_in, support_out = task["support"]
        log: list[dict[str, Any]] = []
        beam: list[tuple[tuple[str, ...], list[int]]] = [((), list(support_in))]
        survivors: list[tuple[str, ...]] = []
        first_match: int | None = None
        pruned = 0

        for depth in range(1, self.max_depth + 1):
            if len(log) >= self.budget or len(survivors) >= int(CONTROLLER["shortlist_limit"]):
                break
            seen: dict[tuple[int, ...], tuple[str, ...]] = {}
            expansions: list[tuple[tuple[str, ...], list[int]]] = []
            for prefix, state in beam:
                residual = residual_io_invariant(state, support_out)
                for op in self.rank_ops(residual)[: self.ops_per_step]:
                    nxt = self._invoke(
                        scope, f"{task['id']}:step:{len(log)}", "step_expand",
                        (op,), state, log,
                    )
                    if nxt is None:
                        break
                    key = tuple(nxt)
                    if key in seen:
                        pruned += 1
                        continue
                    seen[key] = prefix + (op,)
                    prog = prefix + (op,)
                    expansions.append((prog, nxt))
                    if nxt == support_out:
                        survivors.append(prog)
                        if first_match is None:
                            first_match = len(log)
                if len(log) >= self.budget:
                    break
            expansions.sort(
                key=lambda item: (
                    item[1] != support_out,
                    abs(len(item[1]) - len(support_out)),
                    -sum(self.step_score(op, residual_io_invariant(item[1], support_out)) for op in item[0][-1:]),
                    item[0],
                )
            )
            beam = [
                item for item in expansions
                if item[1] != support_out
            ][: self.beam_width]
            if not beam:
                break

        questions = 0
        if (
            CONTROLLER["allow_questions"]
            and len(survivors) > 1
            and questions < int(CONTROLLER["max_questions_per_task"])
        ):
            probe = SPECIALIST_PROBES[task["cluster"]]
            oracle = execute_v3(tuple(task["target"]), probe)
            kept: list[tuple[str, ...]] = []
            for prog in survivors:
                out = self._invoke(
                    scope, f"{task['id']}:probe:{len(log)}", "probe_construction",
                    prog, probe, log,
                )
                if out is None:
                    break
                if out == oracle:
                    kept.append(prog)
            if kept:
                survivors = kept
            questions += 1

        selected = survivors[0] if survivors else None
        assess_in, assess_out = task["assessment"]
        solved = bool(selected is not None and execute_v3(selected, assess_in) == assess_out)
        return dict(
            method="stepwise_residual_phi_frozen",
            task_id=task["id"],
            cluster=task["cluster"],
            depth=task["depth"],
            n_candidate_calls=len(log),
            support_check_calls=sum(1 for row in log if row["phase"] == "step_expand"),
            probe_construction_calls=sum(1 for row in log if row["phase"] == "probe_construction"),
            questions=questions,
            selected=list(selected) if selected else None,
            solved=solved,
            hit_budget=len(log) >= self.budget and not solved,
            untruncated_calls=first_match,
            observational_pruned=pruned,
            calls=log,
            controller=CONTROLLER,
            search="stepwise_residual",
        )


def begin(config: dict, emit) -> dict:
    if set(config["methods"]) != set(METHODS):
        raise ValueError("methods_unlocked")
    if config["controller"] != CONTROLLER:
        raise ValueError("controller_not_equalized")
    if int(config["call_budget"]) != CALL_BUDGET:
        raise ValueError("budget_unlocked")
    sig_a = register_signatures(names("A"))
    sig_b = register_signatures(names("B"))
    if set(sig_a) & set(sig_b):
        raise ValueError("set_a_b_name_overlap")
    trained_flat = train_set_a(config, sig_a)
    trained_step = train_phi_step(config)
    if any(op in str(key) for key in trained_step["phi_step"] for op in names("B")):
        raise ValueError("phi_step_contains_set_b_name")
    emit(dict(
        kind="audit_manifest",
        config_hash=digest(config),
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        live_neural_calls=0,
        freeze_weights=True,
        signatures_a=sig_a,
        signatures_b=sig_b,
        signatures_from="specialist_probes_only",
        controller=CONTROLLER,
        hypothesis_count=22464,
        phi_hash=trained_flat["frozen"]["hash"],
        phi_step_hash=trained_step["frozen"]["hash"],
        name_weights=trained_flat["name_weights"],
        train_calls=trained_flat["train_calls"] + trained_step["train_calls"],
        search=dict(beam_width=BEAM_WIDTH, ops_per_step=OPS_PER_STEP, max_depth=MAX_DEPTH),
        gemini="NOT_RUN",
    ))
    return dict(
        trained_flat=trained_flat,
        trained_step=trained_step,
        signatures_a=sig_a,
        signatures_b=sig_b,
    )


def record_set_b(config: dict, emit, state: dict) -> list[dict]:
    flat = state["trained_flat"]
    step = state["trained_step"]
    frozen_flat = flat["frozen"]["hash"]
    frozen_step = step["frozen"]["hash"]
    rows = []
    for spec in config["set_b_tasks"]:
        task = build_b_task(spec, config)
        invariant = support_io_invariant([task["support"]])
        emit(dict(
            kind="task_lock", category="lock", id=task["id"],
            cluster=task["cluster"], depth=task["depth"],
            invariant=invariant, target=task["target"],
        ))
        for method in FLAT_METHODS:
            if phi_hash(flat["phi"]) != frozen_flat:
                raise ValueError("phi_mutated_during_set_b")
            order = method_order(method, invariant, flat, state["signatures_b"])
            episode = run_episode(method, task, order, CONTROLLER)
            episode["kind"] = "capability"
            episode["category"] = "set_b"
            episode["invariant"] = invariant
            episode["phi_hash_after"] = phi_hash(flat["phi"])
            episode["phi_step_hash_after"] = frozen_step
            episode["search"] = "flat"
            emit(episode)
            rows.append(episode)
        if digest({f"{k[0]}|{k[1]}": float(v) for k, v in sorted(step["phi_step"].items())}) != frozen_step:
            raise ValueError("phi_step_mutated_during_set_b")
        events: list[dict] = []
        meter = EventMeter(events.append)
        investigator = StepwiseResidualInvestigator(step["phi_step"], meter)
        episode = investigator.run(task, f"set_b:{task['id']}")
        episode["kind"] = "capability"
        episode["category"] = "set_b"
        episode["invariant"] = invariant
        episode["phi_hash_after"] = frozen_flat
        episode["phi_step_hash_after"] = digest(
            {f"{k[0]}|{k[1]}": float(v) for k, v in sorted(step["phi_step"].items())}
        )
        episode["metered_candidate_events"] = len(events)
        emit(episode)
        rows.append(episode)
    return rows


def _mean(rows: list[dict], key: str) -> float:
    return sum(row[key] for row in rows) / len(rows) if rows else 0.0


def _rate(rows: list[dict]) -> float:
    return sum(1 for row in rows if row["solved"]) / len(rows) if rows else 0.0


def summarize(records: list[dict], config: dict) -> dict:
    b_rows = [row for row in records if row.get("category") == "set_b"]
    by_method = {method: [row for row in b_rows if row["method"] == method] for method in METHODS}

    def depth_rate(method: str, depth: int) -> float:
        return _rate([row for row in by_method[method] if row["depth"] == depth])

    stepwise_mean = _mean(by_method["stepwise_residual_phi_frozen"], "n_candidate_calls")
    untrained_mean = _mean(by_method["untrained_default"], "n_candidate_calls")
    phi_mean = _mean(by_method["invariant_phi_frozen"], "n_candidate_calls")
    stepwise_rate = _rate(by_method["stepwise_residual_phi_frozen"])
    untrained_rate = _rate(by_method["untrained_default"])
    phi_rate = _rate(by_method["invariant_phi_frozen"])
    freq_rate = _rate(by_method["simple_frequency_interleaved"])
    both_capped = all(
        row["n_candidate_calls"] == CALL_BUDGET
        for row in by_method["untrained_default"] + by_method["stepwise_residual_phi_frozen"]
    )
    gate2 = (
        stepwise_mean <= 0.5 * untrained_mean
        and stepwise_rate > untrained_rate
        and stepwise_rate > phi_rate
    )
    return dict(
        default_investigation_policy="fixed_boundary",
        learned_ranking_promoted=False,
        learning_research_resumed=False,
        live_neural_calls=0,
        methods={
            method: dict(
                solved=sum(1 for row in by_method[method] if row["solved"]),
                n=len(by_method[method]),
                solve_rate=_rate(by_method[method]),
                mean_calls=_mean(by_method[method], "n_candidate_calls"),
                mean_support=_mean(by_method[method], "support_check_calls"),
                mean_probe=_mean(by_method[method], "probe_construction_calls"),
                hit_budget=sum(1 for row in by_method[method] if row.get("hit_budget")),
                depth3=depth_rate(method, 3),
                depth4=depth_rate(method, 4),
            )
            for method in METHODS
        },
        gate2_primary_transfer=gate2,
        gate2_stepwise_mean=stepwise_mean,
        gate2_untrained_mean=untrained_mean,
        gate2_phi_mean=phi_mean,
        gate2_half_untrained=0.5 * untrained_mean,
        gate2_stepwise_rate=stepwise_rate,
        gate2_untrained_rate=untrained_rate,
        gate2_phi_rate=phi_rate,
        gate2_frequency_rate=freq_rate,
        gate2_both_capped_at_35=both_capped,
        gate3_depth3={method: depth_rate(method, 3) for method in METHODS},
        gate3_depth4={method: depth_rate(method, 4) for method in METHODS},
        investigation_transfer_established=bool(gate2),
        open_domain_coding_excluded=True,
        conversation_capability_excluded=True,
        learning_to_learn_established=False,
        verdict="INVESTIGATION_TRANSFER_ON_V3_STEPWISE" if gate2 else "TRANSFER_GATE_FAILED",
    )
