"""Stage 3 runner (NOT LOCKED): both arms on each project; the independent evaluator scores every submitted bundle on the
held-out-batch protocol; the 7-measure Unified Scorecard is written per (project, arm).
  --split dev   dev projects (seed registry de1/dev, reusable)
  --split val   one-use admission-validation projects (de1/val, claimed whole once)
  --split test  one-use final-test projects: loaded ONLY from the sealed vault ($NEXUS_SEALED_VAULT_DIR/de1_test/*.json),
                after verifying every blob against the committed manifest artifacts/de1_test_vault/MANIFEST.json; requires
                NEXUS_SEALED_HARNESS_TOKEN (AGENTS.md RULE 1). One shot: refuses if a de1-test-run row exists.
The agent's workspace receives docs/ + batch1/ + batch2/ only; truth and batch 3 stay with the evaluator."""
import argparse, hashlib, json, os, shutil, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nexus import de_agent as A, de_env as E, de_evaluator as V, outcome_contract as OC, seed_registry as R
from nexus.wave31_evaluator import ledger_append, LEDGER

VAULT_SUB = "de1_test"
MANIFEST = ROOT / "artifacts/de1_test_vault/MANIFEST.json"


def sandbox_profile():
    vault = os.environ.get("NEXUS_SEALED_VAULT_DIR", str(Path.home() / ".nexus_sealed_vault"))
    return ("(version 1)(allow default)" f'(deny file-write* (subpath "{ROOT}"))' f'(deny file-read* (subpath "{Path(vault).resolve()}"))'
            "(deny network*)")


def projects(split, seeds):
    if split in ("dev", "val"):
        for s in seeds:
            yield E.make_project(s, split)
        return
    tok, vault = os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"), os.environ.get("NEXUS_SEALED_VAULT_DIR")
    if not tok or not vault:
        raise SystemExit("sealed test split needs NEXUS_SEALED_HARNESS_TOKEN and NEXUS_SEALED_VAULT_DIR")
    man = json.loads(MANIFEST.read_text())
    for rel, h in sorted(man["files"].items()):
        blob = (Path(vault) / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != h:
            raise SystemExit(f"sealed blob {rel} does not match the committed manifest")
        yield json.loads(blob)


def workspace(inputs, ws):
    ws.mkdir(parents=True)
    for d in ("docs", "batch1", "batch2"):
        shutil.copytree(inputs / d, ws / d)


def scorecard(rec, ev, split):
    sub = rec["submitted"]
    return {
        "1_correctness": dict(independently_checked_correct=bool(sub and ev["correct"]),
                              silent_data_errors=int(sub and ev["exits_ok"] and not (ev["seen_batches_ok"] and ev["heldout_batch_ok"])),
                              seen_batches_correct=ev["seen_batches_ok"], heldout_batch3_correct=ev["heldout_batch_ok"],
                              unresolved_ambiguity=ev["unresolved_ambiguity"], diagnoses=ev["reasons"]),
        "2_completion": dict(outcome=rec["outcome"], finished=int(sub), hard_failures=int(rec["outcome"] == OC.HARD_FAIL),
                             explicit_abstentions=int(rec["outcome"] not in (OC.COMPLETED_VERIFIED, OC.COMPLETED_UNVERIFIED, OC.HARD_FAIL))),
        "3_reliability": dict(freshness_violations=ev["freshness_violations"], idempotent=ev["idempotent"],
                              crash_recovered=ev["recovered"], recovery_s=round(ev["recovery_s"], 3),
                              duplicate_side_effects=ev["duplicate_side_effects"]),
        "4_cost": dict(rec["cost"], model_calls=0, learning_overhead_cpu_s=0.0,
                       operating_cpu_wall_s_per_batch=round(sum(ev["wall_s"][s] for s in ("b1", "b2", "b3")) / 3, 3),
                       development_cpu_s=rec["cost"]["total_cpu_s"]),
        "5_human_dependence": dict(rec["human"], unnecessary_clarifications=ev["unnecessary_clarifications"]),
        "6_learning_benefit": dict(history="none (cross-project learning disabled in both arms)", vs_fresh="n/a (this arm IS the "
                                   "Fresh/0-history baseline)", vs_placebo="n/a until Stage 6"),
        "7_generalization": dict(split=split, heldout_batch3_correct=ev["heldout_batch_ok"]),
    }


FROZEN = ["src/nexus/de_env.py", "src/nexus/de_evaluator.py", "src/nexus/de_template.py", "src/nexus/de_checks.py",
          "src/nexus/de_agent.py", "src/nexus/outcome_contract.py", "src/nexus/seed_registry.py", "scripts/de_stage3.py"]


def assert_frozen():
    """One-use splits run only on committed code: refuse if any Stage 1-3 file differs from HEAD (another writer shares
    this worktree)."""
    import subprocess
    d = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", *FROZEN], capture_output=True, text=True).stdout
    if d.strip():
        raise SystemExit(f"frozen files differ from HEAD:\n{d}")
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev"); ap.add_argument("--seeds", default="")
    ap.add_argument("--out", required=True); ap.add_argument("--max-s", type=float, default=840)
    a = ap.parse_args()
    t0 = time.perf_counter()
    rev = assert_frozen() if a.split != "dev" else None
    if a.split == "dev":
        seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(R.REGISTRY[("de1", "dev")])[:6]
        R.claim("de1", "dev", seeds, run_id="de1-dev", record=False)
    elif a.split in ("val", "val_b"):
        seeds = list(R.REGISTRY[("de1", a.split)])
        R.claim("de1", a.split, seeds, run_id=f"de1-{a.split}")
    else:
        rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
        if any(r.get("run") == "de-stage3-test" for r in rows):
            raise SystemExit("the one-shot final test has already run")
        seeds = None
    out_p = Path(a.out)
    res = json.loads(out_p.read_text()) if out_p.exists() else {"projects": {}}
    res.setdefault("revisions", []).append(rev)
    art = ROOT / f"artifacts/de_stage3_{a.split}"
    split = "val" if a.split == "val_b" else a.split
    for p in projects(split, seeds):
        pid = p["project"]
        if pid in res["projects"]:
            continue
        w = Path(tempfile.mkdtemp(prefix="de3_"))
        E.write_project(p, w / "inputs", w / "truth")
        truth = json.loads((w / "truth/truth.json").read_text())
        row = {"heldout": truth["heldout"], "twists": truth["twists"], "genuine_questions": sorted(truth["answers"]), "arms": {}}
        for arm in A.ARMS + A.SENSITIVITY:
            ws = w / f"ws_{arm}"
            workspace(w / "inputs", ws)
            sh = V.Stakeholder(truth)
            rec = A.solve(arm, ws, sh.ask, sandbox_profile())
            proto = V.run_protocol(ws / "bundle", w / "inputs", w / f"eval_{arm}")
            ev = V.evaluate(truth, proto, sh.log)
            sc = scorecard(rec, ev, split)
            dst = art / pid / arm
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(ws / "bundle", dst)
            (dst / "scorecard.json").write_text(json.dumps(sc, indent=1, sort_keys=True))
            row["arms"][arm] = dict(scorecard=sc, agent=rec, evaluation={k: v for k, v in ev.items() if k != "tables"})
        shutil.rmtree(w)
        res["projects"][pid] = row
        out_p.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
        print(pid, {arm: (r["agent"]["outcome"], r["scorecard"]["1_correctness"]["independently_checked_correct"],
                          r["scorecard"]["1_correctness"]["silent_data_errors"], r["agent"]["cost"]["total_cpu_s"])
                    for arm, r in row["arms"].items()}, "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    run = "de-stage3-test" if a.split == "test" else f"de-stage3-{a.split}"
    ledger_append(dict(run=run, wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
