"""Source-only seed-registration audit; no world/model construction or outcomes."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess

from nexus.evolution2.full_policy_source import seed_collisions
from nexus.tasks.ppo_benchmark import all_seeds, file_hash, validate_config
from nexus.tasks.benchmark import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def audit():
    path = ROOT / "configs/e4_ppo_benchmark.json"
    c = json.loads(path.read_text()); validate_config(c)
    candidates = all_seeds(c)
    refs = subprocess.check_output(["git", "for-each-ref", "--format=%(refname):%(objectname)", "refs/heads", "refs/remotes"], cwd=ROOT, text=True).splitlines()
    # Includes historical config versions reachable from all local/remote refs.
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all", "--", "configs"], cwd=ROOT, text=True).splitlines()
    blobs = {}
    for line in objects:
        oid, _, name = line.partition(" ")
        if name.endswith((".json", ".yaml", ".yml")):
            blobs[oid] = name
    reader = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    collisions, checked = {}, 0
    try:
        for oid, name in blobs.items():
            reader.stdin.write((oid + "\n").encode()); reader.stdin.flush()
            header = reader.stdout.readline().decode().split()
            if len(header) != 3 or header[1] != "blob": raise ValueError("configuration_blob_required")
            text = reader.stdout.read(int(header[2])).decode(); reader.stdout.read(1)
            # Conservative ALL integer literals, regardless of field purpose.
            integers = {int(v.replace("_", "")) for v in re.findall(r"(?<![\w.])-?\d[\d_]*(?![\w.])", text)}
            overlap = sorted(integers & candidates)
            if overlap: collisions[oid + ":" + name] = overlap
            checked += 1
    finally:
        reader.stdin.close(); reader.stdout.close(); reader.wait()
    historical = {}
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", c["base_revision"], "--", "artifacts"], cwd=ROOT, text=True).splitlines()
    for name in paths:
        if not name.endswith(".json"): continue
        if (ROOT / name).read_bytes() != subprocess.check_output(["git", "show", c["base_revision"] + ":" + name], cwd=ROOT):
            raise ValueError("historical_artifact_already_changed")
        historical[name] = file_hash(ROOT / name)
        data = json.loads((ROOT / name).read_text())
        overlap = seed_collisions(data, candidates)  # seed metadata only, never scores
        if overlap: collisions[name] = sorted(overlap)
    registry = ROOT / "artifacts/h17_exclusion_registry_audit_validated.json"
    ranges = json.loads(registry.read_text())["conservative_seed_reservations"]
    reserved = sorted(s for s in candidates if any(lo <= s <= hi for lo, hi in ranges))
    if reserved: collisions["historical_conservative_ranges"] = reserved
    return dict(kind="e4_source_only_seed_registration_audit", base_revision=c["base_revision"],
        config_sha256=file_hash(path), registered_seed_hash=fingerprint(sorted(candidates)),
        registered_seeds=sorted(candidates), reachable_ref_count=len(refs),
        reachable_ref_snapshot_hash=fingerprint(sorted(refs)), historical_configuration_blobs=checked,
        historical_artifact_count=len(historical), historical_artifact_hash=fingerprint(historical),
        conservative_reservation_registry_sha256=file_hash(registry), collisions=collisions,
        passed=not collisions, scope="Reachable historical configuration integer literals, current base artifact seed metadata and preserved conservative ranges. Implicit/unavailable external seed histories cannot be certified. Known source physics only; no independent-physics confirmation claim.")


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, allow_nan=False))
