"""Wave 25 anticipatory controller across three regimes. Dev seeds 1-99, or the one-use confirmation
seeds 601-605. Gates (declared in docs/NEXUS_WAVE25_FACTORED_DISCOVERY_DESIGN.md §11 before that run):
  C1 0 false certificates (all arms, seeds, regimes);  C2 identical replay digest;
  C3 revisable total probes over A+B+C < myopic, b_first and flat_eig, AND < fixed_lambda on A+C;
  C4 revisable lowest fully-loaded work over the suite (positive net vs every other arm);
  C5 every seed: final p_cont < 0.2 in A and > 0.8 in B and C, and final boundary weight in C > in B;
  C6 every seed: 0 PROVED_SOUND contracts lost and credited net utility >= 0 for every NEXUS arm.
"""
import argparse, hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
LEDGER = ROOT / "runs" / "experimental" / "wave24-agi" / "ledger.jsonl"
NEXUS = ("revisable", "myopic", "fixed_lambda")


def digest(outs):
    keep = [(o["seed"], reg, r["episode"], r["arm"], [(q["status"], q["probes"], q["solved"]) for q in r["queries"]],
             r["work"]) for o in outs for reg, d in sorted(o["regimes"].items()) for r in d["rows"]]
    return hashlib.sha256(json.dumps(keep).encode()).hexdigest()


def summarize(outs):
    T = defaultdict(lambda: defaultdict(float))
    for o in outs:
        for reg, d in o["regimes"].items():
            for r in d["rows"]:
                for key in (reg, "ALL"):
                    a = T[(r["arm"], key)]
                    a["episodes"] += 1; a["solved"] += r["solved"]; a["probes"] += r["probes"]
                    a["work"] += r["work"]; a["false"] += r["false_certificates"]
                    a["queries"] += len(r["queries"])
                    for q in r["queries"]:
                        a[f"q{q['q'] + 1}_probes"] += q["probes"]
    arms = sorted({k[0] for k in T})
    over = {}
    for arm in arms:
        over[arm] = sum((o["learning_cost"] if arm in NEXUS else o["tycho_batch"]["overhead"]) for o in outs)
    tab = {arm: {reg: dict(T[(arm, reg)]) for reg in ("A", "B", "C", "ALL")} for arm in arms}
    for arm in arms:
        tab[arm]["ALL"]["fully_loaded"] = tab[arm]["ALL"]["work"] + over[arm]
    bel = {}
    for o in outs:
        p = {reg: d["procedures"].get("revisable", {}) for reg, d in o["regimes"].items()}
        bel[o["seed"]] = {reg: dict(p_cont=v.get("p_cont_final"), weights=v.get("weights_final"),
                                    lookahead=v.get("lookahead")) for reg, v in p.items()}
    vault = {o["seed"]: {reg: {a: d["procedures"][a] and {k: d["procedures"][a][k] for k in ("vault_proved", "utility_net")}
                               for a in d["procedures"]} for reg, d in o["regimes"].items()} for o in outs}
    P = lambda arm, reg: tab[arm][reg]["probes"]
    fl = {a: tab[a]["ALL"]["fully_loaded"] for a in arms}
    gates = dict(
        C1=all(tab[a]["ALL"]["false"] == 0 for a in arms),
        C3=all(P("revisable", "ALL") < P(a, "ALL") for a in ("myopic", "b_first", "flat_eig")) and
        P("revisable", "A") + P("revisable", "C") < P("fixed_lambda", "A") + P("fixed_lambda", "C"),
        C4=all(fl["revisable"] < fl[a] for a in arms if a != "revisable"),
        C5=all(b["A"]["p_cont"] < 0.2 and b["B"]["p_cont"] > 0.8 and b["C"]["p_cont"] > 0.8 and
               b["C"]["weights"]["boundary"] > b["B"]["weights"]["boundary"] for b in bel.values()),
        C6=all(v["vault_proved"] == 30 and v["utility_net"] >= 0 for s in vault.values() for r in s.values()
               for v in r.values()))
    return dict(table=tab, overhead=over, beliefs=bel, vault=vault, gates=gates,
                net_vs={a: fl[a] - fl["revisable"] for a in arms if a != "revisable"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--digest-only", action="store_true")
    a = ap.parse_args()
    if a.digest_only:
        from nexus.wave25_anticipate import run_seed
        print(digest([run_seed(s) for s in a.seeds]))
        return
    if any(s >= 100 for s in a.seeds) and not a.digest_only:
        assert a.seeds == [601, 602, 603, 604, 605] and not Path(a.out).exists(), "one-use confirmation"
    from nexus.wave25_anticipate import run_seed
    t0, c0, status, outs, replay = time.perf_counter(), time.process_time(), "FAILED", [], None
    try:
        for s in a.seeds:
            t1 = time.perf_counter()
            outs.append(run_seed(s))
            print(f"seed {s}: {time.perf_counter() - t1:.1f}s", flush=True)
        if a.replay:
            # replay in a separate process with a DIFFERENT string-hash seed: catches set-order nondeterminism
            import os, subprocess
            env = dict(os.environ, PYTHONHASHSEED="424242")
            out = subprocess.run([sys.executable, __file__, "--seeds", *map(str, a.seeds), "--out", "/dev/null",
                                  "--digest-only"], env=env, capture_output=True, text=True, check=True)
            replay = dict(recorded=digest(outs), replayed=out.stdout.strip().splitlines()[-1],
                          replay_hash_seed="424242")
        status = "COMPLETE"
    finally:
        with LEDGER.open("a") as f:
            f.write(json.dumps(dict(run="wave25-anticipate", seeds=a.seeds, replay=a.replay,
                                    wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - c0,
                                    status=status)) + "\n")
    rep = summarize(outs)
    rep["replay"] = replay
    rep["gates"]["C2"] = bool(replay) and replay["recorded"] == replay["replayed"]
    rep["digest"] = digest(outs)
    Path(a.out).write_text(json.dumps(dict(schema="wave25_anticipate", seeds=a.seeds, summary=rep, seeds_raw=outs),
                                      default=repr, sort_keys=True))
    print(json.dumps({k: rep[k] for k in ("gates", "net_vs", "beliefs", "replay")}, indent=1, default=repr))
    for arm, t in rep["table"].items():
        print(f"{arm:13s}", {reg: (int(v.get("solved", 0)), int(v.get("probes", 0)), int(v.get("work", 0))) for reg, v in t.items()},
              int(t["ALL"]["fully_loaded"]), int(t["ALL"]["false"]))


if __name__ == "__main__":
    main()
