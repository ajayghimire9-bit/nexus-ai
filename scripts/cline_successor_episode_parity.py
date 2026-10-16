#!/usr/bin/env python3
"""Strict serial-versus-batched full-episode successor implementation parity.

Implements docs/NEXUS_SUCCESSOR_EPISODE_PARITY_PROPOSAL.md. Collection is
blocked until the committed allocation record is explicitly authorized by the
user. Never trains, retunes, prunes, or changes any default controller.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
import yaml

import audit_successor_archived_parity as audit
import audit_successor_search_efficiency as common
from nexus.tasks.pendulum_family import pendulum_context_development, pendulum_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world.frozen_dynamics import load_context_checkpoint
from nexus.world.long_continuation_execution import context_hash, frozen_hash
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.successor_search import PreparedSuccessorSearch
from nexus.world.terminal_value_execution import save

CONFIG = Path("configs/cline_successor_episode_parity.yaml")
PROTOCOL = Path("docs/NEXUS_SUCCESSOR_EPISODE_PARITY_CLINE_PROTOCOL.md")
ALLOCATION = Path("configs/cline_successor_episode_parity_allocation.json")
OUTPUT = Path("artifacts/cline_successor_episode_parity.json")
AUDIT = Path("artifacts/cline_successor_episode_parity_offline_audit.json")
REGISTRIES = ("action_conditioned_q", "capacity_matched_q", "bellman_backup_control",
    "receding_policy_consistency", "same_set_planning", "horizon_alignment",
    "decision_aware_world_model", "late_episode_decision_trajectory",
    "pendulum_compute_matched", "lookahead_transfer_confirmation",
    "mountaincar_compute_matched", "acrobot_compute_matched",
    "tree_reuse_lookahead", "prefix_max_tree_reuse", "terminal_value", "planning_value")


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    fixed = dict(audit_id="cline_successor_episode_parity_v1",
        starting_sha="70deb7b3f61d524d4c2493dd834898f4f4e38bc6",
        decoders=list(range(10)), tasks=[0, 1, 2], contexts=["student", "zero"],
        implementations=["serial", "batched"], episode_steps=200, horizon=16,
        n_candidates=16, n_actions=3, q_atol=.0002, q_rtol=.00002, reward_atol=1e-8,
        time_cap_s=180, env_cap=24000, imagined_cap=18504000, model_call_cap=816000,
        reset_base=61000000, step_seed_base=61100000, training_updates=0,
        controller_integration=False)
    for key, value in fixed.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError("locked episode-parity configuration changed")
    if cfg["eval_task_ids"] != [s.task_id for s in pendulum_context_development()]:
        raise ValueError("development physics changed")
    if cfg["eval_physics"] != [list(pendulum_physics_key(s)) for s in pendulum_context_development()]:
        raise ValueError("development physics values changed")
    for file, digest in cfg["parents"].items():
        if common.sha(file) != digest:
            raise ValueError(f"closed parent changed: {file}")
    budget(cfg); check_seeds(cfg)
    return cfg


def reset_seed(cfg, d, t):
    return cfg["reset_base"] + 100 * d + t


def step_seed(cfg, d, t, k):
    # No implementation, context or visitor factor: coupled across all arms.
    return cfg["step_seed_base"] + 10000 * d + 1000 * t + k


def seed_groups(cfg):
    return [
        {reset_seed(cfg, d, t) for d, t in itertools.product(range(10), range(3))},
        {step_seed(cfg, d, t, k) for d, t, k in
         itertools.product(range(10), range(3), range(200))},
    ]


def check_seeds(cfg):
    blocked = set()
    for name in REGISTRIES:
        module = importlib.import_module(f"nexus.world.{name}")
        other = yaml.safe_load(module.CONFIG.read_text())
        blocked |= set().union(*module.seed_groups(other))
    groups = seed_groups(cfg)
    if [len(g) for g in groups] != [30, 6000]:
        raise ValueError("duplicate registered episode-parity seeds")
    used = set().union(*groups)
    if used & blocked:
        raise ValueError("episode-parity seeds collide with a closed experiment")
    if min(used) < cfg["reset_base"]:
        raise ValueError("seed block drifted below the locked base")
    return blocked


def budget(cfg):
    counts = dict(env_steps=60 * 2 * 200, imagined_transitions=24000 * 771,
                  model_calls=12000 * 51 + 12000 * 17)
    if (counts["env_steps"] != cfg["env_cap"]
            or counts["imagined_transitions"] != cfg["imagined_cap"]
            or counts["model_calls"] != cfg["model_call_cap"]):
        raise ValueError("episode-parity resource allocation mismatch")
    return counts


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(config_sha256=common.sha(CONFIG),
            protocol_sha256=common.sha(PROTOCOL), time_cap_s=180, env_cap=24000,
            imagined_cap=18504000, model_call_cap=816000, runs=1).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError("episode-parity allocation drift")
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get("authorized") is not True or int(record.get("runs", 0)) != 1:
        raise PermissionError("fresh human approval required before episode collection")
    if cfg["time_cap_s"] != record["time_cap_s"] or cfg["env_cap"] != record["env_cap"]:
        raise ValueError("allocation does not bind the locked configuration")


class Meter:
    def __init__(self, cfg):
        self.deadline = time.perf_counter() + cfg["time_cap_s"]
        self.cap = cfg["imagined_cap"]
        self.env_cap = cfg["env_cap"]
        self.calls = self.transitions = self.env_steps = 0

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError("episode-parity time cap reached")

    def score(self, model, fn):
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
        try:
            return fn()
        finally:
            model.step = step

    def env_step(self):
        self.check()
        self.env_steps += 1
        if self.env_steps > self.env_cap:
            raise RuntimeError("env-step cap reached")


def rollout(env, model, cfg, d, t, batched, meter):
    obs = np.asarray(env.reset(seed=reset_seed(cfg, d, t))[0], dtype=np.float32)
    steps = []; terminated = truncated = False
    for k in range(cfg["episode_steps"]):
        if terminated or truncated:
            raise ValueError("trajectory ended before TimeLimit")
        meter.check()
        seed = step_seed(cfg, d, t, k)
        seq = candidate_sequences(int(seed), cfg["horizon"], cfg["n_candidates"], 3)
        before = (meter.calls, meter.transitions)
        if batched:
            prepared = PreparedSuccessorSearch(seq, family="pendulum")
            result = meter.score(model, lambda: prepared.score(model, obs))
            action, q = result.action, result.q
        else:
            action, q = meter.score(model, lambda: common.original(model, obs, seq, "pendulum"))
        delta = (meter.calls - before[0], meter.transitions - before[1])
        if delta != ((17, 771) if batched else (51, 771)):
            raise ValueError("per-step call accounting changed")
        nxt, reward, terminated, truncated, _ = env.step(int(action))
        meter.env_step()
        nxt = np.asarray(nxt, dtype=np.float32)
        steps.append(dict(obs=obs.tolist(), candidate_seed=int(seed), action=int(action),
                          q=[float(x) for x in q], reward=float(reward)))
        obs = nxt
    if len(steps) != 200 or terminated or (not truncated):
        raise ValueError("episode did not truncate at 200")
    return steps

def first_divergence(a, b):
    aa = list(map(int, a)); bb = list(map(int, b))
    if len(aa) != len(bb):
        raise ValueError("trace length mismatch")
    for i, (x, y) in enumerate(zip(aa, bb)):
        if x != y:
            return i
    return None


def cell_metrics(cell, cfg):
    serial = cell["implementations"]["serial"]
    batched = cell["implementations"]["batched"]
    if len(serial) != 200 or len(batched) != 200:
        raise ValueError("episode trace length drifted")
    mismatch = first_divergence([s["action"] for s in serial],
                                [s["action"] for s in batched])
    q_dev = max(max(abs(a - b) for a, b in zip(s["q"], t["q"]))
                for s, t in zip(serial, batched))
    within_q = all(abs(a - b) <= cfg["q_atol"] + cfg["q_rtol"] * abs(b)
                   for s, t in zip(serial, batched) for a, b in zip(s["q"], t["q"]))
    rew_dev = max(abs(s["reward"] - t["reward"]) for s, t in zip(serial, batched))
    ret_s = float(math.fsum(s["reward"] for s in serial))
    ret_b = float(math.fsum(t["reward"] for t in batched))
    return dict(actions_identical=mismatch is None,
        first_divergence=(200 if mismatch is None else int(mismatch)),
        max_q_deviation=q_dev, q_within_tolerance=within_q,
        max_reward_deviation=rew_dev, return_serial=ret_s, return_batched=ret_b,
        return_deviation=abs(ret_s - ret_b),
        rewards_within_tolerance=(rew_dev <= cfg["reward_atol"]
            and abs(ret_s - ret_b) <= cfg["reward_atol"]))


def summarize(cells, cfg):
    keys = {(c["decoder"], c["task"], c["context"]) for c in cells}
    expected = {(d, t, n) for d in cfg["decoders"] for t in cfg["tasks"]
                for n in cfg["contexts"]}
    if keys != expected:
        raise ValueError("incomplete planned episode-parity grid")
    ok = all(c["metrics"]["actions_identical"] and c["metrics"]["q_within_tolerance"]
             and c["metrics"]["rewards_within_tolerance"] for c in cells)
    label = ("episode_implementation_parity_established_on_tested_grid" if ok
             else "episode_implementation_parity_not_established")
    return dict(label=label, pooled=dict(cells=len(cells),
        identical_action_cells=sum(c["metrics"]["actions_identical"] for c in cells),
        divergent_cells=[dict(decoder=c["decoder"], task=c["task"], context=c["context"],
            first_divergence=c["metrics"]["first_divergence"])
            for c in cells if not c["metrics"]["actions_identical"]],
        max_q_deviation=max(c["metrics"]["max_q_deviation"] for c in cells),
        max_reward_deviation=max(c["metrics"]["max_reward_deviation"] for c in cells),
        max_return_deviation=max(c["metrics"]["return_deviation"] for c in cells)))


def execute(checkpoint_root):
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError("refusing episode-parity overwrite")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("commit clean protocol before collection")
    subprocess.run(["git", "merge-base", "--is-ancestor", cfg["starting_sha"], "HEAD"], check=True)
    started = time.perf_counter(); meter = Meter(cfg)
    torch.set_num_threads(1)
    archive, contexts = audit.inputs()
    decoders, students = audit.metadata_records()
    records = list(decoders.values()) + list(students.values())
    audit.verify_records(checkpoint_root, records)
    specs = list(pendulum_context_development())
    payload = dict(complete=False, label="incomplete", cells=[], parents=cfg["parents"],
        implementation_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        config_sha256=common.sha(CONFIG), protocol_sha256=common.sha(PROTOCOL),
        allocation_sha256=common.sha(ALLOCATION), checkpoint_root=str(checkpoint_root),
        source_dirty=False, new_environment_interactions=cfg["env_cap"],
        optimizer_updates=0, historical_controller_changed=False,
        unused_reserved_splits_accessed=False, numpy=np.__version__,
        torch=torch.__version__, torch_threads=1)
    payload["code_hashes"] = {f: common.sha(f) for f in (
        "scripts/cline_successor_episode_parity.py",
        "scripts/audit_successor_archived_parity.py",
        "scripts/audit_successor_search_efficiency.py",
        "src/nexus/world/successor_search.py",
        "src/nexus/world/bellman_backup_control.py")}
    try:
        for d in cfg["decoders"]:
            for t in cfg["tasks"]:
                for name in cfg["contexts"]:
                    meter.check()
                    student = "zero" if name == "zero" else str((d + t) % 5)
                    z, fingerprints = audit.saved_context(contexts, d, t, student)
                    model = load_context_checkpoint(checkpoint_root / decoders[d]["path"])
                    if name == "student":
                        model.encoder.load_state_dict(torch.load(
                            checkpoint_root / students[d, student]["path"],
                            map_location="cpu", weights_only=False))
                    model.net.eval(); model.encoder.eval()
                    model.z = torch.tensor(z)
                    if [frozen_hash(model), context_hash(model)] != fingerprints:
                        raise ValueError("loaded student/decoder/normalizer/context differs from the original archive")
                    cell = dict(decoder=d, task=t, context=name, student=student,
                        reset_seed=reset_seed(cfg, d, t),
                        context_sha256=hashlib.sha256(np.asarray(z, dtype=np.float32).tobytes()).hexdigest(),
                        fingerprint_before=common.fingerprint(model), implementations={})
                    for impl in cfg["implementations"]:
                        env = make_task_env(specs[t])
                        try:
                            cell["implementations"][impl] = rollout(
                                env, model, cfg, d, t, impl == "batched", meter)
                        finally:
                            env.close()
                    cell["metrics"] = cell_metrics(cell, cfg)
                    if common.fingerprint(model) != cell["fingerprint_before"]:
                        raise RuntimeError("frozen model/context drift")
                    payload["cells"].append(cell)
        payload.update(summarize(payload["cells"], cfg))
        audit.verify_records(checkpoint_root, records)
        payload["checkpoint_after_verified"] = len(records)
        if (meter.env_steps != cfg["env_cap"] or meter.transitions != cfg["imagined_cap"]
                or meter.calls != cfg["model_call_cap"]):
            raise ValueError("execution totals inconsistent with the locked budget")
        meter.check(); payload["complete"] = True
    except Exception as exc:
        payload["label"] = "invalid_or_incomplete_execution"
        payload["failure"] = dict(type=type(exc).__name__, message=str(exc))
    payload["wall_clock_s"] = time.perf_counter() - started
    payload["counts"] = dict(env_steps=meter.env_steps, model_calls=meter.calls,
                             imagined_transitions=meter.transitions)
    save(OUTPUT, payload)
    return payload


def offline_audit():
    cfg = load_config()
    record = load_allocation()
    report = dict(complete=True, new_environment_steps=0, new_imagined_transitions=0,
        new_model_calls=0, authorized=record.get("authorized") is True,
        config_sha256=common.sha(CONFIG), protocol_sha256=common.sha(PROTOCOL),
        allocation_sha256=common.sha(ALLOCATION), proposed_budget=budget(cfg),
        registered_seed_block=[cfg["reset_base"], cfg["step_seed_base"]],
        closed_registry_modules=list(REGISTRIES), training_updates=0,
        controller_integration=False, confirmation_used=False)
    save(AUDIT, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", type=Path)
    parser.add_argument("--offline-audit", action="store_true")
    args = parser.parse_args()
    if args.offline_audit:
        print(json.dumps(offline_audit(), indent=2))
    else:
        if args.checkpoint_root is None:
            parser.error("--checkpoint-root is required for collection")
        result = execute(args.checkpoint_root.resolve())
        print(json.dumps({k: result.get(k) for k in
            ("complete", "label", "wall_clock_s", "counts", "failure")}, indent=2))
        if not result["complete"]:
            raise SystemExit(1)


