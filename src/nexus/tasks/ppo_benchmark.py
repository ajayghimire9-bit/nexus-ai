"""Locked scratch-PPO pilot over existing TaskSpec, PPOTrainer and Host.

No replacement learning algorithm, controller, memory or resource ledger.
No scientific execution on import. Tests inject authored environments only.
"""
from __future__ import annotations

from dataclasses import asdict
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
from gymnasium.vector import AutoresetMode

from nexus.config import PPOConfig, ArchitectureConfig
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.benchmark import (FAMILIES, MeteredTaskEnv, fingerprint,
    ppo_binding, evaluate_policy, validate_results, summarize_results, paired_comparison)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def historical_snapshot(root, revision):
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision, "--", "artifacts"], cwd=root, text=True).splitlines()
    hashes = {name: file_hash(Path(root) / name) for name in paths if name.endswith(".json")}
    return dict(count=len(hashes), sorted_hash_map_sha256=fingerprint(hashes))


def parameter_hash(agent):
    h = hashlib.sha256()
    for name, value in sorted(agent.state_dict().items()):
        a = value.detach().cpu().numpy()
        h.update(name.encode()); h.update(str((a.shape, a.dtype)).encode()); h.update(a.tobytes())
    return h.hexdigest()


def job_seeds(c, family, replicate):
    base = c["seed_base"] + c["families"].index(family) * 10000 + c["replicates"].index(replicate) * 100
    return dict(model=base, train_reset=base + 10,
                evaluation=[base + 20, base + 21], random_policy=[base + 30, base + 31])


def all_seeds(c):
    values = []
    for f, r in itertools.product(c["families"], c["replicates"]):
        s = job_seeds(c, f, r)
        values += [s["model"], s["train_reset"], *s["evaluation"], *s["random_policy"]]
    if len(values) != len(set(values)):
        raise ValueError("seed_role_collision")
    return set(values)


def bounds(c):
    models = len(c["families"]) * len(c["replicates"])
    train = models * c["training_interactions"]
    evaluation = sum(FAMILIES[f].max_episode_steps for f in c["families"]) * len(c["replicates"]) * len(c["methods"]) * c["evaluation_episodes"]
    # collect: action, successor value, and at most one timeout value per row.
    iterations = c["training_interactions"] // c["ppo"]["num_steps"]
    optimizer = models * iterations * c["ppo"]["update_epochs"] * c["ppo"]["num_minibatches"]
    policy_eval = evaluation // len(c["methods"])
    return dict(training_real=train, evaluation_real_upper=evaluation, real_upper=train + evaluation,
        optimizer_steps=optimizer,
        policy_trunk_calls_upper=3 * train + optimizer + policy_eval,
        policy_trunk_rows_upper=3 * train + optimizer * (c["ppo"]["num_steps"] // c["ppo"]["num_minibatches"]) + policy_eval)


def validate_config(c):
    if (c["version"] != "e4_five_family_ppo_v1" or c["families"] != list(FAMILIES)
            or c["replicates"] != ["learner_0", "learner_1", "learner_2"]
            or c["methods"] != ["ppo_scratch", "random", "fixed"] or c["cases"] != ["source_new_reset"]):
        raise ValueError("locked_family_seed_method_grid")
    for key, value in dict(training_interactions=4096, evaluation_episodes=2, time_cap_s=300,
                           active_stop_s=290, real_cap=84840, imagined_cap=0,
                           model_call_cap=0, network_forward_cap=0).items():
        if type(c[key]) is not int or c[key] != value:
            raise ValueError("locked_compute_recipe")
    p = asdict(PPOConfig(num_envs=1, total_timesteps=4096, device="cpu"))
    for key in ("env_id", "seed"):
        p.pop(key)
    if c["ppo"] != p or c["architecture"] != asdict(ArchitectureConfig()):
        # JSON stores tuple as list.
        expected_arch = json.loads(json.dumps(asdict(ArchitectureConfig())))
        if c["ppo"] != p or c["architecture"] != expected_arch:
            raise ValueError("one_locked_PPO_algorithm")
    if c["autoreset"] != "SameStep" or c["policy_evaluation"] != "categorical_argmax":
        raise ValueError("locked_collection_evaluation_rule")
    if (c["tasks"] != {f: asdict(v.spec("e4_source_" + f, split="train")) for f, v in FAMILIES.items()}
            or c["contract_hashes"] != {f: v.signature() for f, v in FAMILIES.items()}):
        raise ValueError("locked_default_source_physics_and_wrappers")
    if c["training_interactions"] % p["num_steps"]:
        raise ValueError("no_rollout_overshoot")
    if bounds(c)["real_upper"] != c["real_cap"] or c["allocation_runs"] != 1:
        raise ValueError("allocation_upper_bound")
    if any(type(v) not in (int, float) or v <= 0 or not math.isfinite(v) for v in c["margins"].values()) or set(c["margins"]) != set(FAMILIES):
        raise ValueError("locked_family_margins")
    if (type(c["seed_base"]) is not int or not 0 <= c["seed_base"] < 2**32 - 50000
            or len(all_seeds(c)) != 90):
        raise ValueError("bounded_seed_registration")
    return True


class RecordedTaskEnv(MeteredTaskEnv):
    """Raw transition observer over the SAME metered world, not another meter."""
    def __init__(self, spec, host, journal, identity, **kwargs):
        self.journal = journal
        self.identity = identity
        self.episode = -1
        self.last = None
        self.tick = 0
        self.real_steps = 0
        super().__init__(spec, host, **kwargs)

    def emit(self, kind, **payload):
        self.journal.write((json.dumps(dict(kind=kind, identity=self.identity,
            episode=self.episode, **payload), allow_nan=False, separators=(",", ":")) + "\n").encode())

    def reset(self, **kwargs):
        obs, info = super().reset(**kwargs)
        self.episode += 1
        self.last = np.array(obs, copy=True)
        self.tick = 0
        self.emit("reset", seed=kwargs.get("seed"), observation=obs.tolist())
        return obs, info

    def step(self, action):
        before = self.last.copy()
        obs, reward, term, trunc, info = super().step(action)
        self.real_steps += 1
        self.emit("transition", tick=self.tick, observation=before.tolist(), action=int(action),
                  next_observation=obs.tolist(), reward=reward, terminated=term, truncated=trunc)
        self.last = np.array(obs, copy=True)
        self.tick += 1
        return obs, reward, term, trunc, info


class PolicyCounters:
    """PPO-specific hook counters, NOT imagined world-model transitions.

    Existing E1 model operations require imagined rows and must not be misused
    for actor/critic inference on real observations. Enforce proven upper bounds
    here; environment spending stays owned by the original Host/ledger.
    """
    def __init__(self, c):
        self.upper = bounds(c)
        self.counts = dict(trunk_calls=0, trunk_rows=0, policy_head_calls=0, value_head_calls=0, optimizer_steps=0)
        self.phase = "training"
        self.phases = {p: dict(trunk_calls=0, trunk_rows=0) for p in ("training", "evaluation")}

    def attach(self, agent, optimizer=None):
        def trunk(module, args):
            rows = int(args[0].shape[0])
            if (self.counts["trunk_calls"] + 1 > self.upper["policy_trunk_calls_upper"]
                    or self.counts["trunk_rows"] + rows > self.upper["policy_trunk_rows_upper"]):
                raise ValueError("policy_forward_cap")
            self.counts["trunk_calls"] += 1; self.counts["trunk_rows"] += rows
            self.phases[self.phase]["trunk_calls"] += 1; self.phases[self.phase]["trunk_rows"] += rows
        handles = [agent.backbone.register_forward_pre_hook(trunk)]
        for attr in ("policy_head", "value_head"):
            def count(module, args, key=attr + "_calls"):
                self.counts[key] += 1
            handles.append(getattr(agent, attr).register_forward_pre_hook(count))
        if optimizer is not None:
            def pre_step(optimizer, args, kwargs):
                if self.counts["optimizer_steps"] >= self.upper["optimizer_steps"]:
                    raise ValueError("optimizer_step_cap")
                self.counts["optimizer_steps"] += 1
            handles.append(optimizer.register_step_pre_hook(pre_step))
        return handles


def training_kwargs(c, spec, host, seed):
    kwargs = ppo_binding(spec, host, seed=seed, total_timesteps=c["training_interactions"])
    kwargs["ppo"] = PPOConfig(**c["ppo"], env_id=spec.gym_id, seed=seed)
    kwargs["architecture"] = ArchitectureConfig(**c["architecture"])
    return kwargs


def collect_update(trainer, env, *, before_steps):
    """Same PPO methods, explicitly verify every rollout slot was a real step."""
    batch, rollout = trainer.collect()
    size = trainer.ppo.num_steps
    if env.real_steps - before_steps != size or not bool((batch["valid"] == 1).all()):
        raise ValueError("same_step_real_interaction_accounting")
    metrics = trainer.update(batch)
    for key in ("policy_loss", "value_loss", "entropy", "clipfrac"):
        if not math.isfinite(metrics[key]):
            raise ValueError("nonfinite_required_training_metric")
    if any(not torch.isfinite(p).all() for p in trainer.agent.parameters()):
        raise ValueError("nonfinite_parameters")
    if not math.isfinite(metrics["explained_variance"]):
        metrics["explained_variance"] = None
        metrics["explained_variance_missing_reason"] = "optional_degenerate_return_variance"
    if rollout["rollout_episodes"] == 0:
        rollout["rollout_mean_return"] = None
    trainer._num_updates += 1
    trainer._timesteps_done += size
    return dict(iteration=trainer._num_updates, real_steps=env.real_steps,
                **rollout, **metrics)


def evaluate(c, agent, spec, host, journal, identity, *, reset_seed, policy_seed, method):
    if method not in c["methods"]:
        raise ValueError("registered_method_required")
    rng = np.random.default_rng(policy_seed)
    def policy(obs, unused_rng, n_actions):
        if method == "random":
            return int(rng.integers(n_actions))
        if method == "fixed":
            return 0
        with torch.no_grad():
            actor, _ = agent._features(torch.as_tensor(obs, dtype=torch.float32).reshape(1, -1))
            return int(agent.policy_head(actor).argmax(-1).item())
    t0, cpu0 = time.perf_counter(), time.process_time()
    with RecordedTaskEnv(spec, host, journal, identity) as env:
        trajectory = evaluate_policy(env, policy, seed=reset_seed, max_steps=env.contract.max_episode_steps)
    if trajectory["collector_cutoff"]:
        raise ValueError("full_evaluation_episode_required")
    return dict(reset_seed=reset_seed, random_policy_seed=policy_seed,
        raw_return=trajectory["raw_return"], length=len(trajectory["steps"]),
        initial_observation=trajectory["steps"][0]["observation"],
        terminated=trajectory["steps"][-1]["terminated"], truncated=trajectory["steps"][-1]["truncated"],
        trajectory_hash=fingerprint(trajectory), wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - cpu0)


def validate_complete(p, c):
    validate_config(c)
    validate_results(p["rows"], c)
    ids = [(m["family"], m["replicate"]) for m in p["models"]]
    expected = set(itertools.product(c["families"], c["replicates"]))
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError("complete_independent_model_grid")
    for model in p["models"]:
        if (len(model["history"]) != 32 or model["training_real_steps"] != 4096
                or model["optimizer_steps"] != 512 or model["initial_hash"] == model["fitted_hash"]
                or model["fitted_hash"] != model["after_evaluation_hash"]
                or len(model["checkpoint_sha256"]) != 64):
            raise ValueError("complete_finite_frozen_trained_models")
        for row in model["history"]:
            for key in ("policy_loss", "value_loss", "entropy", "clipfrac"):
                if type(row[key]) not in (int, float) or not math.isfinite(row[key]):
                    raise ValueError("finite_training_history")
    initial = [m["initial_hash"] for m in p["models"]]
    if len(set(initial)) != len(initial):
        raise ValueError("distinct_initializations_required")
    total_eval = 0
    for family, replicate in expected:
        selected = [r for r in p["rows"] if (r["family"], r["replicate"]) == (family, replicate)]
        seeds = job_seeds(c, family, replicate)
        for row in selected:
            episodes = row["episodes"]
            if len(episodes) != 2 or [e["reset_seed"] for e in episodes] != seeds["evaluation"]:
                raise ValueError("complete_paired_evaluation_episodes")
            for e in episodes:
                if (type(e["raw_return"]) not in (int, float) or not math.isfinite(e["raw_return"])
                        or type(e["length"]) is not int or not 1 <= e["length"] <= FAMILIES[family].max_episode_steps
                        or not (e["terminated"] or e["truncated"])):
                    raise ValueError("finite_complete_episode")
            if row["metrics"]["raw_return"] != sum(e["raw_return"] for e in episodes) / 2 or row["metrics"]["real_steps"] != sum(e["length"] for e in episodes):
                raise ValueError("episode_aggregation_accounting")
            total_eval += row["metrics"]["real_steps"]
        for i in range(2):
            if len({fingerprint(r["episodes"][i]["initial_observation"]) for r in selected}) != 1:
                raise ValueError("paired_initial_states")
    complete = p["resources"]["completed"]
    if (complete != dict(real_steps=61440 + total_eval, imagined_transitions=0, model_calls=0, network_forwards=0)
            or any(p["resources"]["unknown_upper"].values()) or complete["real_steps"] > c["real_cap"]
            or p["policy_compute"]["counts"]["optimizer_steps"] != bounds(c)["optimizer_steps"]):
        raise ValueError("physical_resource_reconciliation")
    return True


def analyze(p, c):
    validate_complete(p, c)
    summary = summarize_results(p["rows"], c)
    families = {}
    for family in c["families"]:
        contrasts = {b: paired_comparison(p["rows"], c, family=family, case=c["cases"][0],
            treatment="ppo_scratch", baseline=b) for b in ("random", "fixed")}
        passed = all(v["interval"]["mean"] >= c["margins"][family] and v["interval"]["lo"] > 0 for v in contrasts.values())
        families[family] = dict(contrasts=contrasts, practical_margin=c["margins"][family], screen_passed=passed)
    return dict(summaries=summary, families=families,
        label="five_family_scratch_pilot_screen_passed" if all(v["screen_passed"] for v in families.values()) else "five_family_scratch_learning_not_established",
        inference="Exploratory df2 learner-seed intervals; default/source physics, no transfer or learning-to-learn claim.")


def audit_journals(p, root, *, deadline):
    """Independent saved-data accounting, no environment/model construction."""
    from nexus.evolution1.fixtures import Event, verify_journal
    def records(prefix):
        for entry in p["journals"]:
            if not Path(entry["path"]).name.startswith(prefix): continue
            with gzip.open(Path(root) / entry["path"], "rt") as stream:
                for line in stream:
                    if time.perf_counter() >= deadline:
                        raise TimeoutError("combined_execution_and_audit_budget")
                    yield json.loads(line)
    raw, pending, ends = {}, {}, {}
    def transitions():
        for row in records("e4_ppo_transitions"):
            identity = row["identity"]
            key = fingerprint(identity)
            if row["kind"] == "reset":
                pending[key] = dict(last=row["observation"], tick=0, reward=0., count=0, episode=row["episode"])
                continue
            state = pending[key]
            if (row["kind"] != "transition" or row["observation"] != state["last"]
                    or row["tick"] != state["tick"] or row["episode"] != state["episode"]):
                raise ValueError("raw_transition_continuity")
            family = identity["family"]
            if (len(row["next_observation"]) != FAMILIES[family].obs_dim
                    or not np.isfinite(row["observation"]).all() or not np.isfinite(row["next_observation"]).all()
                    or type(row["reward"]) not in (int, float) or not math.isfinite(row["reward"])
                    or type(row["action"]) is not int or not 0 <= row["action"] < len(FAMILIES[family].action_values)
                    or type(row["terminated"]) is not bool or type(row["truncated"]) is not bool):
                raise ValueError("raw_finite_typed_transition")
            state.update(last=row["next_observation"], tick=state["tick"] + 1,
                         reward=state["reward"] + row["reward"], count=state["count"] + 1)
            unit = (identity["role"], family, identity["replicate"], identity["method"])
            raw[unit] = raw.get(unit, 0) + 1
            if row["terminated"] or row["truncated"]:
                if identity["role"] == "evaluation":
                    k = (family, identity["replicate"], identity["method"], identity["evaluation_episode"])
                    if k in ends: raise ValueError("duplicate_raw_evaluation_episode")
                    ends[k] = dict(raw_return=state["reward"], length=state["count"])
            yield row
    receipts = 0
    for receipt, transition in itertools.zip_longest(records("e4_ppo_resources"), transitions()):
        if receipt is None or transition is None:
            raise ValueError("one_receipt_per_actual_transition")
        report, identity = receipt["report"], transition["identity"]
        if (report["status"] != "complete_execution" or any(report["physical_unknown_upper_bound"].values())
                or report["physical_completed_reported"] != dict(real_steps=1, imagined_transitions=0, model_calls=0, network_forwards=0)
                or receipt["meta"]["family"] != identity["family"]
                or receipt["meta"]["split"] != ("train" if identity["role"] == "training" else "development")):
            raise ValueError("actual_receipt_resource_or_role_mismatch")
        events = tuple(Event(**e) for e in report["events"])
        verify_journal(events, events[-1].fingerprint, len(events))
        receipts += 1
    if receipts != p["resources"]["completed"]["real_steps"]:
        raise ValueError("raw_physical_total_mismatch")
    for m in p["models"]:
        if raw[("training", m["family"], m["replicate"], "ppo_scratch")] != 4096:
            raise ValueError("raw_training_grid_mismatch")
    for row in p["rows"]:
        for i, episode in enumerate(row["episodes"]):
            actual = ends[(row["family"], row["replicate"], row["method"], i)]
            if actual["length"] != episode["length"] or not math.isclose(actual["raw_return"], episode["raw_return"], rel_tol=0, abs_tol=1e-8):
                raise ValueError("independent_raw_return_mismatch")
    if len(ends) != 90:
        raise ValueError("raw_complete_ninety_episodes")
    return dict(receipts=receipts, evaluation_episodes=len(ends), raw_returns_reconstructed=True,
                transition_and_hash_chain_integrity=True, no_new_simulator_steps=True)
