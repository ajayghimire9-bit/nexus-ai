"""Wave 36 online / self-improvement track (NOT LOCKED): online streams from an EMPTY library across families
(F2, F3, F4 at 2 and 3 reps; mixed non-stationary Source and Target), every arm on identical streams under Checker v3,
the sandbox and the OS meter.
Arms: B-online (the frozen Wave 35 learner = SEED_PRIOR, (b)), E1 (Bayesian payoff controller around B-online, (b)+(d)),
Fresh-v3 (a), Placebo-v3 (permuted history), Gen0-ON / Gen0-OFF / frozen-a0c2 / Fixed-payoff (fixed controllers).
--split dev (wave36 dev seeds) or --split confirm_online (one-use, run once after freezing)."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
import wave34_meta as M4


def e1_run(ev, tasks, tag, hashseed="0"):
    from nexus import wave31_evaluator as E
    ch = E.Child(hashseed)
    ch.send({"cmd": "e1_reset"}); ch.recv()
    rows, learn, acts = [], 0, []
    for k, t in enumerate(tasks):
        r = ev.lsolve(ch, t, {}, f"{tag}:{k}", cmd="e1_solve")
        rows.append(r)
        c0 = E.instructions(ch.p.pid)
        ch.send({"cmd": "e1_update", "candidate": r.get("candidate"), "rec": r.get("rec"),
                 "view": {"public": t["public"], "query": t["query"]}, "certified": r["label"] == "exhaustive_UNIQUE"})
        acts.append(ch.recv()["result"]["action"])
        learn += E.instructions(ch.p.pid) - c0
    ch.close()
    return rows, learn, acts


def run_family(ev, fam, seeds):
    from nexus import wave34_learner as L
    suite = M4.family_suite(fam, seeds)
    res = M4.confirm_family(ev, L.SEED_PRIOR, suite)          # B-online appears as "Evolved"; Placebo-v3 = its placebo
    for s, cells in suite.items():
        for cell, tasks in cells.items():
            res[s][cell]["B-online"] = res[s][cell].pop("Evolved")
            rows, learn, acts = e1_run(ev, tasks, f"w34cmp:{s}:{cell}")
            res[s][cell]["E1"] = dict(F.summ(rows, learn, 0), digest=W.digest(rows), p_share=acts.count("p") / max(1, len(acts)))
    return res


def run_family_e3(ev, fam, seeds):
    """Stage C: the shortlisted E3 program ('E3') vs B-online, Fresh-v3, Placebo-v3 (placebo of E3) and the fixed controls."""
    from nexus import wave34_learner as L
    prog = json.loads((ROOT / "artifacts/wave36_e3_shortlisted_program.json").read_text())["program"]
    suite = M4.family_suite(fam, seeds)
    res = M4.confirm_family(ev, prog, suite)
    for s, cells in suite.items():
        for cell, tasks in cells.items():
            res[s][cell]["E3"] = res[s][cell].pop("Evolved")
            rows, learn = M4.run_prog(ev, L.SEED_PRIOR, tasks, f"w34cmp:{s}:{cell}")
            res[s][cell]["B-online"] = dict(F.summ(rows, learn, 0), digest=W.digest(rows))
    return res


def table(res):
    if "E1" not in next(iter(next(iter(res.values())).values())):
        return table_e3(res)
    arms = ("E1", "B-online", "Fresh-v3", "Placebo-v3", "Gen0-ON", "Gen0-OFF", "frozen-a0c2", "Fixed-payoff")
    fixed = ("Gen0-ON", "Gen0-OFF", "frozen-a0c2", "Fixed-payoff")
    seeds = sorted(res, key=str)
    tot = {a: sum(res[s][c][a]["work"] for s in seeds for c in res[s]) for a in arms}
    sf = min(fixed, key=lambda a: tot[a])
    out = dict(total=tot, strongest_fixed=sf, n=sum(res[s][c]["E1"]["n"] for s in seeds for c in res[s]),
               solved={a: sum(res[s][c][a]["correct"] for s in seeds for c in res[s]) for a in arms},
               wrong=sum(res[s][c][a]["wrong"] for s in seeds for c in res[s] for a in arms),
               flags=sum(sum(res[s][c][a]["detectors"].values()) for s in seeds for c in res[s] for a in arms))
    for x in ("E1", "B-online"):
        for b in ("Fresh-v3", "Placebo-v3", sf, "B-online"):
            if x == b:
                continue
            out[f"{x}/{b}"] = (tot[x] / tot[b], sum(sum(res[s][c][x]["work"] for c in res[s]) < sum(res[s][c][b]["work"] for c in res[s])
                                                    for s in seeds))
    return out


def table_e3(res):
    arms = ("E3", "B-online", "Fresh-v3", "Placebo-v3", "Gen0-ON", "Gen0-OFF", "frozen-a0c2", "Fixed-payoff")
    fixed = ("Gen0-ON", "Gen0-OFF", "frozen-a0c2", "Fixed-payoff", "B-online")
    seeds = sorted(res, key=str)
    tot = {a: sum(res[s][c][a]["work"] for s in seeds for c in res[s]) for a in arms}
    sf = min(fixed, key=lambda a: tot[a])
    out = dict(total=tot, strongest_fixed=sf, n=sum(res[s][c]["E3"]["n"] for s in seeds for c in res[s]),
               solved={a: sum(res[s][c][a]["correct"] for s in seeds for c in res[s]) for a in arms},
               wrong=sum(res[s][c][a]["wrong"] for s in seeds for c in res[s] for a in arms),
               flags=sum(sum(res[s][c][a]["detectors"].values()) for s in seeds for c in res[s] for a in arms))
    for b in ("Fresh-v3", "Placebo-v3", "B-online", sf):
        out[f"E3/{b}"] = (tot["E3"] / tot[b], sum(sum(res[s][c]["E3"]["work"] for c in res[s]) < sum(res[s][c][b]["work"] for c in res[s])
                                                for s in seeds))
    out["pass"] = bool(out["wrong"] == 0 and out["flags"] == 0 and all(
        out[f"E3/{b}"][0] < 1 and out[f"E3/{b}"][1] >= 4 for b in ("Fresh-v3", "Placebo-v3", sf)))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--family", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_detectors as D
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    if a.split == "dev":
        R.claim("wave36", "dev", list(R.REGISTRY[("wave36", "dev")]), run_id="w36-online-dev", record=False)
        seeds = [821, 822, 823]
    else:
        seeds = list(R.REGISTRY[("wave36", "confirm_online")])
        spent = [json.loads(l) for l in R.SPENT_LEDGER.read_text().splitlines() if l.strip()]
        if not any(r.get("run_id") == "w36-confirm_online" for r in spent):
            R.claim("wave36", "confirm_online", list(R.REGISTRY[("wave36", "confirm_online")]), run_id="w36-confirm_online")
        seeds = [s * 10 + {"F2": 1, "F3": 2, "F4": 3, "mixed": 4}[a.family] for s in seeds]   # disjoint streams per family
    p = Path(a.out)
    out = json.loads(p.read_text()) if p.exists() else {}
    if a.family in out:
        raise SystemExit("family already run")
    res = run_family(ev, a.family, seeds) if a.split == "dev" else run_family_e3(ev, a.family, seeds)
    out[a.family] = dict(results=res, table=table(res), D4=D.scan([], fp)["D4_integrity"])
    p.write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"w36-online-{a.split}-{a.family}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    t = out[a.family]["table"]
    print(a.family, "n", t["n"], "wrong", t["wrong"], "flags", t["flags"], "strongest", t["strongest_fixed"],
          {k: (round(v[0], 4), v[1]) for k, v in t.items() if "/" in k})


if __name__ == "__main__":
    main()
