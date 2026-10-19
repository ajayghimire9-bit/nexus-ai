"""One locked five-family scratch PPO pilot; --verify never opens a world."""
from __future__ import annotations
import time
START = time.perf_counter()
CPU_START = time.process_time()
import argparse
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess

import gymnasium as gym
import numpy as np
import torch
from gymnasium.vector import AutoresetMode

from nexus.evolution1.resources import Clock
from nexus.evolution2.post_probe import Host
from nexus.evolution2.full_policy_source import DecisionJournal
from nexus.tasks.benchmark import FAMILIES, fingerprint
from nexus.tasks.ppo_benchmark import (file_hash, parameter_hash, job_seeds, validate_config,
    all_seeds, historical_snapshot, bounds, RecordedTaskEnv, PolicyCounters, training_kwargs, collect_update, evaluate,
    validate_complete, analyze, audit_journals)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/e4_ppo_benchmark.json"
PROTOCOL = ROOT / "docs/NEXUS_E4_PPO_BENCHMARK_PROTOCOL.md"
ALLOCATION = ROOT / "configs/e4_ppo_benchmark_allocation.json"
RESULT = ROOT / "artifacts/e4_ppo_benchmark.json"
USAGE = ROOT / "artifacts/e4_ppo_benchmark_usage.json"
LOCAL = ROOT / "runs/e4_ppo_benchmark"


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def preflight(c, allocation):
    validate_config(c)
    if (allocation["authorized"] is not True or allocation["runs"] != 1
            or allocation["config_sha256"] != file_hash(CONFIG)
            or allocation["protocol_sha256"] != file_hash(PROTOCOL)
            or allocation["real_cap"] != 84840 or allocation["time_cap_s"] != 300
            or allocation["session_remaining_before_s"] < 300):
        raise ValueError("exact_unconsumed_allocation_required")
    required = {"scripts/run_e4_ppo_benchmark.py", "src/nexus/tasks/ppo_benchmark.py",
                "src/nexus/rl/ppo.py", "src/nexus/tasks/benchmark.py", "src/nexus/evolution2/post_probe.py"}
    if not required <= set(allocation["source_sha256"]):
        raise ValueError("trusted_source_hashes_required")
    for path, expected in allocation["source_sha256"].items():
        if file_hash(ROOT / path) != expected:
            raise ValueError("locked_source_changed")
    for row in allocation["frozen_preservation"]:
        if file_hash(ROOT / row["path"]) != row["sha256"]:
            raise ValueError("historical_checkpoint_source_changed")
    if historical_snapshot(ROOT, c["base_revision"]) != allocation["historical_snapshot"]:
        raise ValueError("historical_artifact_changed")
    if any(path.exists() for path in (USAGE, RESULT, LOCAL)):
        raise FileExistsError("one_run_already_started_no_automatic_retry")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError("commit_protocol_and_implementation_first")
    audit = json.loads((ROOT / allocation["seed_audit_path"]).read_text())
    if (file_hash(ROOT / allocation["seed_audit_path"]) != allocation["seed_audit_sha256"] or not audit["passed"]
            or audit["config_sha256"] != file_hash(CONFIG)
            or audit["registered_seed_hash"] != fingerprint(sorted(all_seeds(c)))):
        raise ValueError("seed_exclusion_audit_required")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def verify():
    c = json.loads(CONFIG.read_text())
    p = json.loads(RESULT.read_text())
    validate_complete(p, c)
    if analyze(p, c) != p["analysis"]:
        raise ValueError("summary_replay_disagrees")
    for row in p["models"]:
        if file_hash(ROOT / row["checkpoint_path"]) != row["checkpoint_sha256"]:
            raise ValueError("missing_or_changed_local_checkpoint")
    for row in p["journals"]:
        if file_hash(ROOT / row["path"]) != row["sha256"]:
            raise ValueError("missing_or_changed_raw_journal")
    audit = audit_journals(p, ROOT, deadline=START + c["time_cap_s"] - p["wall_s"])
    elapsed = time.perf_counter() - START
    audit.update(execution_sha=p["execution_sha"], result_sha256=file_hash(RESULT),
        wall_s=elapsed, cpu_s=time.process_time() - CPU_START,
        combined_execution_audit_wall_s=p["wall_s"] + elapsed,
        session_used_after_s=p["session_ledger"]["used_after_s"] + elapsed,
        session_remaining_after_s=p["session_ledger"]["remaining_after_s"] - elapsed,
        checkpoint_files_verified=len(p["models"]))
    write_new(ROOT / "artifacts/e4_ppo_benchmark_validation.json", audit)
    print(json.dumps(audit), flush=True)


def run():
    c, allocation = json.loads(CONFIG.read_text()), json.loads(ALLOCATION.read_text())
    revision = preflight(c, allocation)
    write_new(USAGE, dict(consumed=True, runs=1, automatic_retry=False, execution_sha=revision,
                         allocation_sha256=file_hash(ALLOCATION)))
    LOCAL.mkdir(parents=True)
    p = dict(status="incomplete", declared_complete=False, execution_sha=revision,
        configuration=c, config_sha256=file_hash(CONFIG), protocol_sha256=file_hash(PROTOCOL),
        allocation_sha256=file_hash(ALLOCATION), seed_audit_sha256=allocation["seed_audit_sha256"],
        models=[], rows=[], journals=[], dependencies=dict(python=platform.python_version(),
        gymnasium=gym.__version__, numpy=np.__version__, torch=torch.__version__),
        checkpoint_note="New scratch models only, local ignored runs/; no historical checkpoint loaded or retrained.")
    p["resource_semantics"] = "resources meters real steps and world-model work only. policy_compute separately counts actor/critic trunk calls, rows, heads and optimizer steps; zero imagined transitions does not mean zero policy inference."
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    clock = lambda: Clock(int((time.process_time() - CPU_START) * 1e9), int((time.perf_counter() - START) * 1e9))
    counters = PolicyCounters(c)
    agents = {}
    resource_stream, transition_stream = None, None
    host = None
    def deadline(*unused):
        raise TimeoutError("registered_active_stop_290s_save_partial_no_retry")
    previous_handler = signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, c["active_stop_s"] - (time.perf_counter() - START)))
    try:
        with ExitStack() as stack:
            resource_stream = stack.enter_context(DecisionJournal(ROOT / "artifacts/e4_ppo_resources.jsonl.gz", 10000))
            transition_stream = stack.enter_context(DecisionJournal(ROOT / "artifacts/e4_ppo_transitions.jsonl.gz", 10000))
            host = Host({**c, "time_cap_s": c["active_stop_s"]}, clock, resource_stream)
            for family, replicate in ((f, r) for r in c["replicates"] for f in c["families"]):
                seeds = job_seeds(c, family, replicate)
                identity = dict(family=family, replicate=replicate, role="training", method="ppo_scratch")
                spec = FAMILIES[family].spec(f"e4_source_{family}", split="train")
                kwargs = training_kwargs(c, spec, host, seeds["model"])
                kwargs["env_fns"] = [lambda: RecordedTaskEnv(spec, host, transition_stream, identity)]
                t0, cpu0 = time.perf_counter(), time.process_time()
                trainer = None
                handles = []
                record = dict(family=family, replicate=replicate, seeds=seeds, history=[])
                p["models"].append(record)
                try:
                    from nexus.rl.ppo import PPOTrainer
                    trainer = PPOTrainer(**kwargs, autoreset_mode=AutoresetMode.SAME_STEP)
                    record.update(initial_hash=parameter_hash(trainer.agent), parameter_count=sum(p.numel() for p in trainer.agent.parameters()))
                    obs, _ = trainer.envs.reset(seed=seeds["train_reset"])
                    trainer._raw_obs = np.asarray(obs, dtype=np.float32)
                    env = trainer.envs.envs[0]
                    before_opt = counters.counts["optimizer_steps"]
                    before_compute = dict(counters.counts)
                    handles = counters.attach(trainer.agent, trainer.optimizer)
                    for _ in range(c["training_interactions"] // c["ppo"]["num_steps"]):
                        record["history"].append(collect_update(trainer, env, before_steps=env.real_steps))
                    record.update(training_real_steps=env.real_steps, optimizer_steps=counters.counts["optimizer_steps"] - before_opt,
                        fitted_hash=parameter_hash(trainer.agent), query_examples_processed=4096 * c["ppo"]["update_epochs"])
                    record["policy_compute"] = {k:v - before_compute[k] for k,v in counters.counts.items()}
                    checkpoint = LOCAL / f"{family}_{replicate}.pt"
                    trainer.save(checkpoint)
                    record.update(checkpoint_path=str(checkpoint.relative_to(ROOT)), checkpoint_sha256=file_hash(checkpoint),
                        checkpoint_bytes=checkpoint.stat().st_size, training_wall_s=time.perf_counter() - t0,
                        training_cpu_s=time.process_time() - cpu0)
                    trainer.agent.eval().requires_grad_(False)
                    agents[(family, replicate)] = trainer.agent
                    print(json.dumps(dict(stage="trained", family=family, replicate=replicate,
                        real_steps=env.real_steps, wall_s=record["training_wall_s"])), flush=True)
                finally:
                    for handle in handles: handle.remove()
                    if trainer is not None: trainer.close()
            # All fifteen fixed-duration fits finish before opening any evaluation.
            counters.phase = "evaluation"
            for record in p["models"]:
                family, replicate = record["family"], record["replicate"]
                agent, seeds = agents[(family, replicate)], record["seeds"]
                handles = counters.attach(agent)
                spec = FAMILIES[family].spec(f"e4_source_{family}", split="development")
                try:
                    for method in c["methods"]:
                        before_calls, before_rows = counters.counts["trunk_calls"], counters.counts["trunk_rows"]
                        episodes = []
                        for e in range(c["evaluation_episodes"]):
                            identity = dict(family=family, replicate=replicate, role="evaluation", method=method, evaluation_episode=e)
                            episodes.append(evaluate(c, agent, spec, host, transition_stream, identity,
                                reset_seed=seeds["evaluation"][e], policy_seed=seeds["random_policy"][e], method=method))
                        metrics = dict(raw_return=sum(e["raw_return"] for e in episodes) / 2,
                            real_steps=sum(e["length"] for e in episodes), imagined_transitions=0, model_calls=0,
                            network_forwards=0, wall_s=sum(e["wall_s"] for e in episodes), cpu_s=sum(e["cpu_s"] for e in episodes))
                        metrics.update(policy_trunk_calls=counters.counts["trunk_calls"] - before_calls,
                                       policy_trunk_rows=counters.counts["trunk_rows"] - before_rows)
                        p["rows"].append(dict(family=family, replicate=replicate, method=method, case=c["cases"][0],
                                              episodes=episodes, metrics=metrics))
                    record["after_evaluation_hash"] = parameter_hash(agent)
                    print(json.dumps(dict(stage="evaluated", family=family, replicate=replicate)), flush=True)
                finally:
                    for handle in handles: handle.remove()
            p.update(resources=host.resources(), policy_compute=dict(counts=counters.counts, phases=counters.phases, bounds=bounds(c)))
            validate_complete(p, c)
            p["analysis"] = analyze(p, c)
            p.update(status="complete", declared_complete=True)
    except BaseException as error:
        p["failure"] = dict(type=type(error).__name__, message=str(error))
        if not isinstance(error, (TimeoutError, KeyboardInterrupt)):
            p["status"] = "invalid_execution"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if host is not None: p["resources"] = host.resources()
        p["policy_compute"] = dict(counts=counters.counts, phases=counters.phases, bounds=bounds(c))
        for journal in (resource_stream, transition_stream):
            if journal is not None:
                p["journals"] += [dict(path=str(path.relative_to(ROOT)), sha256=file_hash(path), bytes=path.stat().st_size) for path in journal.paths]
        for row in allocation["frozen_preservation"]:
            if file_hash(ROOT / row["path"]) != row["sha256"]:
                p.update(status="invalid_execution", declared_complete=False, preservation_failure=row["path"])
        if historical_snapshot(ROOT, c["base_revision"]) != allocation["historical_snapshot"]:
            p.update(status="invalid_execution", declared_complete=False, preservation_failure="historical_json_snapshot")
        elapsed = time.perf_counter() - START
        if elapsed >= c["time_cap_s"]:
            p.update(status="incomplete", declared_complete=False, time_cap_exceeded=True)
        p.update(wall_s=elapsed, cpu_s=time.process_time() - CPU_START,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            session_ledger=dict(used_before_s=allocation["session_used_before_s"],
                used_after_s=allocation["session_used_before_s"] + elapsed,
                remaining_after_s=allocation["session_remaining_before_s"] - elapsed))
        write_new(RESULT, p)
    print(json.dumps(dict(status=p["status"], declared_complete=p["declared_complete"], wall_s=p["wall_s"],
        resources=p.get("resources"), label=p.get("analysis", {}).get("label"))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify() if args.verify else run()
