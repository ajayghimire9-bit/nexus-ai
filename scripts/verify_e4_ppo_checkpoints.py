"""Repeatable stdlib integrity check; explicit missing binaries FAIL, never skip."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def verify_files(p, c, root):
    ids = [(r["family"], r["replicate"]) for r in p["models"]]
    expected = set(itertools.product(c["families"], c["replicates"]))
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError("complete planned checkpoint grid required")
    entries = [dict(path=m["checkpoint_path"], sha256=m["checkpoint_sha256"]) for m in p["models"]] + p["journals"]
    for entry in entries:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or not re.fullmatch("[a-f0-9]{64}", entry["sha256"]):
            raise ValueError("invalid provenance path or hash")
        if not path.is_file():
            raise FileNotFoundError(f"Required checkpoint/journal missing: {entry['path']}; integrity audit failed, not skipped.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Required checkpoint/journal hash mismatch: {entry['path']}")
    return dict(checkpoints=len(p["models"]), journals=len(p["journals"]), verified=True,
                simulator_steps=0, model_inference=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", action="store_true", required=True)
    parser.parse_args()
    from summarize_e4_ppo_benchmark import replay
    p = json.loads((ROOT / "artifacts/e4_ppo_benchmark.json").read_text())
    c = json.loads((ROOT / "configs/e4_ppo_benchmark.json").read_text())
    try:
        replay(p, c)
        print(json.dumps(verify_files(p, c, ROOT)))
    except (FileNotFoundError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
