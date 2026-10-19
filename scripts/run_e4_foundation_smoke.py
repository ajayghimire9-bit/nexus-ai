"""Explicitly gated, 80-step implementation smoke. Never trains or loads models."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import time

from nexus.evolution1.resources import Clock
from nexus.evolution2.post_probe import Host
from nexus.tasks.benchmark import FAMILIES, MeteredTaskEnv, evaluate_policy, fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-smoke", action="store_true")
    args = parser.parse_args()
    if not args.execute_smoke:
        parser.error("explicit --execute-smoke required; no implicit collection")
    cpath = ROOT / "configs/e4_foundation_smoke.json"
    c = json.loads(cpath.read_text())
    if set(c["families"]) != set(FAMILIES) or c["real_cap"] != 80 or c["time_cap_s"] != 30:
        raise ValueError("locked_smoke_recipe")
    target = ROOT / "artifacts/e4_foundation_smoke.json"
    if target.exists():
        raise FileExistsError("preserve previous smoke artifact; no automatic rerun")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # Preserve unrelated untracked user files; require every tracked file clean.
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip():
        raise ValueError("commit implementation before engineering collection")
    journal = io.BytesIO()
    wall0, cpu0 = time.perf_counter_ns(), time.process_time_ns()
    clock = lambda: Clock(time.process_time_ns() - cpu0, time.perf_counter_ns() - wall0)
    host = Host(c, clock, journal)
    rows = []
    result = dict(kind=c["kind"], status="incomplete", execution_sha=revision,
        config_sha256=hashlib.sha256(cpath.read_bytes()).hexdigest(),
        contract_hashes={f: FAMILIES[f].signature() for f in c["families"]}, paths=rows,
        dependencies=dict(python=platform.python_version()), scientific_claims=False)
    failure = None
    try:
        for family in c["families"]:
            for policy in c["policies"]:
                fn = (lambda obs, rng, n: int(rng.integers(n))) if policy == "random" else (lambda obs, rng, n: 0)
                paths = []
                for replay in range(c["replays"]):
                    with MeteredTaskEnv(FAMILIES[family].spec(), host) as env:
                        paths.append(evaluate_policy(env, fn, seed=c["fixture_reset_seed"], max_steps=c["steps_per_path"]))
                if fingerprint(paths[0]) != fingerprint(paths[1]):
                    raise ValueError("deterministic_reset_and_policy_replay")
                rows.append(dict(family=family, policy=policy, replays=paths, deterministic=True))
        result["status"] = "complete"
    except BaseException as error:
        failure = error
        result["failure"] = dict(type=type(error).__name__, message=str(error))
    finally:
        elapsed = clock()
        result.update(resources=host.resources(), receipts=[json.loads(line) for line in journal.getvalue().splitlines()],
            wall_s=elapsed.wall_ns / 1e9, cpu_s=elapsed.cpu_ns / 1e9,
            ledger_used_s=c["ledger_before_used_s"] + elapsed.wall_ns / 1e9,
            ledger_remaining_s=c["ledger_before_remaining_s"] - elapsed.wall_ns / 1e9)
        import gymnasium, numpy
        result["dependencies"].update(gymnasium=gymnasium.__version__, numpy=numpy.__version__)
        with target.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    if failure:
        raise failure
    print(json.dumps({k: result[k] for k in ("status", "resources", "wall_s")}))


if __name__ == "__main__":
    main()
