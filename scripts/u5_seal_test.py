"""Seal the u5 confirmation projects (NOT LOCKED). Claims nothing (u5_run claims at part 1); generates each test project
in memory (the ONLY execution of the test generators) and writes it as an opaque blob $NEXUS_SEALED_VAULT_DIR/u5_test/<k>.json.
Nothing about the projects is printed or written to the repository except per-blob sha256 in
artifacts/u5_test_vault/MANIFEST.json, committed before the one-shot run."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import u5_seeds  # noqa: F401
from nexus import u5_platform as PL, seed_registry as R


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/u5_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    seeds = list(R.REGISTRY[("u5", "test")])
    d = Path(vault) / "u5_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(seeds):
        blob = PL.Project(s, "test").to_json().encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"u5_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("src/nexus/u5_platform.py", "src/nexus/u5_world.py", "src/nexus/u5_stateful.py")}
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen, seeds="u5/test (claimed whole by the runner)"),
                              indent=1, sort_keys=True))
    print(f"sealed {len(files)} projects")


if __name__ == "__main__":
    main()
