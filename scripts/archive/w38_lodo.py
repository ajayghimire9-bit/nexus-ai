"""Wave 38 experiments 1, 2, 3, 7 (NOT LOCKED): leave-one-domain-out over the 4 program domains, sandboxed solver, Checker v4,
OS meter. For held-out domain h: source = SOURCE mechanisms of the other 3 domains (solved Fresh; certified solutions only);
learned objects (prior, repr prior, placebo, neural ranker) fitted from them (marginal cost metered); targets = all tasks of
domain h (category withheld_domain_familiar_type vs withheld_domain_and_mechanism). Arms: Fresh, Fixed (richer fixed DSL, (d)),
Learned, Repr (exp 1), Placebo, Neural (exp 7). --split dev | confirm_lodo."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
ARMS = ("Fresh", "Fixed", "Learned", "Repr", "Placebo", "Neural")
BUDGET = 2_000_000            # Stage 2 dev fix: large enough that Fresh solves what the other arms solve (comparable solve counts)


def run_fold(ev, seed, h, n_src, n_tgt):
    from nexus import w38_domains as D, w38_learn as K
    others = tuple(d for d in D.DOMAINS if d != h)
    src = D.stream(f"{seed}:src:{h}", others, "source", n_src)
    ch = ev.child()
    srows, progs = [], []
    for i, t in enumerate(src):
        r = ev.solve(ch, t, len(t["teacher"]), f"{seed}:{h}:s{i}", budget=BUDGET)
        srows.append(r)
        if r["label"] == "exhaustive_UNIQUE":
            progs.append(r["candidate"])
    fit = {}
    learned = ev.call(ch, {"cmd": "fit", "kind": "learned", "programs": progs}); fit["Learned"] = learned["_instr"]
    rep = ev.call(ch, {"cmd": "fit", "kind": "repr", "programs": progs}); fit["Repr"] = rep["_instr"]
    pla = ev.call(ch, {"cmd": "fit", "kind": "placebo", "programs": progs, "seed": f"{seed}:{h}"}); fit["Placebo"] = pla["_instr"]
    neu = ev.call(ch, {"cmd": "train_ranker", "programs": progs, "seed": 0}); fit["Neural"] = neu["_instr"]
    ch.close()
    priors = {"Fresh": None, "Fixed": {"kind": "fixed"}, "Learned": learned["prior"], "Repr": rep["prior"], "Placebo": pla["prior"]}
    src_seq = {json.dumps([K.akey(t) for t in p]) for p in progs}
    tgt = D.stream(f"{seed}:tgt:{h}", (h,), "all", n_tgt)
    out = {"source": dict(n=len(src), certified=len(progs), work=sum(r["work"] for r in srows),
                          wrong=sum(r["wrong"] for r in srows)), "fit_instr": fit, "neural_counters": neu["counters"], "arms": {}}
    for arm in ARMS:
        ch = ev.child()
        rows = []
        for j, t in enumerate(tgt):
            r = ev.solve(ch, t, len(t["teacher"]), f"{seed}:{h}:t{j}", prior=priors.get(arm),
                         neural=neu["sd"] if arm == "Neural" else None, budget=BUDGET)
            r["category"] = "withheld_domain_familiar_type" if t["source"] else "withheld_domain_and_mechanism"
            r["encoder_task"] = t["teacher"][0]["op"] in K.ENCODERS
            if r.get("candidate"):
                seq = json.dumps([K.akey(x) for x in r["candidate"]])
                r["novel_composition"] = seq not in src_seq
                r["uses_loop_or_cond"] = any(x["op"] in ("fold", "scan") or "\"if\"" in json.dumps(x) for x in r["candidate"])
            rows.append(r)
        ch.close()
        out["arms"][arm] = rows
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", default="strings,tables,grids,graphs"); ap.add_argument("--out", required=True)
    ap.add_argument("--n-src", type=int, default=2); ap.add_argument("--n-tgt", type=int, default=2)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import w38_eval as WE
    from nexus import wave32_detectors as Dt
    kind = "dev" if a.split == "dev" else "confirm_lodo"
    if a.split == "dev":
        R.claim("wave38", "dev", list(R.REGISTRY[("wave38", "dev")]), run_id="w38-dev", record=False)
    else:
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w38-confirm_lodo" for r in spent):
            R.claim("wave38", "confirm_lodo", list(R.REGISTRY[("wave38", "confirm_lodo")]), run_id="w38-confirm_lodo")
    ev = WE.Eval(); t0 = time.perf_counter(); fp = Dt.fingerprint()
    p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    for h in a.folds.split(","):
        if h in res:
            continue
        res[h] = run_fold(ev, a.seed, h, a.n_src, a.n_tgt)
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
        print(a.seed, h, {arm: (sum(r["correct"] for r in rs), len(rs), round(sum(r["work"] for r in rs) / 1e9, 1))
                          for arm, rs in res[h]["arms"].items()}, flush=True)
    res["_D4"] = Dt.scan([], fp)["D4_integrity"]
    p.write_text(json.dumps(res, sort_keys=True, default=repr))
    WE.ledger_append(dict(run=f"w38-lodo-{a.split}-{a.seed}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
