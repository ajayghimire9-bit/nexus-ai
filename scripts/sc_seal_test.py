"""Seal the sc confirmation projects (NOT LOCKED): generates each sc/test project in memory (the only execution of the test
generators) and writes an opaque blob $NEXUS_SEALED_VAULT_DIR/sc_test/<k>.json; only per-blob sha256 go to the repository
(artifacts/sc_test_vault/MANIFEST.json), committed before the one-shot run. Claims nothing (sc_run claims at its first call)."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import sc_seeds, sc_platform as SCP, seed_registry as R  # noqa: F401


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/sc_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    d = Path(vault) / "sc_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(R.REGISTRY[("sc", "test")]):
        blob = SCP.Project(s, "sc_test").to_json().encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"sc_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("src/nexus/u5_platform.py", "src/nexus/t7_platform.py",
           "src/nexus/oc_platform.py", "src/nexus/ba_platform.py", "src/nexus/sc_platform.py", "src/nexus/t7_world.py", "src/nexus/u5_stateful.py")}
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen,
                                   seeds="sc/test 13381-13396 (fault (X6, X3, X6, X5)[i // 4]; domains balanced)"), indent=1, sort_keys=True))
    print(f"sealed {len(files)} projects")


if __name__ == "__main__":
    main()
