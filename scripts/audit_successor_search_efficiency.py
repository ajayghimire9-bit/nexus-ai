#!/usr/bin/env python3
"""Read-only source-checkpoint parity and microtiming, never environment control.

Outputs are engineering observations on synthetic inputs, not new control data.
An explicit checkpoint audit fails on missing/wrong files; it never trains them.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import subprocess
import time

import numpy as np
import torch
import yaml

from nexus.world import acrobot_lookahead, bellman_backup_control, mountaincar_lookahead
from nexus.world.dynamics import WorldModel
from nexus.world.frozen_dynamics import load_context_checkpoint
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.successor_search import DIMS, PreparedSuccessorSearch

CONFIG = Path("configs/successor_search_efficiency.yaml")
PROTOCOL = Path("docs/NEXUS_SUCCESSOR_SEARCH_EFFICIENCY.md")


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    expected = dict(audit_id="successor_search_exact_batching_v1",
        starting_sha="57cbf25b8a1f93210bce383846d05910248a6517",
        families=list(DIMS), model_seeds=list(range(10)), synthetic_cases_per_context=4,
        pendulum_contexts=["zero", "synthetic_nonzero"], horizon=16, n_candidates=16,
        n_actions=3, q_atol=.0002, q_rtol=.00002, warmup_calls=2, timing_repeats=7,
        decisions_per_timing_repeat=3, audit_cap_s=30, new_environment_interactions=0,
        training_updates=0, controller_comparison_authorized=False, reserved_outcome_access=False)
    if cfg != expected or any(type(cfg[k]) is not type(v) for k, v in expected.items()):
        raise ValueError("locked engineering configuration changed")
    return cfg


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original(model, obs, seq, family):
    if family == "pendulum":
        result = bellman_backup_control.lookahead_first_action(model, obs, seq)
    else:
        module = acrobot_lookahead if family == "acrobot" else mountaincar_lookahead
        result = module.lookahead_first_action(module.make_planner(model), obs, seq)
    return result[0], np.asarray(result[1])


def checkpoint_records():
    # Read checkpoint metadata only, never confirmation outcome artifacts.
    control = yaml.safe_load(Path("configs/control_replication.yaml").read_text())
    manifest = json.loads(Path("artifacts/control_replication_checkpoints/manifest.json").read_text())
    parents = {r["seed"]: r for r in control["parent_checkpoints"]}
    records = []
    for family, seed in itertools.product(DIMS, range(10)):
        if family == "pendulum":
            if seed < 3:
                path, digest = parents[seed]["path"], parents[seed]["sha256"]
            else:
                row = manifest["decoders"][str(seed)]
                path, digest = row["model_path"], row["model_sha256"]
        else:
            cfg = yaml.safe_load(Path(f"configs/{family}_compute_matched.yaml").read_text())
            path = f'{cfg["checkpoint_dir"]}/seed{seed}.pt'
            digest = cfg["checkpoint_sha256"][seed]
        records.append(dict(family=family, seed=seed, path=path, sha256=digest))
    return records


def fingerprint(model):
    h = hashlib.sha256()
    modules = [model.net] + ([model.encoder] if hasattr(model, "encoder") else [])
    for i, module in enumerate(modules):
        for name, value in module.state_dict().items():
            array = value.detach().cpu().numpy()
            h.update(f'{i}:{name}:{array.shape}:{array.dtype}'.encode())
            h.update(array.tobytes())
    for name, value in model.obs_rms.state_dict().items():
        h.update(name.encode()); h.update(np.asarray(value).tobytes())
    h.update(str(model.obs_rms.epsilon).encode())
    if hasattr(model, "z"):
        h.update(model.z.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def synthetic_obs(family, case):
    if family == "pendulum":
        angle = [-1.2, -.1, .4, 2.1][case]
        return np.array([np.cos(angle), np.sin(angle), -.3 + .2 * case], np.float32)
    if family == "acrobot":
        a, b = -.3 + .2 * case, .1 + .15 * case
        return np.array([np.cos(a), np.sin(a), np.cos(b), np.sin(b), .1, -.2], np.float32)
    return np.array([-.55 + .1 * case, -.01 + .005 * case], np.float32)


def counted(model, fn):
    step = model.step
    counts = dict(step_calls=0, forward_calls=0, imagined_transitions=0)
    def wrapped(obs, actions):
        counts["step_calls"] += 1
        counts["imagined_transitions"] += len(np.asarray(obs).reshape(-1, model.net.obs_dim))
        return step(obs, actions)
    def hook(*_):
        counts["forward_calls"] += 1
    handle = model.net.register_forward_hook(hook)
    model.step = wrapped
    try:
        result = fn()
    finally:
        model.step = step
        handle.remove()
    return result, counts


def validate_grid(rows, cfg):
    expected = {(f, s, z, c) for f in cfg["families"] for s in cfg["model_seeds"]
                for z in (cfg["pendulum_contexts"] if f == "pendulum" else ["none"])
                for c in range(cfg["synthetic_cases_per_context"])}
    seen = set()
    for row in rows:
        key = tuple(row[k] for k in ("family", "seed", "context", "case"))
        if type(row["seed"]) is not int or type(row["case"]) is not int or key not in expected or key in seen:
            raise ValueError("duplicate/invalid engineering grid cell")
        seen.add(key)
        for name in ("reference_q", "batched_q"):
            a = np.asarray(row[name])
            if (a.shape != (3,) or any(type(v) not in (int, float) for v in row[name])
                    or a.dtype.kind not in "fi" or not np.isfinite(a).all()):
                raise ValueError("nonfinite or incomplete Q vector")
        if row["reference_counts"] != dict(step_calls=51, forward_calls=51, imagined_transitions=771):
            raise ValueError("reference accounting mismatch")
        if row["batched_counts"] != dict(step_calls=17, forward_calls=17, imagined_transitions=771):
            raise ValueError("batched accounting mismatch")
        for name in ("reference", "batched"):
            if type(row[name + "_action"]) is not int or row[name + "_action"] != int(np.argmax(row[name + "_q"])):
                raise ValueError("action/argmax mismatch")
        if row["fingerprint_before"] != row["fingerprint_after"]:
            raise ValueError("frozen state changed")
        if not np.allclose(row["reference_q"], row["batched_q"], atol=cfg["q_atol"], rtol=cfg["q_rtol"]):
            raise ValueError("numerical parity outside predeclared tolerance")
    if seen != expected:
        raise ValueError("incomplete locked engineering grid")


def run(root, cfg):
    started = time.perf_counter()
    def check():
        if time.perf_counter() - started >= cfg["audit_cap_s"]:
            raise TimeoutError("engineering audit cap reached; no automatic retry")
    torch.set_num_threads(1)
    records = checkpoint_records()
    for r in records:
        path = root / r["path"]
        if not path.is_file() or sha(path) != r["sha256"]:
            raise RuntimeError(f"required source checkpoint missing or wrong: {path}")
    p = dict(complete=False, rows=[], timings=[], checkpoint_records=records,
             checkpoint_root=str(root), config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL),
             implementation_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
             source_dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
             numpy=np.__version__, torch=torch.__version__, torch_threads=1,
             new_environment_interactions=0, training_updates=0, reserved_outcomes_accessed=False)
    p["source_hashes"] = {str(path): sha(path) for path in (
        Path("src/nexus/world/successor_search.py"), Path("scripts/audit_successor_search_efficiency.py"),
        Path("src/nexus/world/planning.py"), Path("src/nexus/world/dynamics.py"),
        Path("src/nexus/world/context_model.py"), Path("src/nexus/world/rewards.py"),
        Path("src/nexus/world/bellman_backup_control.py"), Path("src/nexus/world/acrobot_lookahead.py"),
        Path("src/nexus/world/mountaincar_lookahead.py"))}
    p["checkpoint_metadata_hashes"] = {str(path): sha(path) for path in (
        Path("configs/control_replication.yaml"), Path("artifacts/control_replication_checkpoints/manifest.json"),
        Path("configs/acrobot_compute_matched.yaml"), Path("configs/mountaincar_compute_matched.yaml"))}
    try:
        for r in records:
            check(); family, seed = r["family"], r["seed"]
            # The historical .pt payload predates the generic reconstruction metadata.
            # Use the same legacy 48x48/8/32 loader as its original controller.
            model = load_context_checkpoint(root / r["path"]) if family == "pendulum" else WorldModel.load(root / r["path"])
            model.net.eval()
            contexts = cfg["pendulum_contexts"] if family == "pendulum" else ["none"]
            for context, case in itertools.product(contexts, range(cfg["synthetic_cases_per_context"])):
                check()
                if family == "pendulum":
                    model.z = torch.zeros(8) if context == "zero" else torch.linspace(-.2, .2, 8)
                    model.encoder.eval()
                before = fingerprint(model)
                obs = synthetic_obs(family, case); seq = candidate_sequences(case, 16, 16, 3)
                prepared = PreparedSuccessorSearch(seq, family=family)
                (action, q), old_counts = counted(model, lambda: original(model, obs, seq, family))
                result, new_counts = counted(model, lambda: prepared.score(model, obs))
                p["rows"].append(dict(family=family, seed=seed, context=context, case=case,
                    reference_q=q.tolist(), batched_q=result.q.tolist(), reference_action=action,
                    batched_action=result.action, reference_counts=old_counts, batched_counts=new_counts,
                    fingerprint_before=before, fingerprint_after=fingerprint(model)))
            if seed == 0:
                # Isolate scoring, prepared candidates excluded for both paths.
                obs = synthetic_obs(family, 0); seq = candidate_sequences(0, 16, 16, 3)
                prepared = PreparedSuccessorSearch(seq, family=family)
                methods = dict(reference=lambda: original(model, obs, seq, family),
                               batched=lambda: prepared.score(model, obs))
                for fn in methods.values():
                    for _ in range(cfg["warmup_calls"]): check(); fn()
                times = {name: [] for name in methods}
                for i in range(cfg["timing_repeats"]):
                    for name in (list(methods) if i % 2 == 0 else list(reversed(methods))):
                        check(); t = time.perf_counter()
                        for _ in range(cfg["decisions_per_timing_repeat"]): methods[name]()
                        times[name].append((time.perf_counter() - t) / cfg["decisions_per_timing_repeat"])
                med = {k: statistics.median(v) for k, v in times.items()}
                p["timings"].append(dict(family=family, seconds_per_decision=times, medians=med,
                    speedup=med["reference"] / med["batched"], context=context))
        validate_grid(p["rows"], cfg)
        for r in records:
            if sha(root / r["path"]) != r["sha256"]: raise ValueError("checkpoint changed")
        check(); p["complete"] = True
    except Exception as exc:
        p["failure"] = dict(type=type(exc).__name__, message=str(exc))
    p["wall_clock_s"] = time.perf_counter() - started
    p["actions_identical"] = sum(r["reference_action"] == r["batched_action"] for r in p["rows"])
    p["rankings_identical"] = sum(np.array_equal(np.argsort(r["reference_q"], kind="stable"),
        np.argsort(r["batched_q"], kind="stable")) for r in p["rows"])
    p["max_absolute_q_difference"] = max((float(np.max(np.abs(np.array(r["reference_q"]) - r["batched_q"]))) for r in p["rows"]), default=0.)
    p["decision_parity_passed"] = p["complete"] and p["actions_identical"] == len(p["rows"]) and p["rankings_identical"] == len(p["rows"])
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise RuntimeError("refusing overwrite")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("commit the implementation and audit protocol before checkpoint scoring")
    cfg = load_config()
    result = run(args.checkpoint_root.resolve(), cfg)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("complete", "wall_clock_s", "actions_identical", "rankings_identical", "max_absolute_q_difference")}))
    if not result["complete"]: raise SystemExit(1)
