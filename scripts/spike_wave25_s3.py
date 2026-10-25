"""Wave 25 S1-Auto + S3 spike (DEV seeds only; exploration evidence, not a locked evaluation).

Criteria (declared before the frozen-code run on seeds 4-6, after development on seeds 1-3):
  S1-Auto PASS: contracts admitted by cheap Tycho (net > 0 at horizon 100) on every seed, identical verdicts,
                net certification-work reduction >= 30%; validation overhead reported against the ~600k of S1.
  S3 PASS:      s3 solved >= every arm; s3 total probes < flat_eig and < v4 and <= b_first; 0 false certificates
                in every arm; fully-loaded net benefit at horizon 100 > 0 vs the best other arm.
  S3 KILL:      s3 total probes >= flat_eig total probes.
"""
import argparse, hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
H = 100


def digest(outs):
    keep = [(o["seed"], r["world"], r["task"], r["arm"], r["status"], r["solved"], r["probes"], r["work"])
            for o in outs for r in o["s3"]]
    keep += [(o["seed"], r["world"], r["task"], r["work_plain"], r["work_auto"]) for o in outs for r in o["s1"]]
    return hashlib.sha256(json.dumps(keep).encode()).hexdigest()


def summarize(outs):
    rep = {}
    s1 = [r for o in outs for r in o["s1"]]
    for w in ("INT_LIST", "RECORDS"):
        rs = [r for r in s1 if r["world"] == w]
        a, b = sum(r["work_plain"] for r in rs), sum(r["work_auto"] for r in rs)
        rep[f"s1auto_{w}"] = dict(tasks=len(rs), same=all(r["same"] for r in rs), work_plain=a, work_auto=b,
                                  net_reduction=1 - b / max(1, a))
    rep["s1auto_tycho"] = {o["seed"]: {k: o["tycho"][k] for k in ("validation_overhead", "mean_saving_per_task",
                                                                  "net_benefit", "break_even_horizon", "admitted",
                                                                  "alpha", "loo_abs_error_over_total_saving")}
                           for o in outs}
    c0 = outs[0]["contracts"]
    rep["contracts"] = dict(proved=sorted({(c["prop"], c["role"], c["relation"]) for c in c0 if c["status"] == "proved"}),
                            refuted_props={p: sum(c["status"] == "refuted" for c in c0 if c["prop"] == p)
                                           for p in sorted({c["prop"] for c in c0})},
                            usable=outs[0]["props"])
    rep["s1auto_pass"] = all(v["net_benefit"] > 0 for v in rep["s1auto_tycho"].values()) and \
        all(rep[f"s1auto_{w}"]["same"] and rep[f"s1auto_{w}"]["net_reduction"] >= 0.30 for w in ("INT_LIST", "RECORDS"))
    rows = [r for o in outs for r in o["s3"]]
    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    arms = {}
    for arm, rs in by.items():
        arms[arm] = dict(tasks=len(rs), solved=sum(r["solved"] for r in rs),
                         false_certs=sum(bool(r["false_certificate"]) for r in rs),
                         probes=sum(r["probes"] for r in rs), work=sum(r["work"] for r in rs),
                         by_world={w: dict(solved=sum(r["solved"] for r in rs if r["world"] == w),
                                           probes=sum(r["probes"] for r in rs if r["world"] == w),
                                           work=sum(r["work"] for r in rs if r["world"] == w)) for w in ("INT_LIST", "RECORDS")})
    rep["s3_arms"] = arms
    s3r = by["s3"]
    rep["s3_breakdown"] = dict(
        answer_stop_with_residual_ambiguity=sum(r["status"] == "UNIQUE_IN_BOUNDED_SPACE" and
                                                (r["residual_HB"] > 1e-9 or r["residual_HC"] > 1e-9) for r in s3r),
        of_which_residual_composition=sum(r["status"] == "UNIQUE_IN_BOUNDED_SPACE" and r["residual_HC"] > 1e-9 for r in s3r),
        initially_B_and_C_ambiguous=sum(bool(r["trace"]) and r["trace"][0]["HB"] > 1e-9 and r["trace"][0]["HC"] > 1e-9
                                        for r in s3r),
        one_probe_resolved_C_and_answer=sum(bool(r["trace"]) and r["trace"][0]["HB"] > 1e-9 and r["trace"][0]["HC"] > 1e-9
                                            and r["probes"] == 1 and r["solved"] and r["residual_HC"] <= 1e-9 for r in s3r),
        b_first_stage_labels={k: sum(l == k for r in by["b_first"] for l in r["labels"]) for k in ("b_first:B", "b_first:C")})
    others = [a for a in arms if a not in ("s3", "flat_eig_plain")]
    best = min(others, key=lambda a: (-arms[a]["solved"], arms[a]["work"]))
    n = max(1, arms["s3"]["tasks"])
    overhead = sum(o["tycho"]["validation_overhead"] for o in outs)
    rep["s3_tycho"] = dict(best_other_arm=best,
                           net_vs_best_same_certifier=(arms[best]["work"] - arms["s3"]["work"]) / n * H,
                           fully_loaded_vs_flat_eig_without_contracts=(arms["flat_eig_plain"]["work"] - arms["s3"]["work"]) / n * H
                           - overhead / len(outs))
    rep["s3_pass"] = (arms["s3"]["solved"] >= max(v["solved"] for v in arms.values()) and
                      arms["s3"]["probes"] < arms["flat_eig"]["probes"] and arms["s3"]["probes"] < arms["v4"]["probes"] and
                      arms["s3"]["probes"] <= arms["b_first"]["probes"] and
                      all(v["false_certs"] == 0 for v in arms.values()) and
                      rep["s3_tycho"]["net_vs_best_same_certifier"] > 0)
    rep["s3_kill"] = arms["s3"]["probes"] >= arms["flat_eig"]["probes"]
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "wave25_spike_s1auto_s3_dev.json"))
    ap.add_argument("--replay", action="store_true")
    a = ap.parse_args()
    assert all(1 <= s <= 99 for s in a.seeds), "dev seeds only"
    from nexus.wave25_s3 import run_s3_seed
    t0, c0, status = time.perf_counter(), time.process_time(), "FAILED"
    outs, replay = [], None
    try:
        for s in a.seeds:
            t1 = time.perf_counter()
            outs.append(run_s3_seed(s))
            print(f"seed {s}: {time.perf_counter() - t1:.1f}s", flush=True)
        if a.replay:
            again = [run_s3_seed(s) for s in a.seeds]
            replay = dict(recorded=digest(outs), replayed=digest(again))
        status = "COMPLETE"
    finally:
        wall = time.perf_counter() - t0
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave25-spike:s1auto-s3", seeds=a.seeds, replay=a.replay, wall_s=wall,
                                    cpu_s=time.process_time() - c0, status=status)) + "\n")
    rep = summarize(outs)
    rep["replay"] = replay
    rep["digest"] = digest(outs)
    Path(a.out).write_text(json.dumps(dict(schema="wave25_spike_s3_dev", seeds=a.seeds, wall_s=wall, summary=rep,
                                           seeds_raw=outs), default=repr, sort_keys=True))
    print(json.dumps(rep, indent=1, default=repr))


if __name__ == "__main__":
    main()
