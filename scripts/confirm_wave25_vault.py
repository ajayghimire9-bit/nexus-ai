"""Wave 25 refocus: dev runs (seeds 1-99) and the single confirmation run (seeds 501-505).

Gates for the confirmation run (declared in docs/NEXUS_WAVE25_FACTORED_DISCOVERY_DESIGN.md §9 before it):
  C1 zero false certificates in every arm, both queries;  C2 replay digest identical;
  C3 full solved >= every arm AND full probes <= s3_batch's AND < flat_eig, b_first and v4;
  C4 fully-loaded net benefit of full vs s3_batch at horizon 100 > 0;
  C5 version-space reuse: full q2 probes < full_no_reuse q2 probes, 0 false certificates on q2;
  C6 every seed: the vault keeps every PROVED_SOUND contract and the credited lower-bound utility of the
     full arm's active checks is >= 0.
"""
import argparse, copy, hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
H = 100


def digest(outs):
    keep = [(o["seed"], r["episode"], r["arm"], [(q["status"], q["probes"], q["solved"]) for q in r["queries"]],
             r["work"]) for o in outs for r in o["rows"] + o["counterfactual"]]
    return hashlib.sha256(json.dumps(keep).encode()).hexdigest()


def summarize(outs):
    arms = defaultdict(lambda: defaultdict(float))
    for o in outs:
        for r in o["rows"] + o["counterfactual"]:
            a = arms[r["arm"]]
            a["episodes"] += 1
            a["queries"] += len(r["queries"])
            a["solved"] += r["solved"]
            a["probes"] += r["probes"]
            a["work"] += r["work"]
            a["false_certificates"] += r["false_certificates"]
            for q in r["queries"]:
                a[f"q{q['q'] + 1}_probes"] += q["probes"]
                a[f"q{q['q'] + 1}_false"] += q["false_certificate"]
                a[f"q{q['q'] + 1}_zero_probe_unique"] += q["probes"] == 0 and q["status"] == "UNIQUE_IN_BOUNDED_SPACE"
    arms = {k: dict(v) for k, v in arms.items()}
    over_full = sum(o["overhead"]["full"] for o in outs)
    over_batch = sum(o["overhead"]["batch"] for o in outs)
    for k, v in arms.items():
        v["overhead"] = over_full if k in ("full", "full_no_reuse") else over_batch
        v["fully_loaded"] = v["work"] + v["overhead"]
    n = max(1, arms["full"]["episodes"])
    net = (arms["s3_batch"]["work"] - arms["full"]["work"]) / n * H - (over_full - over_batch) / len(outs)
    util_ok = {}
    for o in outs:
        tot = sum(u["observed_work_saved"] - u["check_cost_total"] for u in o["vault"]["utility"].values())
        util_ok[o["seed"]] = dict(net_lower_bound=tot, proved_sound=o["vault"]["proved_sound"],
                                  status=o["vault"]["status"], activation=o["activation"]["rate"])
    rep = dict(arms=arms, net_full_vs_s3_batch_at_H100=net, per_seed=util_ok,
               batch_admitted={o["seed"]: o["tycho_batch"]["admitted"] for o in outs},
               generators={o["seed"]: o["generators"] for o in outs})
    A = arms
    rep["gates"] = dict(
        C1=all(v["false_certificates"] == 0 for v in A.values()),
        C3=A["full"]["solved"] >= max(v["solved"] for k, v in A.items() if k != "full_no_reuse") and
        A["full"]["probes"] <= A["s3_batch"]["probes"] and
        all(A["full"]["probes"] < A[k]["probes"] for k in ("flat_eig", "b_first", "v4")),
        C4=net > 0,
        C5=A["full"]["q2_probes"] < A["full_no_reuse"]["q2_probes"] and A["full"]["q2_false"] == 0,
        C6=all(len(s["proved_sound"]) > 0 and s["net_lower_bound"] >= 0 for s in util_ok.values()))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    if any(s >= 100 for s in a.seeds):
        assert a.seeds == [501, 502, 503, 504, 505], "confirmation seeds are 501-505 only"
        assert not Path(a.out).exists(), "the confirmation run is one-use"
    from nexus.wave25_vault import run_seed
    t0, c0, status, outs, replay = time.perf_counter(), time.process_time(), "FAILED", [], None
    try:
        for s in a.seeds:
            t1 = time.perf_counter()
            outs.append(run_seed(s, n_per_world=a.n))
            print(f"seed {s}: {time.perf_counter() - t1:.1f}s", flush=True)
        if a.replay:
            replay = dict(recorded=digest(outs), replayed=digest([run_seed(s, n_per_world=a.n) for s in a.seeds]))
        status = "COMPLETE"
    finally:
        wall = time.perf_counter() - t0
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave25-vault", seeds=a.seeds, replay=a.replay, wall_s=wall,
                                    cpu_s=time.process_time() - c0, status=status)) + "\n")
    rep = summarize(outs)
    rep["replay"] = replay
    rep["gates"]["C2"] = bool(replay) and replay["recorded"] == replay["replayed"]
    rep["digest"] = digest(outs)
    Path(a.out).write_text(json.dumps(dict(schema="wave25_vault", seeds=a.seeds, wall_s=wall, summary=rep,
                                           seeds_raw=outs), default=repr, sort_keys=True))
    print(json.dumps({k: v for k, v in rep.items() if k != "generators"}, indent=1, default=repr))


if __name__ == "__main__":
    main()
