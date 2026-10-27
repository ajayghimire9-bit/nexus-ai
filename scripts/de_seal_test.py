"""Seal the Stage 3 final-test projects (NOT LOCKED). Claims the one-use de1/test seeds, generates each project in memory
and writes it as an opaque blob $NEXUS_SEALED_VAULT_DIR/de1_test/<k>.json (k = 0..7; no project names, schemas or contents
are printed or written into the repository). The repository receives only artifacts/de1_test_vault/MANIFEST.json
(relative blob path -> sha256), committed before the one-shot runner (scripts/de_stage3.py --split test) may load them."""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import de_env as E, seed_registry as R


def main():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not vault:
        raise SystemExit("set NEXUS_SEALED_VAULT_DIR")
    out = ROOT / "artifacts/de1_test_vault/MANIFEST.json"
    if out.exists():
        raise SystemExit("already sealed")
    seeds = list(R.REGISTRY[("de1", "test")])
    R.claim("de1", "test", seeds, run_id="de1-test-seal")
    d = Path(vault) / "de1_test"
    d.mkdir(parents=True, exist_ok=False)
    files = {}
    for k, s in enumerate(seeds):
        blob = json.dumps(E.make_project(s, "test"), sort_keys=True, default=str).encode()
        (d / f"{k}.json").write_bytes(blob)
        files[f"de1_test/{k}.json"] = hashlib.sha256(blob).hexdigest()
    gen = hashlib.sha256((ROOT / "src/nexus/de_env.py").read_bytes()).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(files=files, n=len(files), generator_sha256=gen, seeds="de1/test (claimed whole)"),
                              indent=1, sort_keys=True))
    print(f"sealed {len(files)} blobs; manifest {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
