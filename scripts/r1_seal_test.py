"""Seal the R1 confirmation worlds (NOT LOCKED). Claims the one-use de3/test seeds, generates each world in memory (this is
the ONLY execution of the X1 / X2 generators) and writes it as an opaque blob $NEXUS_SEALED_VAULT_DIR/de3_test/<k>.json.
Nothing about the worlds is printed or written to the repository except per-blob sha256 in
artifacts/de3_test_vault/MANIFEST.json, committed before the one-shot run."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import r1_seeds  # noqa: F401
from nexus import r1_env as RE, s4_env as E, seed_registry as R


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/de3_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    seeds = list(R.REGISTRY[("de3", "test")])
    R.claim("de3", "test", seeds, run_id="de3-test-seal")
    d = Path(vault) / "de3_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(seeds):
        blob = E.world_to_json(RE.make_world(s, "test")).encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"de3_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in ("src/nexus/s4_env.py", "src/nexus/r1_env.py")}
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen, seeds="de3/test (claimed whole)"),
                              indent=1, sort_keys=True))
    print(f"sealed {len(files)} worlds")


if __name__ == "__main__":
    main()
