#!/usr/bin/env python3
"""Independent Cline re-scoring of the locked archived successor-parity grid.

Frozen-model inference on archived observations with genuine saved student
contexts only. Never instantiates an environment, trains, retunes, opens a
closed split or compares controllers. Every freshly scored cell is
cross-checked against the recorded archived-parity artifact; no historical
artifact is overwritten and no closed screen is reopened.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
import yaml

import audit_successor_archived_parity as audit
import audit_successor_search_efficiency as common
from nexus.world.frozen_dynamics import load_context_checkpoint
from nexus.world.long_continuation_execution import context_hash, frozen_hash
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.successor_search import PreparedSuccessorSearch
from nexus.world.terminal_value_execution import save

CONFIG = Path("configs/cline_archived_rescore.yaml")
PROTOCOL = Path("docs/NEXUS_SUCCESSOR_ARCHIVED_PARITY_CLINE_RESCORE_PROTOCOL.md")
RECORDED = Path("artifacts/successor_archived_parity.json")
OUTPUT = Path("artifacts/cline_archived_rescore.json")
BASE_GRID_SHA256 = "47803e17bd4bc15cdff3a37da121a134d225924f3f9f7f2dff3c861eb0380897"
RECORDED_SHA256 = "4a0afd518d632b78451324dfbed89cfa2b17e644b60ef9aa0511b40d34454707"


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    fixed = dict(audit_id="cline_archived_rescore_verification_v1",
        starting_sha="9c6ed4aa75b3fe430514ea77bf44064faaf34011",
        base_grid_config_sha256=BASE_GRID_SHA256,
        decoders=list(range(10)), tasks=list(range(3)), visitors=["student", "zero"],
        contexts=["zero", "0", "1", "2", "3", "4"], phases=[0, 16, 50, 100, 150, 199],
        horizon=16, n_candidates=16, q_atol=.0002, q_rtol=.00002, cross_atol=1e-9,
        time_cap_s=120, imagined_transition_cap=3330720, environment_interactions=0,
        training_updates=0, controller_integration=False)
    if set(cfg) != set(fixed) | {"parents"} or any(
            type(cfg.get(k)) is not type(v) or cfg[k] != v for k, v in fixed.items()):
        raise ValueError("locked Cline rescore configuration changed")
    if common.sha("configs/successor_archived_parity.yaml") != BASE_GRID_SHA256:
        raise ValueError("locked base archived-parity grid changed")
    if common.sha(RECORDED) != RECORDED_SHA256:
        raise ValueError("recorded archived-parity artifact changed")
    for file, digest in cfg["parents"].items():
        if common.sha(file) != digest:
            raise ValueError(f"closed parent changed: {file}")
    return cfg


def within(a, b, atol, rtol):
    return all(abs(x - y) <= atol + rtol * abs(y) for x, y in zip(a, b))


def cross_check(fresh, recorded, cfg):
    ref = fresh["reference_q"]; bat = fresh["batched_q"]
    dev_ref = max(abs(x - y) for x, y in zip(ref, recorded["reference_q"]))
    dev_bat = max(abs(x - y) for x, y in zip(bat, recorded["batched_q"]))
    return dict(
        reference_action_equal=fresh["reference_action"] == recorded["reference_action"],
        batched_action_equal=fresh["batched_action"] == recorded["batched_action"],
        metrics_equal=fresh["metrics"] == recorded["metrics"],
        max_reference_deviation=dev_ref, max_batched_deviation=dev_bat,
        reference_bitwise=dev_ref == 0., batched_bitwise=dev_bat == 0.,
        within_cross_tolerance=dev_ref <= cfg["cross_atol"] and dev_bat <= cfg["cross_atol"],
        within_audit_tolerance=within(ref, recorded["reference_q"], cfg["q_atol"], cfg["q_rtol"])
            and within(bat, recorded["batched_q"], cfg["q_atol"], cfg["q_rtol"]))


def summarize(rows, cfg):
    n = len(rows)
    pooled = dict(cases=n,
        fresh_action_matches=sum(r["metrics"]["action_equal"] for r in rows),
        fresh_ranking_matches=sum(r["metrics"]["ranking_equal"] for r in rows),
        fresh_numerical_matches=sum(r["metrics"]["q_within_tolerance"] for r in rows),
        fresh_near_ties=sum(r["metrics"]["near_tie"] for r in rows),
        fresh_max_absolute_q_difference=max(
            r["metrics"]["max_absolute_q_difference"] for r in rows),
        recorded_reference_action_agreement=sum(
            r["cross"]["reference_action_equal"] for r in rows),
        recorded_batched_action_agreement=sum(
            r["cross"]["batched_action_equal"] for r in rows),
        recorded_metrics_agreement=sum(r["cross"]["metrics_equal"] for r in rows),
        bitwise_reference_cells=sum(r["cross"]["reference_bitwise"] for r in rows),
        bitwise_batched_cells=sum(r["cross"]["batched_bitwise"] for r in rows),
        within_cross_tolerance=sum(r["cross"]["within_cross_tolerance"] for r in rows),
        within_audit_tolerance=sum(r["cross"]["within_audit_tolerance"] for r in rows),
        max_reference_deviation=max(r["cross"]["max_reference_deviation"] for r in rows),
        max_batched_deviation=max(r["cross"]["max_batched_deviation"] for r in rows))
    parity = (pooled["fresh_action_matches"] == pooled["fresh_numerical_matches"] == n
        and pooled["fresh_ranking_matches"] == n)
    actions = (pooled["recorded_reference_action_agreement"]
        == pooled["recorded_batched_action_agreement"] == n)
    if parity and actions and pooled["within_cross_tolerance"] == n \
            and pooled["recorded_metrics_agreement"] == n:
        label = "independent_rescore_reproduced"
    elif parity and actions and pooled["within_audit_tolerance"] == n:
        label = "independent_rescore_confirmed_within_tolerance_not_bitwise"
    else:
        label = "independent_rescore_disagrees"
    return dict(pooled=pooled, label=label)


class Guard:
    def __init__(self, cfg):
        self.deadline = time.perf_counter() + cfg["time_cap_s"]
        self.cap = cfg["imagined_transition_cap"]
        self.calls = self.transitions = 0

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError("Cline rescore time cap reached")

    def install(self, model):
        step = model.step

        def guarded(obs, actions):
            self.check()
            count = len(np.asarray(actions).reshape(-1))
            if self.transitions + count > self.cap:
                raise RuntimeError("imagined-transition cap reached")
            result = step(obs, actions)
            self.calls += 1; self.transitions += count
            return result
        model.step = guarded


def run(root, cfg):
    if cfg != load_config():
        raise ValueError("runtime configuration differs from locked protocol")
    if OUTPUT.exists():
        raise RuntimeError("refusing repeated Cline rescore/overwrite")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("commit clean protocol before Cline rescore")
    subprocess.run(["git", "merge-base", "--is-ancestor", cfg["starting_sha"], "HEAD"], check=True)
    recorded = json.loads(RECORDED.read_text())
    if recorded.get("complete") is not True or recorded.get("label") != \
            "archived_decision_parity_established_on_tested_inputs":
        raise ValueError("recorded archived-parity result incomplete or unexpected")
    if recorded["parents"] != {k: v for k, v in cfg["parents"].items() if k != str(RECORDED)}:
        raise ValueError("recorded parent provenance differs from locked rescore configuration")
    for file, digest in recorded["code_hashes"].items():
        if common.sha(file) != digest:
            raise ValueError("code that produced the recorded result changed")
    recorded_rows = {(r["decoder"], r["task"], r["visitor"], r["phase"], r["context"]): r
                     for r in recorded["rows"]}
    expected = audit.expected_grid(cfg)
    if set(recorded_rows) != expected:
        raise ValueError("recorded grid differs from the locked rescore grid")
    started = time.perf_counter(); guard = Guard(cfg)
    torch.set_num_threads(1)
    payload = dict(complete=False, label="incomplete", rows=[], parents=cfg["parents"],
        implementation_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        config_sha256=common.sha(CONFIG), protocol_sha256=common.sha(PROTOCOL), source_dirty=False,
        base_grid_config_sha256=BASE_GRID_SHA256, recorded_artifact_sha256=RECORDED_SHA256,
        checkpoint_root=str(root), new_environment_interactions=0, optimizer_updates=0,
        historical_controller_changed=False, unused_reserved_splits_accessed=False,
        numpy=np.__version__, torch=torch.__version__, torch_threads=1)
    payload["code_hashes"] = {f: common.sha(f) for f in (
        "scripts/cline_verify_successor_archived_rescore.py",
        "scripts/audit_successor_archived_parity.py",
        "scripts/audit_successor_search_efficiency.py",
        "src/nexus/world/successor_search.py",
        "src/nexus/world/bellman_backup_control.py")}
    try:
        archive, contexts = audit.inputs()
        decoders, students = audit.metadata_records()
        records = list(decoders.values()) + list(students.values())
        audit.verify_records(root, records)
        payload["checkpoint_records"] = records
        for d in cfg["decoders"]:
            for name in cfg["contexts"]:
                guard.check()
                model = load_context_checkpoint(root / decoders[d]["path"])
                if name != "zero":
                    model.encoder.load_state_dict(torch.load(
                        root / students[d, name]["path"], map_location="cpu", weights_only=False))
                model.net.eval(); model.encoder.eval(); guard.install(model)
                for t in cfg["tasks"]:
                    z, fingerprints = audit.saved_context(contexts, d, t, name)
                    model.z = torch.tensor(z)
                    if [frozen_hash(model), context_hash(model)] != fingerprints:
                        raise ValueError("loaded student/decoder/normalizer/context differs from the original archive")
                    for visitor, phase in itertools.product(cfg["visitors"], cfg["phases"]):
                        guard.check()
                        obs, seed = audit.observation(archive[d, t], visitor, phase)
                        rec = recorded_rows[(d, t, visitor, phase, name)]
                        if rec["observation"] != obs.tolist() or rec["candidate_seed"] != seed:
                            raise ValueError("recorded observation/candidate-seed provenance drift")
                        seq = candidate_sequences(seed, cfg["horizon"], cfg["n_candidates"], 3)
                        prepared = PreparedSuccessorSearch(seq, family="pendulum")
                        before = common.fingerprint(model)
                        (action, q), old_count = common.counted(
                            model, lambda: common.original(model, obs, seq, "pendulum"))
                        result, new_count = common.counted(
                            model, lambda: prepared.score(model, obs))
                        fresh = dict(reference_q=q.tolist(), batched_q=result.q.tolist(),
                            reference_action=action, batched_action=result.action,
                            reference_counts=old_count, batched_counts=new_count)
                        fresh["metrics"] = audit.row_metrics(fresh, cfg)
                        for counts, step_calls in ((old_count, 51), (new_count, 17)):
                            if counts != dict(step_calls=step_calls,
                                    forward_calls=step_calls, imagined_transitions=771):
                                raise ValueError("per-cell call accounting changed")
                        row = dict(decoder=d, task=t, visitor=visitor, phase=phase, context=name,
                            observation=obs.tolist(), candidate_seed=seed,
                            fingerprint_before=before, fingerprint_after=common.fingerprint(model))
                        row.update(fresh); row["cross"] = cross_check(fresh, rec, cfg)
                        payload["rows"].append(row)
        payload.update(summarize(payload["rows"], cfg))
        audit.verify_records(root, records)
        payload["checkpoint_after_verified"] = len(records)
        if guard.transitions != cfg["imagined_transition_cap"] or guard.calls != 2160 * 68:
            raise ValueError("fresh inference totals inconsistent with the recorded grid")
        guard.check(); payload["complete"] = True

    except Exception as exc:
        payload["label"] = "invalid_or_incomplete_execution"
        payload["failure"] = dict(type=type(exc).__name__, message=str(exc))
    payload["wall_clock_s"] = time.perf_counter() - started
    payload["counts"] = dict(model_calls=guard.calls, imagined_transitions=guard.transitions)
    save(OUTPUT, payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    args = parser.parse_args(); cfg = load_config()
    result = run(args.checkpoint_root.resolve(), cfg)
    print(json.dumps({k: result.get(k) for k in
        ("complete", "label", "wall_clock_s", "counts", "failure")}, indent=2))
    if not result["complete"]:
        raise SystemExit(1)

