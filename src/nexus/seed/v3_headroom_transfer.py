"""Set A → Set B transfer and depth 3–4 ablation on v3_headroom.

Reuses v3_headroom operators, automatic signatures, EventMeter digest.
Does not edit apply_primitive_op or local_model_runtime. No neural calls.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .capability_evidence import digest
from .v3_headroom import (
    CALL_BUDGET, CLUSTER_IDS, CLUSTER_TAG, SPECIALIST_PROBES,
    automatic_signature, conditioned_order, execute_v3, hypothesis_space,
    interleaved_catalogue, names, phi_key, score_program, support_io_invariant,
)


METHODS = (
    "untrained_default",
    "simple_frequency_interleaved",
    "name_indexed_ranker",
    "invariant_phi_frozen",
    "higher_order_skeletons_only",
    "combined_invariant_phi_plus_skeletons",
)
CONTROLLER = dict(
    shortlist_limit=8,
    allow_questions=True,
    max_questions_per_task=2,
    max_episode_candidate_calls=CALL_BUDGET,
    enable_widening=True,
    widen_stop="same_call_and_question_ceiling",
)


def tagged(cluster: str, payload: list[int]) -> list[int]:
    return [CLUSTER_TAG[cluster]] + list(payload)


def pair(cluster: str, target: tuple[str, ...], payload: list[int]) -> tuple[list[int], list[int]]:
    inp = tagged(cluster, payload)
    return inp, execute_v3(target, inp)


def register_signatures(ops: tuple[str, ...]) -> dict[str, str]:
    """Set B (and A) signatures from the four specialist probes only."""
    return {op: automatic_signature(op) for op in ops}


def freeze_phi(weights: dict[tuple[str, str], float]) -> dict:
    frozen = {f"{k[0]}|{k[1]}": float(v) for k, v in sorted(weights.items())}
    return dict(weights=deepcopy(weights), hash=digest(frozen), freeze_weights=True)


def phi_hash(weights: dict[tuple[str, str], float]) -> str:
    return digest({f"{k[0]}|{k[1]}": float(v) for k, v in sorted(weights.items())})


def extract_skeletons(targets: list[tuple[str, ...]], signatures: dict[str, str]) -> list[tuple[str, ...]]:
    templates: list[tuple[str, ...]] = []
    for target in targets:
        sigs = tuple(signatures[op] for op in target)
        templates.append(sigs)
        for left, right in zip(sigs, sigs[1:]):
            templates.append((left, right))
    # Unique, keep longer first in storage; runnable pool uses length 3–4 only.
    return sorted(set(templates), key=lambda row: (len(row), row))


def skeleton_pool(templates: list[tuple[str, ...]], signatures: dict[str, str]) -> list[tuple[str, ...]]:
    by_sig: dict[str, list[str]] = defaultdict(list)
    for op, sig in signatures.items():
        by_sig[sig].append(op)
    for sig in by_sig:
        by_sig[sig].sort()
    pool: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    runnable = [tmpl for tmpl in templates if len(tmpl) in (3, 4) and all(s in by_sig for s in tmpl)]
    for tmpl in sorted(runnable, key=len):
        for prog in _product(by_sig, tmpl):
            if prog not in seen:
                seen.add(prog)
                pool.append(prog)
    return pool


def _product(by_sig: dict[str, list[str]], tmpl: tuple[str, ...]):
    import itertools
    return itertools.product(*[by_sig[sig] for sig in tmpl])


def train_set_a(config: dict, signatures_a: dict[str, str]) -> dict:
    weights: dict[tuple[str, str], float] = {}
    name_weights: dict[str, float] = defaultdict(float)
    train_calls = 0
    targets = []
    for spec in config["set_a_tasks"]:
        target = tuple(spec["target"])
        targets.append(target)
        cluster = spec["cluster"]
        support = pair(cluster, target, config["support_payloads"][cluster])
        invariant = support_io_invariant([support])
        for op in names("A"):
            from .v3_headroom import apply_v3
            # Metered as a single-op support screen, not a Set B call.
            train_calls += 1
            _ = apply_v3(op, support[0])
        for op in target:
            key = phi_key(invariant, signatures_a[op])
            weights[key] = weights.get(key, 0.0) + 1.0
            name_weights[op] += 1.0
    skeletons = extract_skeletons(targets, signatures_a)
    return dict(
        phi=weights,
        name_weights=dict(name_weights),
        skeletons=skeletons,
        train_calls=train_calls,
        frozen=freeze_phi(weights),
    )


def method_order(
    method: str,
    invariant: str,
    trained: dict,
    signatures_b: dict[str, str],
) -> list[tuple[str, ...]]:
    raw = hypothesis_space("B")
    if method == "untrained_default":
        return raw
    if method == "simple_frequency_interleaved":
        return interleaved_catalogue("B")
    if method == "name_indexed_ranker":
        name_w = trained["name_weights"]
        return [
            prog for _, prog in sorted(
                enumerate(raw),
                key=lambda item: (-sum(name_w.get(op, 0.0) for op in item[1]), item[0]),
            )
        ]
    if method == "invariant_phi_frozen":
        return conditioned_order("B", invariant, trained["phi"])
    pool = skeleton_pool(trained["skeletons"], signatures_b)
    if method == "higher_order_skeletons_only":
        return pool
    return sorted(pool, key=lambda prog: (-score_program(prog, invariant, trained["phi"]), prog))


def untruncated_calls(order: list[tuple[str, ...]], support: tuple[list[int], list[int]]) -> int | None:
    for index, prog in enumerate(order, 1):
        if execute_v3(prog, support[0]) == support[1]:
            return index
    return None


def run_episode(method: str, task: dict, order: list[tuple[str, ...]], ctrl: dict) -> dict:
    budget = int(ctrl["max_episode_candidate_calls"])
    shortlist = int(ctrl["shortlist_limit"])
    allow_q = bool(ctrl["allow_questions"])
    max_q = int(ctrl["max_questions_per_task"])
    support = task["support"]
    probe = SPECIALIST_PROBES[task["cluster"]]
    log: list[dict[str, Any]] = []

    def invoke(phase: str, prog: tuple[str, ...], inp: list[int]) -> list[int] | None:
        if len(log) >= budget:
            return None
        out = execute_v3(prog, inp)
        log.append(dict(phase=phase, program=list(prog), input=list(inp), output=list(out)))
        return out

    survivors: list[tuple[str, ...]] = []
    for prog in order:
        if len(log) >= budget or len(survivors) >= shortlist:
            break
        out = invoke("support_check", prog, support[0])
        if out is None:
            break
        if out == support[1]:
            survivors.append(prog)
    questions = 0
    if allow_q and len(survivors) > 1 and questions < max_q:
        oracle = execute_v3(tuple(task["target"]), probe)
        kept: list[tuple[str, ...]] = []
        for prog in survivors:
            out = invoke("probe_construction", prog, probe)
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
    support_n = sum(1 for row in log if row["phase"] == "support_check")
    probe_n = sum(1 for row in log if row["phase"] == "probe_construction")
    return dict(
        method=method,
        task_id=task["id"],
        cluster=task["cluster"],
        depth=task["depth"],
        n_candidate_calls=len(log),
        support_check_calls=support_n,
        probe_construction_calls=probe_n,
        questions=questions,
        selected=list(selected) if selected else None,
        solved=solved,
        hit_budget=len(log) >= budget and not solved,
        untruncated_calls=untruncated_calls(order, support),
        calls=log,
        controller=ctrl,
        phi_hash_after=task.get("phi_hash"),
    )


def build_b_task(spec: dict, config: dict) -> dict:
    target = tuple(spec["target"])
    cluster = spec["cluster"]
    return dict(
        id=spec["id"],
        cluster=cluster,
        depth=spec["depth"],
        target=list(target),
        support=pair(cluster, target, config["support_payloads"][cluster]),
        assessment=pair(cluster, target, config["assessment_payloads"][cluster]),
    )


def begin(config: dict, emit) -> dict:
    if set(config["methods"]) != set(METHODS):
        raise ValueError("methods_unlocked")
    if config["controller"] != CONTROLLER:
        raise ValueError("controller_not_equalized")
    sig_a = register_signatures(names("A"))
    sig_b = register_signatures(names("B"))
    if set(sig_a) & set(sig_b):
        raise ValueError("set_a_b_name_overlap")
    if set(sig_a.values()) != set(sig_b.values()):
        raise ValueError("automatic_signatures_do_not_align")
    trained = train_set_a(config, sig_a)
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
        phi_hash=trained["frozen"]["hash"],
        name_weights=trained["name_weights"],
        skeletons=[list(row) for row in trained["skeletons"]],
        train_calls=trained["train_calls"],
        gemini="NOT_RUN",
    ))
    return dict(trained=trained, signatures_a=sig_a, signatures_b=sig_b)


def record_set_b(config: dict, emit, state: dict) -> list[dict]:
    trained = state["trained"]
    frozen_hash = trained["frozen"]["hash"]
    rows = []
    for spec in config["set_b_tasks"]:
        task = build_b_task(spec, config)
        task["phi_hash"] = frozen_hash
        invariant = support_io_invariant([task["support"]])
        emit(dict(kind="task_lock", category="lock", id=task["id"], cluster=task["cluster"],
                  depth=task["depth"], invariant=invariant, target=task["target"]))
        for method in METHODS:
            if phi_hash(trained["phi"]) != frozen_hash:
                raise ValueError("phi_mutated_during_set_b")
            order = method_order(method, invariant, trained, state["signatures_b"])
            episode = run_episode(method, task, order, CONTROLLER)
            episode["kind"] = "capability"
            episode["category"] = "set_b"
            episode["invariant"] = invariant
            episode["phi_hash_after"] = phi_hash(trained["phi"])
            episode["name_index_scores"] = [
                sum(trained["name_weights"].get(op, 0.0) for op in tuple(spec["target"]))
            ]
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
    cluster_support = {}
    cluster_probe = {}
    for method in ("invariant_phi_frozen", "simple_frequency_interleaved"):
        cluster_support[method] = {c: 0 for c in CLUSTER_IDS}
        cluster_probe[method] = {c: 0 for c in CLUSTER_IDS}
        for row in by_method[method]:
            cluster_support[method][row["cluster"]] += row["support_check_calls"]
            cluster_probe[method][row["cluster"]] += row["probe_construction_calls"]
    gate1 = all(
        cluster_support["invariant_phi_frozen"][c] < cluster_support["simple_frequency_interleaved"][c]
        and cluster_probe["invariant_phi_frozen"][c] < cluster_probe["simple_frequency_interleaved"][c]
        for c in CLUSTER_IDS
    )
    phi_mean = _mean(by_method["invariant_phi_frozen"], "n_candidate_calls")
    untrained_mean = _mean(by_method["untrained_default"], "n_candidate_calls")
    phi_rate = _rate(by_method["invariant_phi_frozen"])
    untrained_rate = _rate(by_method["untrained_default"])
    name_rate = _rate(by_method["name_indexed_ranker"])
    both_capped = all(row["n_candidate_calls"] == CALL_BUDGET for row in by_method["untrained_default"] + by_method["invariant_phi_frozen"])
    gate2 = (
        phi_mean <= 0.5 * untrained_mean
        and phi_rate > untrained_rate
        and phi_rate > name_rate
    )
    def depth_rate(method, depth):
        rows = [row for row in by_method[method] if row["depth"] == depth]
        return _rate(rows)

    depth3 = {
        "invariant_phi_frozen": depth_rate("invariant_phi_frozen", 3),
        "combined_invariant_phi_plus_skeletons": depth_rate("combined_invariant_phi_plus_skeletons", 3),
    }
    depth4 = {
        "invariant_phi_frozen": depth_rate("invariant_phi_frozen", 4),
        "combined_invariant_phi_plus_skeletons": depth_rate("combined_invariant_phi_plus_skeletons", 4),
    }
    manifest = next((row for row in records if row.get("kind") == "audit_manifest"), {})
    name_weights = manifest.get("name_weights") or {}
    name_zero = all(op not in name_weights or name_weights[op] == 0 for op in names("B"))
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
                mean_untruncated=_mean(
                    [row for row in by_method[method] if row.get("untruncated_calls") is not None],
                    "untruncated_calls",
                ),
                hit_budget=sum(1 for row in by_method[method] if row.get("hit_budget")),
            )
            for method in METHODS
        },
        cluster_support=cluster_support,
        cluster_probe=cluster_probe,
        gate1_specialist_separation=gate1,
        gate2_primary_transfer=gate2,
        gate2_phi_mean=phi_mean,
        gate2_untrained_mean=untrained_mean,
        gate2_half_untrained=0.5 * untrained_mean,
        gate2_phi_rate=phi_rate,
        gate2_untrained_rate=untrained_rate,
        gate2_name_rate=name_rate,
        gate2_both_capped_at_35=both_capped,
        gate3_depth3=depth3,
        gate3_depth4=depth4,
        name_indexed_zero_on_set_b=name_zero,
        investigation_transfer_established=bool(gate2),
        open_domain_coding_excluded=True,
        conversation_capability_excluded=True,
        learning_to_learn_established=False,
        verdict="INVESTIGATION_TRANSFER_ON_V3_HEADROOM" if gate2 else "TRANSFER_GATE_FAILED",
    )
