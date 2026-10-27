"""Seal the Stages 4-6 final-test worlds (NOT LOCKED). Claims the one-use de2/test seeds, generates each world in memory and
writes it as an opaque blob $NEXUS_SEALED_VAULT_DIR/de2_test/<k>.json (nothing about the worlds is printed or written to the
repository except per-blob sha256 in artifacts/de2_test_vault/MANIFEST.json, committed before the one-shot run)."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import s456_seeds  # noqa: F401
from nexus import s4_env as E, seed_registry as R


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/de2_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    seeds = list(R.REGISTRY[("de2", "test")])
    R.claim("de2", "test", seeds, run_id="de2-test-seal")
    d = Path(vault) / "de2_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(seeds):
        blob = E.world_to_json(E.make_world(s, "test")).encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"de2_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=hashlib.sha256((ROOT / "src/nexus/s4_env.py").read_bytes()).hexdigest(),
                                   seeds="de2/test (claimed whole)"), indent=1, sort_keys=True))
    print(f"sealed {len(files)} worlds")


if __name__ == "__main__":
    main()
