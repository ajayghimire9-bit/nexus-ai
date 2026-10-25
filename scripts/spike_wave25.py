"""Wave 25 spike S1 + S2 (DEV seeds only; exploration evidence, not a locked evaluation).

Pass / kill criteria are the ones written in docs/NEXUS_WAVE25_FACTORED_DISCOVERY_DESIGN.md §5.2 before any
spike code ran. Every execution is ledgered against the standing grant.
"""
import argparse, json, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"


def summarize(outs, horizon=100):
    s1_all = [r for o in outs for r in o["s1"]]
    rep = {}
    for world in ("INT_LIST", "RECORDS"):
        rs = [r for r in s1_all if r["world"] == world and r["ruleset"] == "tycho_admitted"]
        fd, ab = sum(r["work_fd"] for r in rs), sum(r["work_ab"] for r in rs)
        rep[f"admitted_{world}"] = dict(tasks=len(rs), same_verdicts=all(r["same"] for r in rs),
                                        work_fd=fd, work_ab=ab, net_reduction=1 - ab / max(1, fd))
    s1 = [r for r in s1_all if r["ruleset"] == "all_proved"]
    for world in ("INT_LIST", "RECORDS"):
        rs = [r for r in s1 if r["world"] == world]
        fd, ab = sum(r["work_fd"] for r in rs), sum(r["work_ab"] for r in rs)
        rep[f"s1_{world}"] = dict(tasks=len(rs), same_verdicts=all(r["same"] for r in rs),
                                  evals_fd=sum(r["evals_fd"] for r in rs), evals_ab=sum(r["evals_ab"] for r in rs),
                                  work_fd=fd, work_ab=ab, net_reduction=1 - ab / max(1, fd))
    s1_tot = sum(r["work_fd"] for r in s1), sum(r["work_ab"] for r in s1)
    val = sum(o["ledger"].get("tycho_abstract_validation_work", 0) for o in outs)
    rep["s1_pass"] = all(v["same_verdicts"] and v["net_reduction"] >= 0.30 for k, v in rep.items() if k.startswith("s1_") and isinstance(v, dict) and "net_reduction" in v)
    rep["s1_kill"] = any((not v["same_verdicts"]) or v["net_reduction"] < 0.15 for k, v in rep.items()
                         if k.startswith("s1_") and isinstance(v, dict) and "net_reduction" in v)
    per_task = (s1_tot[0] - s1_tot[1]) / max(1, len(s1))
    rep["s1_tycho"] = dict(saving_per_task_all_proved=per_task, validation_work=val,
                           projected_net_at_horizon=per_task * horizon - val,
                           break_even_horizon=val / per_task if per_task > 0 else None,
                           admitted={o["seed"]: o["abstract_admitted"] for o in outs})
    s2 = [r for o in outs for r in o["s2"]]
    by = defaultdict(lambda: defaultdict(list))
    for r in s2:
        by[r["stratum"]][r["arm"]].append(r)
    for stratum, arms in by.items():
        rep[f"s2_{stratum}"] = {a: dict(tasks=len(rs), solved=sum(r["solved"] for r in rs),
                                        false_certs=sum(bool(r.get("false_certificate")) for r in rs),
                                        probes=sum(r["probes"] for r in rs),
                                        mean_probes=sum(r["probes"] for r in rs) / max(1, len(rs)),
                                        work=sum(r["work"] for r in rs),
                                        rule_fires=sum(l.startswith("rule") for r in rs for l in r["labels"]))
                                for a, rs in arms.items()}
    fs = rep.get("s2_fs_ambiguous", {})
    mining = sum(o["ledger"].get(k, 0) for o in outs for k in ("mining_work", "rule_learning_work", "scope_check_work"))
    if fs:
        r, best = fs["rule"], min((fs[a] for a in ("eig_edit", "eig_perturb", "v4")), key=lambda v: v["work"])
        rep["s2_tycho"] = dict(mining_work=mining, saving_vs_best_baseline=best["work"] - r["work"],
                               projected_net=(best["work"] - r["work"]) / max(1, r["tasks"]) * horizon - mining)
        rep["s2_pass"] = (r["solved"] >= max(fs[a]["solved"] for a in fs) and
                          all(r["mean_probes"] < fs[a]["mean_probes"] for a in ("eig_edit", "eig_perturb", "v4")) and
                          rep["s2_tycho"]["projected_net"] > 0 and r["false_certs"] == 0)
        rep["s2_kill"] = r["mean_probes"] >= min(fs[a]["mean_probes"] for a in ("eig_edit", "eig_perturb"))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "wave25_spike_s1_s2_dev.json"))
    a = ap.parse_args()
    assert all(1 <= s <= 99 for s in a.seeds), "dev seeds only"
    from nexus.wave25_factored import run_spike_seed
    t0, c0, outs, status = time.perf_counter(), time.process_time(), [], "FAILED"
    try:
        for s in a.seeds:
            t1 = time.perf_counter()
            outs.append(run_spike_seed(s))
            print(f"seed {s}: {time.perf_counter() - t1:.1f}s", flush=True)
        status = "COMPLETE"
    finally:
        wall = time.perf_counter() - t0
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave25-spike:s1-s2", seeds=a.seeds, wall_s=wall,
                                    cpu_s=time.process_time() - c0, status=status)) + "\n")
    rep = summarize(outs)
    Path(a.out).write_text(json.dumps(dict(schema="wave25_spike_dev", seeds=a.seeds, wall_s=wall, summary=rep,
                                           seeds_raw=outs), default=repr, sort_keys=True))
    print(json.dumps(rep, indent=1, default=repr))


if __name__ == "__main__":
    main()
