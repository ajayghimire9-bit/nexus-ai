"""t7 confirmation runner (NOT LOCKED).  python scripts/t7_run.py val|val_b|test --part=k/n
Paired arms on identical projects (same project objects, same crash schedules, same spot-check seeds per arm name):
NEXUS_Tournament_Winner (t7_platform.NexusArmStrong), NEXUS_U5 (t7_platform.NexusArm: the u5 behaviour), Fixed_Policy,
Conventional. Seeds: one-use t7 ranges claimed whole at part 1; parts run once each, in order; a crash stops the run.
test: only with NEXUS_SEALED_HARNESS_TOKEN; reads only vault blobs whose sha256 match artifacts/t7_test_vault/MANIFEST.json."""
import hashlib, json, os, sys, traceback
from pathlib import Path
sys.path.insert(0, "scripts")
from u5_run import learners, ledger_rows
from nexus import t7_seeds, t7_platform as T7, seed_registry as R  # noqa: F401
ROOT = Path(__file__).resolve().parents[1]


def main():
    split = sys.argv[1]
    k, n = map(int, dict(a.split("=", 1) for a in sys.argv[2:])["--part"].split("/"))
    fr = json.loads((ROOT / "artifacts/t7_freeze.json").read_text())
    if split == "val_b" and not fr.get("revision"):
        raise SystemExit("val_b only after one disclosed revision")
    if split == "test" and not json.loads((ROOT / "artifacts/t7_val/gate.json").read_text())["passed"]:
        raise SystemExit("validation gate not passed: the sealed test stays closed")
    done = [r for r in ledger_rows() if r.get("run", "").startswith(f"t7-{split}-part")]
    if any(r.get("status") == "CRASHED" for r in done):
        raise SystemExit("crashed earlier: no rerun")
    if any(r.get("run") == f"t7-{split}-part{k}of{n}" and r.get("status") in ("COMPLETE", "FAILED", "TIMEOUT") for r in done):
        raise SystemExit("part already ran")
    seeds = list(R.REGISTRY[("t7", split)])
    if k == 1:
        R.claim("t7", split, seeds, run_id=f"t7-{split}")
    chunk = [s for i, s in enumerate(seeds) if i % n == k - 1]
    if split == "test":
        if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
            raise SystemExit("sealed test needs NEXUS_SEALED_HARNESS_TOKEN")
        man = json.loads((ROOT / "artifacts/t7_test_vault/MANIFEST.json").read_text())
        vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"])

        def make(s):
            rel = f"t7_test/{seeds.index(s)}.json"
            blob = (vault / rel).read_bytes()
            if hashlib.sha256(blob).hexdigest() != man["files"][rel]:
                raise SystemExit("vault blob does not match the manifest")
            return T7.PL.Project.from_json(blob.decode())
    else:
        def make(s):
            return T7.Project(s, split)
    nx, _ = learners()
    L = nx["NEXUS_U5"][0]
    arms = [T7.NexusArmStrong("NEXUS_Tournament_Winner", L), T7.NexusArm("NEXUS_U5", L), T7.FixedArm("Fixed_Policy"),
            T7.FixedArm("Conventional", monitored=False, handle_units=False)]
    res, status = [], "COMPLETE"
    for s in chunk:
        for a in arms:
            try:
                r = T7.run_project(make(s), a)
            except Exception as e:                                       # noqa: BLE001
                res.append(dict(arm=a.name, project=s, outcome="CRASHED", error=type(e).__name__ if split == "test" else traceback.format_exc()))
                status = "CRASHED"
                break
            res.append(r)
            print(s, r["domain"], r["fault"], a.name, "OK" if r["data_ok"] else "BAD", "indep" if r["independently_correct"] else "-",
                  "silent" if r["silent"] else "", "human", r["human_repairs"], r["outcome"], flush=True)
        if status == "CRASHED":
            break
    out = ROOT / f"artifacts/t7_{split}" / f"part{k}of{n}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(split=split, seeds=chunk, status=status, results=res), indent=1, default=str))
    print("STATUS", status)
    if status == "CRASHED":
        sys.exit(3)


if __name__ == "__main__":
    main()
