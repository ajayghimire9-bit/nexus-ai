"""Independent audit and raw-receipt verifier; imports no experiment builder.

Checks preservation and receipt arithmetic. It cannot attest discovery, semantic
privacy or a completed v2 scientific experiment; none is present in this commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

BASE = "8d62ce23722bafea9c355cde4f306ca23dad3584"
COUNTERS = ("source_bytes", "ast_nodes", "function_calls", "candidate_executions",
            "visible_tests", "patches", "sandbox_actions")


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def reconstruct(records):
    """Counters are increments, never maxima, cumulative totals, or estimates."""
    totals = dict.fromkeys(COUNTERS + ("wall_ns", "cpu_ns"), 0)
    previous = "0" * 64
    for sequence, r in enumerate(records):
        if set(r) != {"sequence", "action", "observation", "costs", "wall_ns", "cpu_ns",
                      "previous_sha256", "sha256"}:
            raise ValueError("receipt fields mismatch")
        if type(r["sequence"]) is not int or r["sequence"] != sequence or r["previous_sha256"] != previous:
            raise ValueError("receipt chain mismatch")
        if r["sha256"] != sha({k: v for k, v in r.items() if k != "sha256"}):
            raise ValueError("receipt hash mismatch")
        if set(r["costs"]) != set(COUNTERS):
            raise ValueError("counter schema mismatch")
        increments = dict(r["costs"], wall_ns=r["wall_ns"], cpu_ns=r["cpu_ns"])
        for k, v in increments.items():
            if type(v) is not int or v < 0:
                raise ValueError("nonnegative integer counters required")
            totals[k] += v
        previous = r["sha256"]
    return totals


def validate_grid(rows, seeds, families, methods, required_metrics):
    """Expected cells come from a locked plan, never from produced rows."""
    for values in (seeds, families, methods):
        if not values or len(set(values)) != len(values):
            raise ValueError("empty or duplicate planned identifiers")
    if any(type(s) is not int for s in seeds):
        raise ValueError("integer planned seeds required")
    if any(type(x) is not str for x in list(families) + list(methods)):
        raise ValueError("string planned task/method identifiers required")
    expected = {(s, f, m) for s in seeds for f in families for m in methods}
    found = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {"seed", "family", "method", "metrics"}
                or type(row["seed"]) is not int or type(row["family"]) is not str
                or type(row["method"]) is not str or type(row["metrics"]) is not dict):
            raise ValueError("typed grid row required")
        key = (row["seed"], row["family"], row["method"])
        if key not in expected or key in found:
            raise ValueError("duplicate or unexpected cell")
        found.add(key)
        if set(row["metrics"]) != set(required_metrics):
            raise ValueError("required metric set mismatch")
        for value in row["metrics"].values():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("finite numeric metrics required")
    if found != expected:
        raise ValueError("incomplete locked grid")
    return True


def verify_preservation(root):
    """Compare EVERY historical artifact and checkpoint tracked at the base."""
    root = Path(root)
    tree = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=root).decode().splitlines()
    protected = [p for p in tree if p.startswith("artifacts/") or p.endswith((".pt", ".npz", ".npy"))]
    hashes = {}
    # Stream multi-gigabyte research history; never capture it all in RAM.
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
        try:
            for p in protected:
                proc.stdin.write((BASE + ":" + p + "\n").encode())
                proc.stdin.flush()
                header = proc.stdout.readline().split()
                if len(header) != 3 or header[1] != b"blob":
                    raise ValueError("missing base blob: " + p)
                remaining = int(header[2])
                base_hash = hashlib.sha256()
                while remaining:
                    chunk = proc.stdout.read(min(65536, remaining))
                    if not chunk:
                        raise ValueError("truncated Git blob")
                    base_hash.update(chunk)
                    remaining -= len(chunk)
                if proc.stdout.read(1) != b"\n":
                    raise ValueError("Git framing mismatch")
                local_hash = hashlib.sha256()
                with (root / p).open("rb") as stream:
                    for chunk in iter(lambda: stream.read(65536), b""):
                        local_hash.update(chunk)
                if local_hash.hexdigest() != base_hash.hexdigest():
                    raise ValueError("historical artifact modified: " + p)
                hashes[p] = local_hash.hexdigest()
        finally:
            proc.stdin.close()
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=5)
    return {"base": BASE, "preserved_files": len(hashes), "sha256_by_path": hashes}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = verify_preservation(args.root)
    print(json.dumps({"historical_preservation": True, "preserved_files": result["preserved_files"],
                      "v2_scientific_completion_verified": False, "base": BASE}, sort_keys=True))


if __name__ == "__main__":
    main()
