"""Stdlib-only independent result arithmetic; no models or environments.

--check-only works in a fresh clone without local checkpoint binaries.
--write adds labeled descriptive action counts from the saved raw journals.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import time

ROOT = Path(__file__).resolve().parents[1]


def interval(values):
    if len(values) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("three_finite_independent_learner_means_required")
    mean = statistics.mean(values)
    half = 4.303 * statistics.stdev(values) / math.sqrt(3)
    return dict(mean=mean, lo=mean - half, hi=mean + half, n=3, df=2)


def replay(p, c):
    expected = set(itertools.product(c["families"], c["replicates"], c["methods"], c["cases"]))
    ids = [(r["family"], r["replicate"], r["method"], r["case"]) for r in p["rows"]]
    if len(ids) != len(expected) or set(ids) != expected or not p["declared_complete"] or p["status"] != "complete":
        raise ValueError("complete_locked_grid_required")
    lookup = {}
    for row in p["rows"]:
        episodes = row["episodes"]
        if len(episodes) != 2 or any(type(e["raw_return"]) not in (int, float) or not math.isfinite(e["raw_return"]) for e in episodes):
            raise ValueError("two_complete_finite_episodes_required")
        mean = sum(e["raw_return"] for e in episodes) / 2
        if not math.isclose(mean, row["metrics"]["raw_return"], rel_tol=0, abs_tol=1e-9):
            raise ValueError("episode_mean_does_not_match_record")
        lookup[(row["family"], row["replicate"], row["method"])] = mean
    result = {}
    for f in c["families"]:
        means = {m: interval([lookup[f, r, m] for r in c["replicates"]]) for m in c["methods"]}
        contrasts = {}
        for baseline in ("random", "fixed"):
            deltas = [lookup[f, r, "ppo_scratch"] - lookup[f, r, baseline] for r in c["replicates"]]
            ci = interval(deltas)
            stored = p["analysis"]["families"][f]["contrasts"][baseline]["interval"]
            if any(not math.isclose(ci[k], stored[k], rel_tol=0, abs_tol=1e-8) for k in ("mean", "lo", "hi")):
                raise ValueError("independent_paired_interval_disagrees")
            contrasts[baseline] = dict(per_seed=deltas, interval=ci)
        passed = all(v["interval"]["mean"] >= c["margins"][f] and v["interval"]["lo"] > 0 for v in contrasts.values())
        if passed != p["analysis"]["families"][f]["screen_passed"]:
            raise ValueError("independent_primary_decision_disagrees")
        result[f] = dict(means=means, contrasts=contrasts, screen_passed=passed)
    return result


def main(write=False):
    start = time.perf_counter()
    c = json.loads((ROOT / "configs/e4_ppo_benchmark.json").read_text())
    path = ROOT / "artifacts/e4_ppo_benchmark.json"
    p = json.loads(path.read_text())
    families = replay(p, c)
    if not write:
        print("Repository-only paired arithmetic and complete grid verified; no checkpoint binaries or simulation required.")
        return
    validation = json.loads((ROOT / "artifacts/e4_ppo_benchmark_validation.json").read_text())
    out = ROOT / "artifacts/e4_ppo_benchmark_independent_summary.json"
    if out.exists(): raise FileExistsError("preserve_saved_independent_summary")
    action_counts = {}
    for entry in p["journals"]:
        if not Path(entry["path"]).name.startswith("e4_ppo_transitions"): continue
        with gzip.open(ROOT / entry["path"], "rt") as stream:
            for line in stream:
                if time.perf_counter() - start + validation["combined_execution_audit_wall_s"] >= c["time_cap_s"]:
                    raise TimeoutError("combined_analysis_budget")
                row = json.loads(line)
                if row["kind"] != "transition": continue
                i = row["identity"]
                if i["role"] != "evaluation": continue
                key = f'{i["family"]}/{i["replicate"]}/{i["method"]}'
                n = c["tasks"][i["family"]]["n_actions"]
                action_counts.setdefault(key, [0] * n)[row["action"]] += 1
    diagnostics = []
    for model in p["models"]:
        f, r = model["family"], model["replicate"]
        selected = {row["method"]: row for row in p["rows"] if (row["family"], row["replicate"]) == (f, r)}
        n = c["tasks"][f]["n_actions"]
        diagnostics.append(dict(family=f, replicate=r,
            action_counts={m: action_counts[f"{f}/{r}/{m}"] for m in c["methods"]},
            ppo_fixed_trajectory_matches=[selected["ppo_scratch"]["episodes"][e]["trajectory_hash"] == selected["fixed"]["episodes"][e]["trajectory_hash"] for e in range(2)],
            final_update_training_entropy=model["history"][-1]["entropy"], maximum_categorical_entropy=math.log(n),
            interpretation="Posthoc descriptive action usage; training entropy is sampled-batch entropy, not held-out statewise logits or causal explanation."))
    elapsed = time.perf_counter() - start
    result = dict(kind="independent_stdlib_replay_plus_posthoc_action_description", execution_sha=p["execution_sha"],
        result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), families=families,
        action_diagnostics=diagnostics, new_simulator_steps=0, new_model_inference=0,
        new_training=0, analysis_wall_s=elapsed,
        combined_execution_audit_analysis_wall_s=validation["combined_execution_audit_wall_s"] + elapsed,
        session_used_after_s=validation["session_used_after_s"] + elapsed,
        session_remaining_after_s=validation["session_remaining_after_s"] - elapsed)
    with out.open("x") as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({k:result[k] for k in ("analysis_wall_s", "combined_execution_audit_analysis_wall_s", "session_used_after_s", "session_remaining_after_s")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check-only", action="store_true")
    main(parser.parse_args().write)
