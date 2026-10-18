"""E2.24 recorded-source/proxy audit; never collects simulator experience.

Reuses ObservationAwareAdaptive, AdaptiveProposer, TrustedEvaluator and
the closed E2.22 development fixture. No new memory/evolution stack.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory_decide_bench import (
    PROPOSALS, raw_catalogue_scores, obs_from_source, support_from_source,
)
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS, VARIANTS
from nexus.evolution2.methods import make_methods
from nexus.evolution2.observation_memory import (
    ROOT, SOURCE, ObservationAwareAdaptive, calibrate_cross_bundle,
    fit_family_normalizers,
)
from nexus.evolution2.observation_memory_bench import PHASES, _run_task, make_e222_tasks
from nexus.evolution2.persist_reset_science import FrozenRevealedScale
from nexus.evolution2.planner_adapter import FakeStepModel

RESULTS = ROOT / "artifacts/evolution2_24_evidence_arbitration.json"
BASE = "3bf0a97f15f98af5e28dcf619fe8c1332eea2818"
METHODS = ("persistent_adaptive", "observation_cross_bundle", "observation_ungated_memory",
           "neighbor_consensus", "evidence_arbitration", "reset_adaptive")
OFFSETS = (0, 32, 64, 96)
CAP_S = 60.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CountedFake(FakeStepModel):
    def __init__(self, model):
        super().__init__(model.obs_dim, model.n_actions, scale=model.scale)
        self.states = 0
        self.calls = 0

    def step(self, obs, action):
        self.states += int(np.asarray(obs).reshape(-1, self.obs_dim).shape[0])
        self.calls += 1
        return super().step(obs, action)


def score_table(task, seed):
    counter = CountedFake(task.model)
    raw = raw_catalogue_scores(replace(task, model=counter), seed)
    scale = FrozenRevealedScale(raw)
    return ({v: scale.unit(raw[v]) for v in VARIANTS},
            {"imagined_transitions": counter.states, "fake_step_calls": counter.calls})


def source_quality_calibration(normalizers, cross, *, seed=7, deadline=math.inf):
    """Conservative empirical paired-score error, held-out whole bundle.

    Only E2.8 bundle0/1 train observations. Six legitimate source receipts
    per context; full source proxy grid is audit-only calibration ground
    truth, not accessible to a proposer. No development task is constructed.
    """
    from nexus.core.strategy_memory_decide_bench import _task
    source = []
    imagined = calls = 0
    for family in ("pendulum", "acrobot"):
        for bundle in (0, 1):
            for offset in OFFSETS:
                if time.perf_counter() >= deadline:
                    raise TimeoutError("source_calibration_cap")
                task = _task(f"cal:{family}:{bundle}:{offset}", "train", family, bundle,
                             support_from_source(family, bundle, start=offset),
                             obs_from_source(family, bundle, offset))
                unit, cost = score_table(task, seed + int(digest(task.task_id)[:8], 16) % 1000)
                imagined += cost["imagined_transitions"]
                calls += cost["fake_step_calls"]
                proposer = make_methods(seed)["persistent_adaptive"]
                row = _run_task(proposer, task, unit=unit, update=True)
                source.append({"family": family, "bundle": bundle, "offset": offset,
                               "embedding": normalizers[family].embed(task.obs),
                               "receipts": dict(zip(row["variants"], row["scores"])),
                               "unit": {v.fingerprint: s for v, s in unit.items()}})
    errors = []
    anchor_errors = []
    audits = []
    for query in source:
        bank = [r for r in source if r["family"] == query["family"] and r["bundle"] != query["bundle"]]
        for i, a in enumerate(VARIANTS):
            for b in VARIANTS[i+1:]:
                paired = [r for r in bank if a.fingerprint in r["receipts"] and b.fingerprint in r["receipts"]]
                if not paired:
                    continue
                w = np.asarray([math.exp(-(np.linalg.norm(r["embedding"]-query["embedding"])/cross.kernel_length)**2)
                                for r in paired])
                if w.sum() <= 1e-300:
                    continue
                predicted = float(w @ np.asarray([r["receipts"][a.fingerprint]-r["receipts"][b.fingerprint]
                                                   for r in paired]) / w.sum())
                actual = query["unit"][a.fingerprint] - query["unit"][b.fingerprint]
                error = abs(predicted-actual)
                errors.append(error)
                audits.append({"family": query["family"], "query_bundle": query["bundle"],
                               "offset": query["offset"], "arms": [a.fingerprint,b.fingerprint],
                               "predicted_delta": predicted, "actual_delta": actual, "absolute_error": error})
        nearest = min(bank, key=lambda r: np.linalg.norm(r["embedding"]-query["embedding"]))
        anchor_errors.append(float(np.mean([abs(nearest["receipts"][a.fingerprint]-query["unit"][a.fingerprint]) for a in ANCHORS])))
    return {"rule": "max_lobo_paired_advantage_error", "quality_error": max(errors) if errors else 1.0,
            "n_contexts": len(source), "offsets": list(OFFSETS), "bundles": [0,1],
            "n_pairs": len(errors), "anchor_error_mean": float(np.mean(anchor_errors)),
            "pair_error_mean": float(np.mean(errors)) if errors else None,
            "independent_physics_replications": 0,
            "warning": "empirical finite-source error allowance, not a calibrated probability or confidence bound",
            "used_development_outcomes": False, "rows": audits,
            "imagined_transitions": imagined, "fake_step_calls": calls}


def methods_for(seed, normalizers, cross, quality_error):
    old = make_methods(seed)
    methods = {k: old[k] for k in ("persistent_adaptive", "reset_adaptive")}
    for name, mode, gated in (("observation_cross_bundle","legacy",True),
                              ("observation_ungated_memory","legacy",False),
                              ("neighbor_consensus","consensus",True),
                              ("evidence_arbitration","evidence",True)):
        m = ObservationAwareAdaptive(seed=seed, label=name, gated=gated,
                                     arbitration=mode, quality_error=quality_error)
        m.normalizers, m.calibration = normalizers, cross
        methods[name] = m
    return {k: methods[k] for k in METHODS}


def validate_results(payload):
    def finite_tree(value):
        if isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                finite_tree(child)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite_trace_metric")
    finite_tree(payload)
    expected = {"train": {"pend_store_0","acro_store_0","pend_store_1","acro_zero_0"},
                "development": {"pend_store_2","acro_store_1"},
                "shifted": {"acro_zero_1","pend_far_2","acro_far_1"},
                "collision": {"acro_zero_collision"}}
    if set(payload["rows"]) != set(METHODS):
        raise ValueError("incomplete_methods")
    for name in METHODS:
        if set(payload["rows"][name]) != set(PHASES):
            raise ValueError("incomplete_phases")
        for phase, ids in expected.items():
            rows = payload["rows"][name][phase]
            if len(rows) != len(ids) or {r["task_id"] for r in rows} != ids:
                raise ValueError("incomplete_or_duplicate_tasks")
            for row in rows:
                if (len(row["variants"]) != PROPOSALS or len(set(row["variants"])) != PROPOSALS
                        or len(row["scores"]) != PROPOSALS or len(row["traces"]) != PROPOSALS
                        or row["charged"] != PROPOSALS):
                    raise ValueError("incomplete_proposal_grid")
                for value in row["scores"] + [row[k] for k in ("best","regret","first_free_regret","cumulative_free_regret")]:
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError("nonfinite_required_metric")
    return True


def run_benchmark(seed=7):
    started, cpu0 = time.perf_counter(), time.process_time()
    deadline = started + CAP_S
    # Read bytes, never rewrite historical artifacts or the scientific ledger.
    historical = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT/"artifacts").glob("*.json")
                  if p != RESULTS}
    normalizers = fit_family_normalizers()
    cross = calibrate_cross_bundle(normalizers, seed=seed)
    calibration = source_quality_calibration(normalizers, cross, seed=seed, deadline=deadline)
    # This boundary is deliberate: development tasks cannot affect calibration.
    calibration_hash = digest(calibration)
    tasks = make_e222_tasks(normalizers)
    methods = methods_for(seed, normalizers, cross, calibration["quality_error"])
    rows = {n: {p: [] for p in PHASES} for n in METHODS}
    method_time = {n: 0.0 for n in METHODS}
    model_states = model_calls = 0
    for task in tasks:
        if time.perf_counter() >= deadline:
            return {"declared_complete": False,"failure": "execution_cap", "rows": rows,
                    "wall_s": time.perf_counter()-started, "env_steps": 0}
        unit, cost = score_table(task, seed + int(digest(task.task_id)[:8],16) % 1000)
        model_states += cost["imagined_transitions"]
        model_calls += cost["fake_step_calls"]
        for name, method in methods.items():
            t0 = time.perf_counter()
            row = _run_task(method, task, unit=unit, update=True, include_traces=True)
            method_time[name] += time.perf_counter()-t0
            rows[name][task.phase].append(row)
    summary = {}
    for name in METHODS:
        summary[name] = {}
        for phase in PHASES:
            block = rows[name][phase]
            traces = [t for r in block for t in r["traces"][2:]]
            overrides = [t for t in traces if t.get("override")]
            selected = [t["comparisons"][t["choice"]] for t in traces if "comparisons" in t]
            summary[name][phase] = {
                **{k: float(np.mean([r[k] for r in block])) for k in
                   ("first_free_regret","cumulative_free_regret","best","regret")},
                "acceptance_rate": sum(t.get("action")=="retrieve" for t in traces)/len(traces),
                "abstention_rate": sum(t.get("action")=="fallback" for t in traces)/len(traces),
                "overrides": len(overrides),
                "correct_overrides": sum(t["posthoc_override_gain"]>1e-12 for t in overrides),
                "harmful_overrides": sum(t["posthoc_override_gain"]<-1e-12 for t in overrides),
                "neutral_overrides": sum(abs(t["posthoc_override_gain"])<=1e-12 for t in overrides),
                "mean_anchor_error": float(np.mean([t["anchor_error"] for t in selected if t.get("anchor_error") is not None]))
                    if any(t.get("anchor_error") is not None for t in selected) else None,
                "mean_contexts": float(np.mean([t.get("independent_contexts",0) for t in traces])),
            }
    for name in METHODS:
        for phase in PHASES:
            for baseline in ("persistent_adaptive","observation_ungated_memory"):
                summary[name][phase][f"first_free_minus_{baseline}"] = (
                    summary[name][phase]["first_free_regret"]-summary[baseline][phase]["first_free_regret"])
    preserved = all(sha(ROOT/p)==h for p,h in historical.items())
    if not preserved:
        raise RuntimeError("historical_artifact_changed")
    payload = {"declared_complete": False, "scientific": False, "score_is_real_control": False,
               "collection": False, "env_steps": 0, "neural_training": False,
               "used_e217_science_arrays": False, "scientific_ledger": {"used_s":327.869,"remaining_s":3272.131},
               "base_sha": BASE, "execution_sha": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
               "implementation_sha256": {p:sha(ROOT/p) for p in (
                   "src/nexus/evolution2/observation_memory.py",
                   "src/nexus/evolution2/observation_memory_bench.py",
                   "src/nexus/evolution2/evidence_arbitration_bench.py",
                   "src/nexus/core/strategy_memory_decide_bench.py",
                   "src/nexus/evolution1/toy_loop.py",
                   "src/nexus/evolution2/planner_adapter.py",
                   "docs/NEXUS_E2_24_EVIDENCE_ARBITRATION.md")},
               "tracked_diff_before_results": subprocess.check_output(["git","diff","HEAD","--stat"],cwd=ROOT,text=True),
               "untracked_before_results": subprocess.check_output(["git","ls-files","--others","--exclude-standard"],cwd=ROOT,text=True).splitlines(),
               "seed": seed, "cap_s": CAP_S, "calibration": calibration, "calibration_hash": calibration_hash,
               "cross_calibration": {"length": cross.kernel_length, "gate": cross.gate_threshold},
               "rows": rows,"summary": summary,"historical_artifacts_sha256":historical,
               "historical_artifacts_preserved": preserved,
               "source_sha256": {str(p.relative_to(ROOT)):sha(p) for p in SOURCE.glob("*/bundle[01]_train.npz")},
               "resources": {"wall_s": time.perf_counter()-started,"cpu_s":time.process_time()-cpu0,
                             "method_wall_s":method_time,"diagnostic_proxy_states":model_states,
                             "calibration_proxy_states":calibration["imagined_transitions"],
                             "fake_step_calls":model_calls+calibration["fake_step_calls"],
                             "logical_lookups_each":len(tasks)*PROPOSALS,
                             "actual_proxy_catalogue_evaluations":(len(tasks)+calibration["n_contexts"])*len(VARIANTS),
                             "matched_cached_receipts_each":len(tasks)*PROPOSALS,
                             "store_records":{n:len(m._store) for n,m in methods.items() if hasattr(m,"_store")},
                             "store_serialized_bytes":{n:len(json.dumps([vars(r) for r in m._store]).encode())
                                                       for n,m in methods.items() if hasattr(m,"_store")}},
               "limitations": ["Known development fixtures; no independent confirmation or statistical replication.",
                               "Proxy full-catalogue unit scaling and regret oracles are retained from E2.23.",
                               "Distinct support contexts are not independent physics replications.",
                               "Current receipts update sequentially, including development, as in E2.23.",
                               "Accept/override quality measured against same-path proposer, not counterfactual full policy."]}
    validate_results(payload)
    payload["declared_complete"] = True
    return payload


def write_artifact(path=RESULTS):
    path = Path(path)
    if path.exists():
        raise FileExistsError("preserve_previous_e224_result")
    started = time.perf_counter()
    try:
        payload = run_benchmark()
        encoded = json.dumps(payload,indent=2,allow_nan=False)+"\n"
    except Exception as exc:
        path.write_text(json.dumps({"declared_complete":False,"env_steps":0,
                                   "failure":f"{type(exc).__name__}: {exc}",
                                   "wall_s":time.perf_counter()-started})+"\n")
        raise
    path.write_text(encoded)
    return payload
