"""Seal the ba confirmation projects (NOT LOCKED). Claims nothing (ba_run claims at its first call); generates each test
project in memory (the ONLY execution of the test generators) and writes it as an opaque blob
$NEXUS_SEALED_VAULT_DIR/ba_test/<k>.json. Nothing about the projects is printed or written to the repository except per-blob
sha256 in artifacts/ba_test_vault/MANIFEST.json, committed before the one-shot run."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus import ba_seeds, ba_platform as BP, seed_registry as R  # noqa: F401


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/ba_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    seeds = list(R.REGISTRY[("ba", "test")])
    d = Path(vault) / "ba_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(seeds):
        blob = BP.Project(s, "ba_test").to_json().encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"ba_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("src/nexus/u5_platform.py", "src/nexus/t7_platform.py",
           "src/nexus/oc_platform.py", "src/nexus/ba_platform.py", "src/nexus/t7_world.py", "src/nexus/u5_stateful.py")}
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen,
                                   seeds="ba/test (claimed whole by the runner; X6 X3 X6 X5 by (seed // 4) % 4)"), indent=1, sort_keys=True))
    print(f"sealed {len(files)} projects")


if __name__ == "__main__":
    main()
