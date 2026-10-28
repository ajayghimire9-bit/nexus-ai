"""Seal the x7 confirmation projects (NOT LOCKED): generates each x7/test project in memory (the only execution of the test
generators for NEXUS-facing data) and writes an opaque blob $NEXUS_SEALED_VAULT_DIR/x7_test/<k>.json; only per-blob sha256 go
to the repository (artifacts/x7_test_vault/MANIFEST.json), committed before the one-shot run. Claims nothing (x7_run claims at
its first call). Requires a passing validation gate and the freeze."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import x7_seeds, x7_platform as XP, seed_registry as R  # noqa: F401


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    fr = json.loads((ROOT / "artifacts/x7_freeze.json").read_text())
    gate = ROOT / ("artifacts/x7_val_b/gate.json" if fr.get("revision") else "artifacts/x7_val/gate.json")
    if not json.loads(gate.read_text())["passed"]:
        raise SystemExit("validation gate not passed")
    out = ROOT / "artifacts/x7_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    d = Path(vault) / "x7_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(R.REGISTRY[("x7", "test")]):
        blob = XP.Project(s, "x7_test").to_json().encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"x7_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("src/nexus/u5_platform.py", "src/nexus/t7_platform.py",
           "src/nexus/oc_platform.py", "src/nexus/ba_platform.py", "src/nexus/sc_platform.py", "src/nexus/x7_platform.py",
           "src/nexus/t7_world.py", "src/nexus/u5_stateful.py")}
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen,
                                   seeds="x7/test 13481-13496 (X7_TEST[i // 4][i % 4]: X7a x4, X7b x4, X6/X6P/X6D/X6M, X3/X5/X3/X5)"),
                              indent=1, sort_keys=True))
    print(f"sealed {len(files)} projects")


if __name__ == "__main__":
    main()
