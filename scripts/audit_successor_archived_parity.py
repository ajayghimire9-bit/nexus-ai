#!/usr/bin/env python3
"""Archived Pendulum observations/context only. Never instantiates an environment."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
import yaml

import audit_successor_search_efficiency as common
from nexus.world.frozen_dynamics import load_context_checkpoint
from nexus.world.long_continuation_execution import frozen_hash, context_hash
from nexus.world.planning_value import finite_array
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.successor_search import PreparedSuccessorSearch
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG = Path("configs/successor_archived_parity.yaml")
PROTOCOL = Path("docs/NEXUS_SUCCESSOR_ARCHIVED_PARITY_PROTOCOL.md")
OUTPUT = Path("artifacts/successor_archived_parity.json")
ARCHIVE = Path("artifacts/late_episode_decision_trajectory.json")
CONTEXTS = Path("artifacts/source_scalar_calibration.json")
CONFIG_SHA256 = "47803e17bd4bc15cdff3a37da121a134d225924f3f9f7f2dff3c861eb0380897"


def load_config():
    if common.sha(CONFIG) != CONFIG_SHA256:
        raise ValueError("locked archived parity configuration hash changed")
    cfg = yaml.safe_load(CONFIG.read_text())
    fixed = dict(audit_id="successor_archived_context_parity_v1",
        starting_sha="f6230c5f87148986a42f612ff905353d1aa244f6", decoders=list(range(10)),
        tasks=list(range(3)), visitors=["student", "zero"], contexts=["zero", "0", "1", "2", "3", "4"],
        phases=[0, 16, 50, 100, 150, 199], horizon=16, n_candidates=16, q_atol=.0002,
        q_rtol=.00002, time_cap_s=60, imagined_transition_cap=3330720,
        environment_interactions=0, training_updates=0, controller_integration=False)
    if set(cfg) != set(fixed) | {"parents"} or any(type(cfg.get(k)) is not type(v) or cfg[k] != v for k, v in fixed.items()):
        raise ValueError("locked archived parity configuration changed")
    for file, digest in cfg["parents"].items():
        if common.sha(file) != digest:
            raise ValueError(f"closed parent changed: {file}")
    return cfg


def expected_grid(cfg):
    return set(itertools.product(cfg["decoders"], cfg["tasks"], cfg["visitors"], cfg["phases"], cfg["contexts"]))


def inputs():
    archive = json.loads(ARCHIVE.read_text())
    contexts = json.loads(CONTEXTS.read_text())
    if archive.get("complete") is not True or contexts.get("complete") is not True:
        raise ValueError("incomplete archive/context evidence")
    a = checked_id_grid(archive["cells"], ("decoder", "task"), set(itertools.product(range(10), range(3))))
    c = checked_id_grid(contexts["cells"], ("decoder", "task", "state"), set(itertools.product(range(10), range(3), range(2))))
    return a, c


def saved_context(cells, d, t, name):
    vectors = []
    for v in range(2):
        row = cells[d, t, v]
        x = finite_array(row["scores"][name]["inputs"], (16, 11))
        if not np.all(x[:, 3:] == x[0, 3:]): raise ValueError("context varied within archived scoring")
        z = np.asarray(x[0, 3:], dtype=np.float32)
        digest = hashlib.sha256(z.tobytes()).hexdigest()
        if row["before"] != row["after"] or digest != row["before"][name][1]:
            raise ValueError("context fingerprint drift")
        vectors.append(z)
    if not np.array_equal(*vectors): raise ValueError("context differs between visitor archives")
    return vectors[0], cells[d, t, 0]["before"][name]


def metadata_records():
    # Only already-published checkpoint metadata is selected; no prediction scores,
    # query outcomes, task tuples or unused reserved splits enter this audit.
    old = json.loads(Path("artifacts/latent_generalization_confirmation.json").read_text())["checkpoints"]
    manifest = json.loads(Path("artifacts/control_replication_checkpoints/manifest.json").read_text())["decoders"]
    decoders = {r["seed"]: r for r in common.checkpoint_records() if r["family"] == "pendulum"}
    students = {}
    for d, s in itertools.product(range(10), range(5)):
        if d < 3:
            found = [r for r in old if r["kind"] == "broad" and r["epoch"] == 200 and r["decoder"] == d and r["student"] == s]
            if len(found) != 1: raise ValueError("missing/duplicate original student checkpoint")
            row = found[0]
        else:
            row = manifest[str(d)]["students"][f"{s}:broad"]
        students[d, str(s)] = dict(path=row["path"], sha256=row["sha256"])
    return decoders, students


def observation(row, visitor, phase):
    trace = row[visitor]
    if len(trace["obs"]) != 200 or len(trace["seeds"]) != 200:
        raise ValueError("archived episode truncated or missing observations/seeds")
    obs = finite_array(trace["obs"][phase], (3,)).astype(np.float32)
    seed = trace["seeds"][phase]
    if type(seed) is not int: raise ValueError("invalid archived candidate seed")
    return obs, seed


def verify_records(root, records):
    if not records: raise ValueError("no requested checkpoint records")
    for r in records:
        if not (root / r["path"]).is_file() or common.sha(root / r["path"]) != r["sha256"]:
            raise RuntimeError(f'required checkpoint missing or wrong: {r["path"]}')


def row_metrics(row, cfg):
    old = finite_array(row["reference_q"], (3,)); new = finite_array(row["batched_q"], (3,))
    rank = np.argsort(old, kind="stable")
    gap = float(old[rank[-1]] - old[rank[-2]])
    threshold = 2 * (cfg["q_atol"] + cfg["q_rtol"] * float(np.max(np.abs(old))))
    return dict(action_equal=int(np.argmax(old)) == int(np.argmax(new)),
        ranking_equal=bool(np.array_equal(rank, np.argsort(new, kind="stable"))),
        q_within_tolerance=bool(np.allclose(old, new, atol=cfg["q_atol"], rtol=cfg["q_rtol"])),
        max_absolute_q_difference=float(np.max(np.abs(old - new))),
        reference_top_gap=gap, near_tie_threshold=threshold, near_tie=gap <= threshold)


def validate(rows, cfg):
    seen = set(); expected = expected_grid(cfg)
    for row in rows:
        key = tuple(row[k] for k in ("decoder", "task", "visitor", "phase", "context"))
        if (any(type(row[k]) is not int for k in ("decoder", "task", "phase"))
                or key not in expected or key in seen): raise ValueError("duplicate/invalid planned cell")
        seen.add(key)
        m = row_metrics(row, cfg)
        if row["metrics"] != m: raise ValueError("saved metrics differ from Q vectors")
        for prefix, count in (("reference", 51), ("batched", 17)):
            if row[prefix + "_counts"] != dict(step_calls=count, forward_calls=count, imagined_transitions=771):
                raise ValueError("call/state accounting mismatch")
            if type(row[prefix + "_action"]) is not int or row[prefix + "_action"] != int(np.argmax(row[prefix + "_q"])):
                raise ValueError("saved selected action mismatch")
        if row["fingerprint_before"] != row["fingerprint_after"]:
            raise ValueError("frozen model/normalizer/context changed")
    if seen != expected: raise ValueError("incomplete planned parity grid")
    return summarize(rows)


def summarize(rows):
    def aggregate(selected):
        return dict(cases=len(selected), action_matches=sum(r["metrics"]["action_equal"] for r in selected),
            ranking_matches=sum(r["metrics"]["ranking_equal"] for r in selected),
            numerical_matches=sum(r["metrics"]["q_within_tolerance"] for r in selected),
            near_ties=sum(r["metrics"]["near_tie"] for r in selected),
            max_absolute_q_difference=max(r["metrics"]["max_absolute_q_difference"] for r in selected),
            minimum_top_gap=min(r["metrics"]["reference_top_gap"] for r in selected))
    groups = dict(pooled=aggregate(rows))
    for field in ("decoder", "task", "visitor", "phase", "context"):
        for value in sorted({r[field] for r in rows}, key=str):
            groups[f'{field}_{value}'] = aggregate([r for r in rows if r[field] == value])
    m = groups["pooled"]
    label = "archived_decision_parity_established_on_tested_inputs" if m["action_matches"] == m["numerical_matches"] == len(rows) else "archived_decision_parity_not_established"
    return dict(groups=groups, label=label)


class Meter:
    def __init__(self, cfg):
        self.deadline = time.perf_counter() + cfg["time_cap_s"]
        self.cap = cfg["imagined_transition_cap"]
        self.calls = self.states = 0
    def check(self):
        if time.perf_counter() >= self.deadline: raise TimeoutError("archived audit cap reached")
    def install(self, model):
        step = model.step
        def guarded(obs, actions):
            self.check()
            n = len(np.asarray(actions).reshape(-1))
            if self.states + n > self.cap: raise RuntimeError("imagined-transition cap reached")
            result = step(obs, actions)
            self.calls += 1; self.states += n
            return result
        model.step = guarded


def run(root, cfg):
    if cfg != load_config(): raise ValueError("runtime configuration differs from locked protocol")
    if OUTPUT.exists(): raise RuntimeError("refusing repeated archived audit/overwrite")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("commit clean protocol before audit")
    subprocess.run(["git", "merge-base", "--is-ancestor", cfg["starting_sha"], "HEAD"], check=True)
    started = time.perf_counter(); meter = Meter(cfg)
    torch.set_num_threads(1)
    payload = dict(complete=False, label="incomplete", rows=[], parents=cfg["parents"],
        implementation_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        config_sha256=common.sha(CONFIG), protocol_sha256=common.sha(PROTOCOL), source_dirty=False,
        new_environment_interactions=0, optimizer_updates=0, historical_controller_changed=False,
        unused_reserved_splits_accessed=False, numpy=np.__version__, torch=torch.__version__, torch_threads=1)
    payload["code_hashes"] = {f: common.sha(f) for f in (
        "scripts/audit_successor_archived_parity.py", "scripts/audit_successor_search_efficiency.py",
        "src/nexus/world/successor_search.py", "src/nexus/world/bellman_backup_control.py")}
    try:
        archive, contexts = inputs(); decoders, students = metadata_records()
        records = list(decoders.values()) + list(students.values())
        verify_records(root, records)
        payload["checkpoint_records"] = records
        unique = set()
        for d in cfg["decoders"]:
            for name in cfg["contexts"]:
                meter.check(); model = load_context_checkpoint(root / decoders[d]["path"])
                if name != "zero": model.encoder.load_state_dict(torch.load(root / students[d, name]["path"], map_location="cpu", weights_only=False))
                model.net.eval(); model.encoder.eval(); meter.install(model)
                for t in cfg["tasks"]:
                    z, expected = saved_context(contexts, d, t, name); model.z = torch.tensor(z)
                    if [frozen_hash(model), context_hash(model)] != expected:
                        raise ValueError("loaded student/decoder/normalizer/context differs from original archive")
                    for visitor, phase in itertools.product(cfg["visitors"], cfg["phases"]):
                        meter.check(); obs, seed = observation(archive[d, t], visitor, phase)
                        unique.add((d, t, obs.tobytes()))
                        seq = candidate_sequences(seed, 16, 16, 3)
                        prepared = PreparedSuccessorSearch(seq, family="pendulum"); before = common.fingerprint(model)
                        (action, q), old_count = common.counted(model, lambda: common.original(model, obs, seq, "pendulum"))
                        result, new_count = common.counted(model, lambda: prepared.score(model, obs))
                        row = dict(decoder=d, task=t, visitor=visitor, phase=phase, context=name,
                            observation=obs.tolist(), candidate_seed=seed,
                            reference_q=q.tolist(), batched_q=result.q.tolist(), reference_action=action,
                            batched_action=result.action, reference_counts=old_count, batched_counts=new_count,
                            fingerprint_before=before, fingerprint_after=common.fingerprint(model))
                        row["metrics"] = row_metrics(row, cfg); payload["rows"].append(row)
                save(OUTPUT, {**payload, "wall_clock_s": time.perf_counter()-started,
                    "counts": dict(model_calls=meter.calls, imagined_transitions=meter.states)})
        payload.update(validate(payload["rows"], cfg))
        verify_records(root, records)
        payload["checkpoint_after_verified"] = len(records)
        payload["unique_archived_observations_inside_decoder_task"] = len(unique)
        if meter.states != cfg["imagined_transition_cap"] or meter.calls != 2160 * 68:
            raise ValueError("inference totals inconsistent")
        meter.check(); payload["complete"] = True
    except Exception as exc:
        payload["label"] = "invalid_or_incomplete_execution"
        payload["failure"] = dict(type=type(exc).__name__, message=str(exc))
    payload["wall_clock_s"] = time.perf_counter() - started
    payload["counts"] = dict(model_calls=meter.calls, imagined_transitions=meter.states)
    save(OUTPUT, payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--checkpoint-root", type=Path, required=True)
    args = parser.parse_args(); cfg = load_config()
    if OUTPUT.exists(): raise RuntimeError("refusing repeated archived audit/overwrite")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip(): raise RuntimeError("commit clean protocol before audit")
    result = run(args.checkpoint_root.resolve(), cfg)
    print(json.dumps({k: result.get(k) for k in ("complete", "label", "wall_clock_s", "counts", "failure")}, indent=2))
    if not result["complete"]: raise SystemExit(1)
