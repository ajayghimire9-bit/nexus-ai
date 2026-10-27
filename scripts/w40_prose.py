"""Wave 40 Step 5 external PROSE track (NOT LOCKED): search work vs certification work, sound witness short-circuiting, and
payoff-gated online learning. --split dev (PROSE-dev, quarantined development data) | confirm (PROSE-confirm-2: 185 sealed
tasks never used before; frozen runner; manifest hashes verified; one-use claim wave40/confirm_prose).
Task format, harness and held-out scoring: identical to Wave 39 (scripts/w39_prose.py: public = first 3 pairs, query = the 4th
input, held-out = pairs 4.., extra queries = held-out inputs 2..17; < 4 examples -> NOT_EVALUABLE).
Static arms (repaired search; one sandboxed child per arm; budget 4M executions): Fresh-v5, Placebo-v5, Fixed-v5, Repr-v5,
Fixed+Repr-v5. Each solve: search -> witness search in the arm's prior order (<= WITNESS_BUDGET executions) -> Checker v5 ALWAYS (so both accountings and the
short-circuit soundness check come from one run):
  * no-SC work  = search + certification (checker) instructions;
  * SC work     = search + witness search + certification only if no disagreeing witness was found.
Online arms (empty library, continual in name order, certified updates only): Online-hier-v5 (Wave 39 learner, repaired search,
exact O(T) prior rows) and Online-hier-payoff-v5 (w40_online.PayoffGated). Priors: the Wave 39 frozen priors trained ONLY on
internal source domains (artifacts/w39_prose_confirm.json 'source'; the uniform source solves are unchanged by the repair);
their source cost is carried from Wave 39. No external outcome trains anything."""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
CAP2 = 4_000_000
WITNESS_BUDGET = 48_000    # frozen on PROSE-dev: the only grid value with a positive net saving for every arm (w40_prose_dev.json)
MANIFEST = ROOT / "artifacts/external/prose_confirm2/MANIFEST.json"
STATIC = ("Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Fixed+Repr-v5")
ONLINE = ("Online-hier-v5", "Online-hier-payoff-v5")


def tasks_for(split):
    import w39_prose as P
    if split == "dev":
        return P.tasks_for("dev")
    if not os.environ.get("NEXUS_SEALED_HARNESS_TOKEN"):
        raise SystemExit("PROSE-confirm-2 may be loaded only by the frozen runner (NEXUS_SEALED_HARNESS_TOKEN)")
    man = json.loads(MANIFEST.read_text())
    vault = Path(os.environ["NEXUS_SEALED_VAULT_DIR"]) / "wave40_prose_confirm2"
    out = {}
    for n, h in sorted(man["sha256"].items()):
        b = (vault / f"{n}.json").read_bytes()
        if hashlib.sha256(b).hexdigest() != h:
            raise SystemExit(f"manifest hash mismatch: {n}")
        out[n] = json.loads(b)
    return out, man["split"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    ap.add_argument("--arms", default=",".join(STATIC + ONLINE)); ap.add_argument("--max-s", type=float, default=850)
    a = ap.parse_args()
    import w39_prose as P
    from nexus import w38_online as O, w39_lang as L, w40_eval as WE
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    if a.split == "confirm" and "claimed" not in res:
        from nexus import seed_registry as R
        R.claim("wave40", "confirm_prose", [7861], run_id="w40-confirm_prose")
        res["claimed"] = True
    specs, split_of = tasks_for(a.split)
    src = json.loads((ROOT / "artifacts/w39_prose_confirm.json").read_text())["source"]
    pri = src["priors"]
    priors = {"Fresh-v5": None, "Placebo-v5": pri["placebo"], "Fixed-v5": {"kind": "fixed5"}, "Repr-v5": pri["repr"],
              "Fixed+Repr-v5": {"kind": "fixed_repr", "repr": pri["repr"]}}
    res["source_carried_from_w39"] = {k: v for k, v in src.items() if k != "priors"}
    ev = WE.Eval()
    names = sorted(specs)
    res.setdefault("tasks", {n: {"split": split_of[n]} for n in names})
    for arm in a.arms.split(","):
        if res.get("done", {}).get(arm):
            continue
        if arm in ONLINE:
            todo = [(n, P.convert(specs[n], True)[0]) for n in names]
            for n, t in todo:
                if t is None:
                    res["tasks"][n][arm] = {"label": "NOT_EVALUABLE"}
            todo = [(n, t) for n, t in todo if t]
            gate = "hier-payoff" if arm == "Online-hier-payoff-v5" else "hier"
            rows, learn, declared, glog = ev.stream([t for _, t in todo], dict(O.BASELINE_80F9CC2, gate=gate), f"prose40-{a.split}-online",
                                                    shrink=1.0, budget=CAP2, extras=[[x for x, _ in t["heldout"][1:17]] for _, t in todo],
                                                    oracle=False, depth=3)
            for (n, t), r in zip(todo, rows):
                res["tasks"][n][arm] = P.score(r, t, L.run)
            res.setdefault("online", {})[arm] = dict(learn_instr=learn, declared=declared, gate_log=glog)
        else:
            ch = ev.child()
            for n in names:
                if arm in res["tasks"][n]:
                    continue
                t, why = P.convert(specs[n], True)
                if t is None:
                    res["tasks"][n][arm] = {"label": why}; continue
                r = ev.solve(ch, t, 3, f"prose:{n}", prior=priors[arm], budget=CAP2, extra=[x for x, _ in t["heldout"][1:17]],
                             oracle=False, witness=True, witness_budget=WITNESS_BUDGET)
                res["tasks"][n][arm] = P.score(r, t, L.run)
                if time.perf_counter() - t0 > a.max_s:
                    break
            ch.close()
        if all(arm in res["tasks"][n] for n in names):
            res.setdefault("done", {})[arm] = True
        p.write_text(json.dumps(res, sort_keys=True))
        print(arm, "done" if res.get("done", {}).get(arm) else "partial", "%.0fs" % (time.perf_counter() - t0), flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    WE.ledger_append(dict(run=f"w40-prose-{a.split}", wall_s=time.perf_counter() - t0,
                          status="COMPLETE" if all(res.get("done", {}).get(x) for x in a.arms.split(",")) else "CHECKPOINT"))


if __name__ == "__main__":
    main()
