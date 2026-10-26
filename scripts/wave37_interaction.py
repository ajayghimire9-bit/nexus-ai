"""Wave 37 (NOT LOCKED): baseline / learner-only / N1-only / both, in one pipeline (online program streams from an empty
library), on STATIONARY streams (one family, two segments: detection can only add overhead or false alarms) and
NON-STATIONARY streams (unannounced family switches). Checker v3 pinned, sandbox, OS meter, detectors on every arm.
--split dev | confirm (one-use wave37 confirm 7701-7705, run once after the freeze)."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
MODES = ("base", "learner", "n1", "both")


def fam(name, seed, rep=3):
    from nexus import wave33_tasks as T33
    from nexus import wave34_tasks as T4
    if name == "F2":
        return T33.f2_stream(f"{seed}", rep)
    return T4.family_stream(T4.F3 if name == "F3" else T4.F4, seed, rep, name)


def streams(seed):
    return {"stat_F2": fam("F2", f"{seed}a") + fam("F2", f"{seed}b"),
            "stat_F3": fam("F3", f"{seed}a") + fam("F3", f"{seed}b"),
            "switch_A": fam("F2", f"{seed}c") + fam("F4", f"{seed}c") + fam("F3", f"{seed}c"),
            "switch_B": fam("F3", f"{seed}d") + fam("F2", f"{seed}d") + fam("F4", f"{seed}d")}


def run(ev, mode, tasks, tag, hashseed="0"):
    from nexus import wave31_evaluator as E
    ch = E.Child(hashseed)
    ch.send({"cmd": "cd_reset", "mode": mode}); ch.recv()
    rows, learn, decl = [], 0, 0
    for k, t in enumerate(tasks):
        r = ev.lsolve(ch, t, {}, f"{tag}:{k}", cmd="cd_solve")
        rows.append(r)
        c0 = E.instructions(ch.p.pid)
        ch.send({"cmd": "cd_update", "candidate": r.get("candidate"), "rec": r.get("rec"),
                 "view": {"public": t["public"], "query": t["query"]}, "certified": r["label"] == "exhaustive_UNIQUE"})
        decl = ch.recv()["result"].get("n_declared", 0)
        learn += E.instructions(ch.p.pid) - c0
    ch.close()
    return dict(F.summ(rows, learn, 0), declared=decl, digest=W.digest(rows))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_detectors as D
    seeds = list(R.REGISTRY[("wave37", "dev" if a.split == "dev" else "confirm")])
    R.claim("wave37", a.split, seeds, run_id=f"w37-{a.split}", record=(a.split != "dev"))
    if a.split == "dev":
        seeds = seeds[:3]
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    res = {}
    for s in seeds:
        res[s] = {}
        for name, tasks in streams(s).items():
            res[s][name] = {m: run(ev, m, tasks, f"w37:{s}:{name}") for m in MODES}
            print(s, name, {m: (round(v["work"] / 1e9, 2), v["declared"]) for m, v in res[s][name].items()}, flush=True)
    out = {"results": res, "D4": D.scan([], fp)["D4_integrity"]}
    if a.split != "dev":
        s0 = seeds[2]
        r2 = run(ev, "both", streams(s0)["switch_A"], f"w37:{s0}:switch_A", "1")
        out["replay_both_switch_A"] = r2["digest"] == res[s0]["switch_A"]["both"]["digest"]
    Path(a.out).write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"w37-{a.split}", wall_s=time.perf_counter() - t0, status="COMPLETE"))
    kinds = {"stationary": ("stat_F2", "stat_F3"), "non-stationary": ("switch_A", "switch_B")}
    for kname, names in kinds.items():
        tot = {m: sum(res[s][n][m]["work"] for s in seeds for n in names) for m in MODES}
        wrong = sum(res[s][n][m]["wrong"] for s in seeds for n in names for m in MODES)
        flags = sum(sum(res[s][n][m]["detectors"].values()) for s in seeds for n in names for m in MODES)
        decl = {m: sum(res[s][n][m]["declared"] for s in seeds for n in names) for m in ("n1", "both")}
        def w(x, y): return sum(sum(res[s][n][x]["work"] for n in names) < sum(res[s][n][y]["work"] for n in names) for s in seeds)
        print(kname, {m: round(v / 1e9, 2) for m, v in tot.items()}, "wrong", wrong, "flags", flags, "declared", decl,
              "| learner/base %.4f both/learner %.4f (%d/%d) n1/base %.4f both/base %.4f" % (
                  tot["learner"] / tot["base"], tot["both"] / tot["learner"], w("both", "learner"), len(seeds),
                  tot["n1"] / tot["base"], tot["both"] / tot["base"]))
    print("replay", out.get("replay_both_switch_A"), "D4", out["D4"])


if __name__ == "__main__":
    main()
