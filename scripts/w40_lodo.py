"""Wave 40 Step 4.1 (NOT LOCKED): the Wave 39 internal-fold protocol rerun with the REPAIRED search (w40_search) and the added arm
Fixed+Repr-v5 (Fixed-v5 as the base prior mean updated with the learned representation counts; w40_learn.fixed_repr).
Otherwise identical to Wave 39 (below). Seeds: wave40 dev | confirm_lodo (one-use, claimed whole). Resumable per fold.
Wave 39 text: internal transfer under the expanded language: leave-one-domain-out over the 4 program domains with the
v5 language / scope / Checker v5 given identically to every arm. For held-out domain h: source = SOURCE mechanisms of the other
3 domains, solved by Fresh-v5 (metered; certified solutions only); priors fitted from them (fitting metered); targets = all
tasks of domain h. Arms: Fresh-v5, Placebo-v5 (permuted learned prior), Fixed-v5 (hand-designed, category d), Repr-v5 (learned
representation prior), Repr-core-v5 (one certified program per source mechanism). Budget = 2x cap (4M executions per search);
anytime curves at 0.25x-2x are read from this run. --split dev | confirm_lodo5 (one-use, claimed whole)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
ARMS = ("Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Fixed+Repr-v5", "Repr-core-v5")
CAP2 = 4_000_000


def run_fold(ev, seed, h, n_src, n_tgt, arms):
    from nexus import w38_domains as D
    others = tuple(d for d in D.DOMAINS if d != h)
    src = D.stream(f"{seed}:src:{h}", others, "source", n_src)
    ch = ev.child()
    srows, progs, core, seen = [], [], [], set()
    for i, t in enumerate(src):
        r = ev.solve(ch, t, len(t["teacher"]), f"{seed}:{h}:s{i}", budget=CAP2)
        srows.append(r)
        if r.get("certified"):
            progs.append(r["candidate"])
            if (t["domain"], t["mechanism"]) not in seen:
                seen.add((t["domain"], t["mechanism"])); core.append(r["candidate"])
    fits = {k: ev.call(ch, job) for k, job in (("Placebo-v5", {"cmd": "fit", "kind": "placebo", "programs": progs, "seed": f"{seed}:{h}"}),
                                               ("Repr-v5", {"cmd": "fit", "kind": "repr", "programs": progs}),
                                               ("Fixed+Repr-v5", {"cmd": "fit", "kind": "fixed_repr", "programs": progs}),
                                               ("Repr-core-v5", {"cmd": "fit", "kind": "repr", "programs": core}))}
    ch.close()
    priors = {"Fresh-v5": None, "Fixed-v5": {"kind": "fixed5"}, **{k: v["prior"] for k, v in fits.items()}}
    tgt = D.stream(f"{seed}:tgt:{h}", (h,), "all", n_tgt)
    out = {"source": dict(n=len(src), certified=len(progs), core=len(core), work=sum(r["work"] for r in srows),
                          wrong=sum(r["wrong"] for r in srows), work_by_task=[r["work"] for r in srows],
                          mech_by_task=[[t["domain"], t["mechanism"]] for t in src],
                          cert_by_task=[bool(r.get("certified")) for r in srows]),
           "fit_instr": {k: v["_instr"] for k, v in fits.items()}, "arms": {}}
    for arm in arms:
        ch = ev.child()
        rows = []
        for j, t in enumerate(tgt):
            r = ev.solve(ch, t, len(t["teacher"]), f"{seed}:{h}:t{j}", prior=priors[arm], budget=CAP2)
            r["category"] = "withheld_domain_familiar_type" if t["source"] else "withheld_domain_and_mechanism"
            r.pop("candidate", None)
            rows.append(r)
        ch.close()
        out["arms"][arm] = rows
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", default="strings,tables,grids,graphs"); ap.add_argument("--out", required=True)
    ap.add_argument("--n-src", type=int, default=2); ap.add_argument("--n-tgt", type=int, default=2)
    ap.add_argument("--arms", default=",".join(ARMS)); ap.add_argument("--max-s", type=float, default=600)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import w40_eval as WE
    if a.split == "dev":
        R.claim("wave40", "dev", [a.seed], run_id="w40-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w40-confirm_lodo" for r in spent):
            R.claim("wave39", "confirm_lodo5", list(R.REGISTRY[("wave40", "confirm_lodo")]), run_id="w40-confirm_lodo")
        if a.seed not in R.REGISTRY[("wave40", "confirm_lodo")]:
            raise SystemExit("seed outside wave40 confirm_lodo")
    ev = WE.Eval(); t0 = time.perf_counter()
    p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    for h in a.folds.split(","):
        if h in res:
            continue
        res[h] = run_fold(ev, a.seed, h, a.n_src, a.n_tgt, a.arms.split(","))
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
        print(a.seed, h, "%.0fs" % (time.perf_counter() - t0), {arm: (sum(r["correct"] for r in rs), len(rs), sum(r["wrong"] for r in rs),
                          round(sum(r["work"] for r in rs) / 1e9, 1)) for arm, rs in res[h]["arms"].items()}, flush=True)
        if time.perf_counter() - t0 > a.max_s:
            break
    done = all(h in res for h in a.folds.split(","))
    WE.ledger_append(dict(run=f"w40-lodo-{a.split}-{a.seed}", wall_s=time.perf_counter() - t0, status="COMPLETE" if done else "CHECKPOINT"))


if __name__ == "__main__":
    main()
