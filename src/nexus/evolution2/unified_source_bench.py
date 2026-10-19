"""Inspected-source development only; FakeStepModel labels are not returns.

Reuses catalogue planners, the existing proposer/memory, ridge fitting,
TrustedEvaluator and ReservationLedger. Nothing dispatches real environments.
"""
import copy
from dataclasses import asdict
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import time

import numpy as np

from nexus.core.strategy_memory_decide_bench import _task, family_context, support_from_source, obs_from_source
from nexus.evolution1.catalogue import digest, plan_bound, Rule
from nexus.evolution1.fixtures import Journal
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work, model_work
from nexus.evolution1.toy_loop import ANCHORS, VARIANTS, AdaptiveProposer, TrainingFeedback
from nexus.evolution2.generated_strategies import (
    StrategyGenerator, AdvantagePredictor, universe, leaf, execute, advantage_features,
)
from nexus.evolution2.observation_memory import FamilyNormalizer, load_source_train_obs, ObservationAwareAdaptive, SourceCalibration
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.planner_adapter import FakeStepModel, decide, score_open_loop, _reward
from nexus.evolution2.bindings import reviewed_binding

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs/unified_e225_e30.json"
RESULT = ROOT / "artifacts/unified_e225_e30_recovery.json"
METHODS = ("persistent", "quality_catalogue", "random_generation", "feedback_generation", "unified",
           "shuffled", "withheld", "ungated", "nearest", "consensus", "evidence")


def validate_config(c):
    expected = {"version": "source_proxy_unified_v1", "families": ["pendulum", "acrobot"],
        "bundles": [0, 1], "offsets": [0, 32, 64, 96], "proposal_seeds": [7, 17, 27],
        "cap_s": 180, "real_interaction_cap": 0, "logical_proposals_per_context": 6,
        "imagined_cap_per_strategy": 1536, "ridge": 1.0, "gate_thresholds": [.25, 1.],
        "proxy_probe_horizon": 16, "feedback_scale": 100.0}
    if json.dumps(c, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("runtime_config_mismatch")


def sha(p):
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def feedback_unit(raw):
    # Fixed analytical transform. No query extrema or fitted query scale.
    if not math.isfinite(raw): raise ValueError("nonfinite_proxy_label")
    return .5 + .5 * math.tanh(raw / 100.)


def proxy_table(task, seed, deadline, resources):
    """Evaluator-only full finite grammar; immutable source state, common probe.

    Reserve every fake step against its exact batch shape before dispatch.
    Reused leaf decisions are exact same-context/seed/cap computations.
    """
    plans = []
    for cap in (1536, 768):
        for v in VARIANTS:
            n = plan_bound(v, task.context.n_actions, cap).candidates_per_root
            for _ in range(1 if v.rule is Rule.FLAT else task.context.n_actions):
                if v.rule is Rule.SUCCESSOR: plans.append(model_work((1, task.context.obs_dim), 1))
                plans.extend(model_work((n, task.context.obs_dim), n) for _ in range(v.horizon))
    plans.extend(model_work((3, task.context.obs_dim), 3) for _ in range(16))
    ops = tuple(Operation(f"step_{i}", "model", p) for i, p in enumerate(plans))
    cap = Work()
    for p in plans: cap = cap.plus(p)
    ledger = ReservationLedger(ops, Limits(cap, cap, 180_000_000_000, 180_000_000_000))
    t0, c0 = time.perf_counter_ns(), time.process_time_ns()
    clock = lambda: Clock(time.process_time_ns() - c0, time.perf_counter_ns() - t0)
    fake = FakeStepModel(task.context.obs_dim, task.context.n_actions)
    cursor = [0]

    class ReservedFake:
        def step(self, obs, action):
            if time.perf_counter() >= deadline: raise TimeoutError("unified_source_cap")
            i = cursor[0]
            shape = np.asarray(obs).reshape(-1, task.context.obs_dim).shape
            cost = model_work(shape, int(np.asarray(action).size))
            if i >= len(ops) or cost != ops[i].cost: raise ValueError("unplanned_model_batch")
            ticket = ledger.reserve(ops[i].key, clock())
            try:
                result = fake.step(obs, action)
            except BaseException:
                ledger.settle(ticket, "interrupted", clock()); raise
            ledger.settle(ticket, "success", clock())
            cursor[0] += 1
            resources["fake_calls"] += 1
            resources["fake_imagined_transitions"] += shape[0]
            return result

    model = ReservedFake()
    decisions = {}
    try:
        for cap_value in (1536, 768):
            for v in VARIANTS:
                decisions[v.fingerprint, cap_value] = decide(task.family, v, task.obs, model, seed=seed, imagined_cap=cap_value)
        # Common fixed continuation: each possible first action then fifteen
        # neutral (index1) actions. Labels are same-horizon proxy action values.
        probe = np.ones((3, 16), dtype=np.int64); probe[:, 0] = np.arange(3)
        action_values = score_open_loop(model, task.obs, probe, _reward(reviewed_binding(task.family)))
    finally:
        report = ledger.close(clock())
        resources["ledger_reports"].append({"task": task.task_id, "status": report.status,
            "reserved": report.physical_reserved.payload(), "completed": report.physical_completed_reported.payload(),
            "unknown": report.physical_unknown_upper_bound.payload(), "journal_hash": digest([asdict(e) for e in report.events])})
    if report.status != "complete_execution": raise ValueError("incomplete_proxy_plan")
    table, behaviors = {}, {}
    for s in universe():
        action = execute(s, task.family, task.obs, None, seed=seed,
                         resolve=lambda v, c: decisions[v.fingerprint, c])
        table[s] = feedback_unit(float(action_values[action]))
        behaviors[s.fingerprint] = {"action": action, "raw_proxy": float(action_values[action])}
    return table, behaviors


def run(config):
    validate_config(config)
    t0, c0 = time.perf_counter(), time.process_time()
    deadline = t0 + config["cap_s"]
    old = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / "artifacts").rglob("*.json") if p != RESULT}
    resources = {"fake_calls": 0, "fake_imagined_transitions": 0, "ledger_reports": [], "logical_evaluations": 0,
                 "generated_validations": 0, "ridge_fits": 0, "real_interactions": 0, "neural_forwards": 0}
    payload = {"declared_complete": False, "scientific": False, "config": config, "rows": [], "predictions": [],
               "histories": [], "source_sha256": {}, "resources": resources, "historical_artifacts_sha256": old}
    try:
        tasks, tables, behaviors = {}, {}, {}
        for f in config["families"]:
            seed_sets = []
            for b in config["bundles"]:
                path = ROOT / "artifacts/evolution2_source_arrays" / f / f"bundle{b}_train.npz"
                payload["source_sha256"][str(path.relative_to(ROOT))] = sha(path)
                with np.load(path) as data: seed_sets.append(set(data["env_seeds"].tolist()))
                for offset in config["offsets"]:
                    key = (f, b, offset)
                    task = _task(f"unified:{f}:{b}:{offset}", "train", f, b,
                                 support_from_source(f, b, start=offset), obs_from_source(f, b, offset))
                    tasks[key] = task
                    tables[key], behaviors[key] = proxy_table(task, 700 + offset, deadline, resources)
            if seed_sets[0] & seed_sets[1]: raise ValueError("source_episode_overlap")
        payload["proxy_behaviors"] = {str(k): v for k, v in behaviors.items()}
        leafs = tuple(leaf(v) for v in VARIANTS)
        # Executable-policy witness over all registered source observations.
        signatures = {s.fingerprint: tuple(behaviors[k][s.fingerprint]["action"] for k in tasks) for s in universe()}
        fixed_signatures = {signatures[s.fingerprint] for s in leafs}
        payload["behavior_witness"] = {"structural_novel": len(universe()) - 12,
            "distinct_action_vectors": len(set(signatures.values())),
            "novel_action_vectors_beyond_fixed": len(set(signatures.values()) - fixed_signatures)}
        for f in config["families"]:
            for held in config["bundles"]:
                norm = FamilyNormalizer.fit(f, load_source_train_obs(f, (1 - held,)))
                bank = [k for k in tasks if k[0] == f and k[1] != held]
                queries = [k for k in tasks if k[0] == f and k[1] == held]
                for seed in config["proposal_seeds"]:
                    # Shared six legitimately exposed catalogue source labels.
                    pretrain = []
                    persistent = AdaptiveProposer(seed)
                    for key in bank:
                        task, table = tasks[key], tables[key]
                        source_evaluator = TrustedEvaluator(leafs, family=f, bundle_id=1-held, produce_score=lambda s: table[s])
                        available = list(VARIANTS)
                        for slot in range(6):
                            v = ANCHORS[slot] if slot < 2 else persistent.choose(tuple(available), task.context)
                            available.remove(v)
                            score = source_evaluator.evaluate("common_source", leaf(v))
                            persistent.update(TrainingFeedback(v.fingerprint, score, False, digest([key, slot, seed])), task.context)
                            pretrain.append((key, v, score))
                    for method in METHODS:
                        policy = AdaptiveProposer(seed)
                        generator = StrategyGenerator(seed, adaptive=method != "random_generation")
                        predictor = AdvantagePredictor()
                        memory = ObservationAwareAdaptive(seed=seed, gated=method == "nearest",
                            arbitration=method if method in ("consensus", "evidence") else "legacy")
                        memory.normalizers = {f: norm}
                        memory.calibration = SourceCalibration(1., float("inf"), 1., 1., {f: norm.n}, rule="cross_bundle_lobo_p95")
                        withheld = method == "withheld"
                        # Shuffling uses only already revealed source labels.
                        shuffled = [r[2] for r in pretrain]; random.Random(seed + 100).shuffle(shuffled)
                        for i, (key, v, score) in enumerate(pretrain):
                            task = tasks[key]
                            supplied = shuffled[i] if method == "shuffled" else score
                            event = digest([method, "source", seed, key, v.fingerprint])
                            policy.update(TrainingFeedback(v.fingerprint, supplied, False, event), task.context)
                            generator.update(leaf(v), supplied, task.obs, task.context, event=event, withheld=withheld)
                            memory.observe(f, task.obs, task.context, provenance=str(key), support_digest=digest(key))
                            memory.update(TrainingFeedback(v.fingerprint, supplied, False, event), task.context)
                            anchors = tuple(tables[key][leaf(a)] for a in ANCHORS)
                            x = advantage_features(leaf(v), task.obs, task.support, task.context, norm, anchors)
                            ref = advantage_features(leaf(ANCHORS[0]), task.obs, task.support, task.context, norm, anchors)
                            if not withheld: predictor.observe(x - ref, supplied - anchors[0], event=event, provenance="revealed_source")
                        # Query state is cloned: no feedback can leak to another held context.
                        for key in queries:
                            task, table = tasks[key], tables[key]
                            gen, pred, pol, mem = copy.deepcopy((generator, predictor, policy, memory))
                            mem.observe(f, task.obs, task.context, provenance=str(key), support_digest=digest(key))
                            available = list(leafs); used = set(); trace = []; own_scores = []
                            anchors = tuple(table[leaf(a)] for a in ANCHORS)
                            ref = advantage_features(leaf(ANCHORS[0]), task.obs, task.support, task.context, norm, anchors)
                            evaluator = TrustedEvaluator(universe(), family=f, bundle_id=held, produce_score=lambda s: table[s])
                            # A joint, charged two-anchor reveal precedes free choices.
                            anchor_receipts = [evaluator.evaluate(method, leaf(a)) for a in ANCHORS]
                            if method == "quality_catalogue":
                                # Frozen source fit; audit all descriptors before reading
                                # their query labels. This audit never updates any learner.
                                predictions = {s: pred.predict(advantage_features(s, task.obs, task.support, task.context, norm, anchors) - ref)
                                               for s in universe()}
                                for s, guess in predictions.items():
                                    means, weights = [], []
                                    if s.kind == "leaf":
                                        for bk, bv, val in pretrain:
                                            if bv == s.left:
                                                means.append(val - tables[bk][leaf(ANCHORS[0])])
                                                dist = np.linalg.norm(norm.embed(tasks[bk].obs) - norm.embed(task.obs))
                                                weights.append(math.exp(-min(float(dist * dist), 700.)))
                                    mean = float(np.mean(means)) if means else None
                                    kernel = float(np.average(means, weights=weights)) if means else None
                                    payload["predictions"].append({"family": f, "held_bundle": held, "offset": key[2],
                                        "seed": seed, "strategy_id": s.fingerprint, "novel": s.kind != "leaf",
                                        "predicted": guess, "actual": table[s] - anchors[0],
                                        "zero_prediction": 0., "paired_mean": mean, "observation_kernel": kernel})
                            for slot in range(6):
                                if time.perf_counter() >= deadline: raise TimeoutError("unified_source_cap")
                                before = gen.inner.learned_state()
                                pool = []
                                if slot < 2: selected = leaf(ANCHORS[slot])
                                elif method in ("persistent", "ungated", "nearest", "consensus", "evidence"):
                                    v = pol.choose(tuple(s.left for s in available), task.context) if method == "persistent" else mem.choose(tuple(s.left for s in available), task.context)
                                    selected = leaf(v)
                                elif method == "quality_catalogue":
                                    selected = max(available, key=lambda s: pred.predict(advantage_features(s, task.obs, task.support, task.context, norm, anchors) - ref))
                                else:
                                    for _ in range(2):
                                        child = gen.propose(task.context, excluded=used | {p.fingerprint for p in pool})
                                        resources["generated_validations"] += 1
                                        if child.bound(task.obs, task.context.n_actions) > 1536: raise ValueError("overbudget_child")
                                        pool.append(child)
                                    if method in ("unified", "shuffled", "withheld") and slot % 2 == 0:
                                        selected = max(pool, key=lambda s: pred.predict(advantage_features(s, task.obs, task.support, task.context, norm, anchors) - ref))
                                    else: selected = pool[0]
                                prediction = pred.predict(advantage_features(selected, task.obs, task.support, task.context, norm, anchors) - ref)
                                if selected.fingerprint in used: raise ValueError("free_duplicate_evaluation")
                                observed = anchor_receipts[slot] if slot < 2 else evaluator.evaluate(method, selected)
                                event = digest([method, seed, key, slot])
                                own_scores.append(observed)
                                # Cyclic relabeling uses only earlier exposed values; never future outcomes.
                                supplied = own_scores[slot - 1] if method == "shuffled" and slot else observed
                                gen.update(selected, supplied, task.obs, task.context, event=event, withheld=withheld)
                                active = selected.active(task.obs)
                                if not withheld:
                                    pol.update(TrainingFeedback(active.fingerprint, supplied, False, event), task.context)
                                    mem.update(TrainingFeedback(active.fingerprint, supplied, False, event), task.context)
                                    pred.observe(advantage_features(selected, task.obs, task.support, task.context, norm, anchors) - ref,
                                        supplied - anchors[0], event=event, provenance="revealed_source")
                                trace.append({"slot": slot, "strategy": selected.payload(), "id": selected.fingerprint,
                                    "observed": observed, "supplied": supplied, "prediction": prediction,
                                    "raw_proxy": behaviors[key][selected.fingerprint]["raw_proxy"],
                                    "action": behaviors[key][selected.fingerprint]["action"],
                                    "policy_before": before, "policy_after": gen.inner.learned_state(),
                                    "regret": max(table.values()) - observed, "candidate_pool": [s.payload() for s in pool]})
                                if selected in available: available.remove(selected)
                                used.add(selected.fingerprint)
                            resources["logical_evaluations"] += 6
                            resources["ridge_fits"] += pred.fit_calls
                            if evaluator.charged != 6: raise ValueError("unequal_evaluation_opportunities")
                            payload["rows"].append({"family": f, "held_bundle": held, "training_bundle": 1-held,
                                "offset": key[2], "seed": seed, "method": method, "trace": trace,
                                "first_free_regret": trace[2]["regret"], "cumulative_regret": sum(t["regret"] for t in trace[2:]),
                                "best_observed": max(t["observed"] for t in trace),
                                "mean_prediction_error": sum(abs(t["prediction"] - (t["observed"] - anchors[0])) for t in trace[2:]) / 4,
                                "generation_gain": sum(t["observed"] for t in trace[4:]) / 2 - sum(t["observed"] for t in trace[2:4]) / 2})
                            payload["rows"][-1]["predictor_parameters"] = pred.parameter_count
                            payload["rows"][-1]["memory_records"] = len(mem._store)
                            payload["rows"][-1]["proposal_attempts"] = gen.proposal_attempts
                            payload["rows"][-1]["duplicate_rejections"] = gen.duplicate_rejections
                            payload["rows"][-1]["fallbacks"] = gen.fallbacks
                            payload["rows"][-1]["predictor_memory_bytes"] = sum(x.nbytes for x in pred.x) + 8*len(pred.y)
                            payload["rows"][-1]["memory_serialized_bytes"] = len(json.dumps([asdict(r) for r in mem._store]).encode())
                            payload["histories"].append({"method": method, "key": list(key), "seed": seed,
                                                       "journal": [asdict(e) for e in gen.journal.snapshot()]})
        payload["summary"] = summarize(payload["rows"])
        payload["prediction_summary"] = {}
        for domain in ("fixed", "novel"):
            subset = [r for r in payload["predictions"] if r["novel"] == (domain == "novel")]
            payload["prediction_summary"][domain] = {"n": len(subset),
                "mae": float(np.mean([abs(r["predicted"]-r["actual"]) for r in subset])),
                "zero_mae": float(np.mean([abs(r["actual"]) for r in subset])),
                "sign_accuracy": float(np.mean([np.sign(r["predicted"]) == np.sign(r["actual"]) for r in subset])),
                "abstention": float(np.mean([abs(r["predicted"]) < .001 for r in subset])),
                "mean_calibration_bias": float(np.mean([r["predicted"]-r["actual"] for r in subset]))}
        paired = [r for r in payload["predictions"] if r["paired_mean"] is not None]
        payload["prediction_common_support"] = {"n": len(paired),
            **{m: float(np.mean([abs(r[m] - r["actual"]) for r in paired]))
               for m in ("predicted", "paired_mean", "observation_kernel")}}
        ranking = []
        for f, b, o, seed in itertools.product(config["families"], config["bundles"], config["offsets"], config["proposal_seeds"]):
            subset = [r for r in payload["predictions"] if not r["novel"] and
                      (r["family"], r["held_bundle"], r["offset"], r["seed"]) == (f, b, o, seed)]
            comparisons = [(np.sign(a["predicted"]-b_["predicted"]), np.sign(a["actual"]-b_["actual"]))
                           for a, b_ in itertools.combinations(subset, 2) if abs(a["actual"]-b_["actual"]) > 1e-12]
            ranking.append({"family": f, "held_bundle": b, "offset": o, "seed": seed,
                            "informative_pairs": len(comparisons),
                            "accuracy": float(np.mean([a == b_ for a, b_ in comparisons])) if comparisons else None})
        payload["ranking_accuracy"] = ranking
        payload["paired_comparisons"] = {}
        for baseline in METHODS:
            comparisons = []
            for row in payload["rows"]:
                if row["method"] != "unified": continue
                match = next(r for r in payload["rows"] if r["method"] == baseline and
                             all(r[k] == row[k] for k in ("family", "held_bundle", "offset", "seed")))
                comparisons.append({**{k: row[k] for k in ("family", "held_bundle", "offset", "seed")},
                    "regret_reduction": match["cumulative_regret"] - row["cumulative_regret"]})
            payload["paired_comparisons"][baseline] = comparisons
        if not all(sha(ROOT / p) == h for p, h in old.items()): raise ValueError("history_changed")
        validate(payload, config)
        payload["declared_complete"] = True
    except Exception as exc:
        payload["failure"] = f"{type(exc).__name__}: {exc}"
    resources.update(wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - c0)
    prior = json.loads((ROOT / "artifacts/unified_e225_e30.json").read_text())
    prior_s = prior["resources"]["wall_s"]
    payload["prior_incomplete_attempt"] = {"path": "artifacts/unified_e225_e30.json",
        "sha256": sha(ROOT / "artifacts/unified_e225_e30.json"), "wall_s": prior_s}
    payload["session_ledger"] = {"used_before_s": 327.869 + prior_s, "remaining_before_s": 3272.131 - prior_s,
        "used_after_s": 327.869 + prior_s + resources["wall_s"], "remaining_after_s": 3272.131 - prior_s - resources["wall_s"]}
    return payload


def summarize(rows):
    metrics = ("first_free_regret", "cumulative_regret", "best_observed", "mean_prediction_error", "generation_gain")
    # Each fold has four offsets and three proposer seeds; reverse folds are
    # dependent. Descriptive paired rows only, no fabricated decoder intervals.
    return {m: {k: float(np.mean([r[k] for r in rows if r["method"] == m])) for k in metrics} for m in METHODS}


def validate(payload, config):
    validate_config(config)
    expected = set(itertools.product(config["families"], config["bundles"], config["offsets"], config["proposal_seeds"], METHODS))
    actual = [(r["family"], r["held_bundle"], r["offset"], r["seed"], r["method"]) for r in payload["rows"]]
    if len(actual) != len(expected) or set(actual) != expected: raise ValueError("incomplete_method_grid")
    for r in payload["rows"]:
        if r["held_bundle"] == r["training_bundle"]: raise ValueError("bundle_leak")
        if len(r["trace"]) != 6 or len({t["id"] for t in r["trace"]}) != 6 or [t["slot"] for t in r["trace"]] != list(range(6)):
            raise ValueError("incomplete_or_duplicate_feedback")
        for t in r["trace"]:
            if any(type(t[k]) not in (int, float) or not math.isfinite(t[k]) for k in ("observed", "supplied", "prediction", "regret")):
                raise ValueError("invalid_metric")
    expected_predictions = {(f,b,o,seed,s.fingerprint) for f,b,o,seed in itertools.product(config["families"],config["bundles"],config["offsets"],config["proposal_seeds"]) for s in universe()}
    predictions = [(r["family"],r["held_bundle"],r["offset"],r["seed"],r["strategy_id"]) for r in payload["predictions"]]
    if len(predictions) != len(expected_predictions) or set(predictions) != expected_predictions:
        raise ValueError("incomplete_prediction_grid")
    for r in payload["predictions"]:
        if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) for k in ("predicted", "actual")):
            raise ValueError("invalid_prediction_metric")
    if payload["resources"]["logical_evaluations"] != len(expected)*6:
        raise ValueError("unequal_evaluation_accounting")
    reports = payload["resources"]["ledger_reports"]
    expected_tasks = {f"unified:{f}:{b}:{o}" for f,b,o in itertools.product(config["families"],config["bundles"],config["offsets"])}
    if len(reports) != len(expected_tasks) or {r["task"] for r in reports} != expected_tasks or any(r["status"] != "complete_execution" for r in reports):
        raise ValueError("incomplete_resource_accounting")
    return True
