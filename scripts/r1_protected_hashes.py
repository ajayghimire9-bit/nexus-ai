"""Protected-file hashes for the self-repair increment R1 (NOT LOCKED).
Protected = the 391 Stages 1-3 / checker-kernel files of artifacts/s456_protected_hashes_before.json PLUS every Stages 4-6
result, bundle, manifest, library, calibration and the Stages 4-6 report (old results stay byte-identical).
  python scripts/r1_protected_hashes.py OUT.json            write the current hashes
  python scripts/r1_protected_hashes.py OUT.json BEFORE.json  also compare with BEFORE (exit 1 on any difference)"""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S456 = ["artifacts/s456_dev.json", "artifacts/s456_val.json", "artifacts/s456_test.json", "artifacts/s4_integration_dev.json",
        "artifacts/s4_integration_confirm.json", "artifacts/s5_detector_calibration.json", "artifacts/s6_library.json",
        "artifacts/de2_test_vault/MANIFEST.json", "artifacts/s456_protected_hashes_before.json",
        "artifacts/s456_protected_hashes_after.json", "docs/NEXUS_STAGES_4_TO_6_REPORT.md"]
S456_DIRS = ["artifacts/s456_dev", "artifacts/s456_val", "artifacts/s456_test", "artifacts/s6_src"]


def files():
    base = json.loads((ROOT / "artifacts/s456_protected_hashes_before.json").read_text())["files"]
    out = set(base) | set(S456)
    for d in S456_DIRS:
        out |= {str(p.relative_to(ROOT)) for p in (ROOT / d).rglob("*") if p.is_file()}
    return sorted(out)


def main(out, before=None):
    h = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() if (ROOT / f).exists() else None for f in files()}
    agg = hashlib.sha256(json.dumps(h, sort_keys=True).encode()).hexdigest()
    rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    Path(out).write_text(json.dumps(dict(commit=rev, n=len(h), aggregate=agg, files=h), indent=1, sort_keys=True))
    print(f"{len(h)} protected files, aggregate {agg[:16]}, missing {sum(v is None for v in h.values())}")
    if before:
        b = json.loads(Path(before).read_text())["files"]
        diff = sorted(f for f in set(b) | set(h) if b.get(f) != h.get(f))
        print(f"changed vs {before}: {len(diff)}", diff[:10])
        if diff:
            raise SystemExit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
