"""Milestone B (NOT LOCKED): autonomous evolution of a programmatic meta-learner (wave33_metalearner DSL) under ONE locked
selection criterion with ZERO human selection amendments, then a single test of the winner on an UNSEEN task family.
LOCKED CRITERION (also in docs/NEXUS_WAVE33_MILESTONES.md, committed before evolution):
  * stream score = learner evaluator_work (incl. every metered update) / the GEN0_OFF learner's work on the same stream;
  * fitness = mean stream score over the 9 fitness streams (wave33 dev 791-793 x {2rep, 3rep, mixed}); admission requires
    wrong == 0, all detectors 0, and a matching replay when replayed;
  * evolution: archive seeded with GEN0_ON, GEN0_OFF, SEED_PRIOR; 8 generations x 6 children; parent = 2-way tournament
    over the archive; selection: the top 5 by fitness are re-scored on wave33 valsel 796-800 (15 streams), and the winner is the
    minimum mean valsel score. Nothing else is chosen by hand.
TEST (one-use wave33 test 7301-7305, run once): family F2 at 2 and 3 reps, from an empty library; arms: the evolved learner,
Gen 0 learning ON (GEN0_V3C), Gen 0 learning OFF, and the frozen a0c2 gate."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
STATE = ROOT / "artifacts/wave33B_state.json"
FIT, VALSEL, TEST = (791, 792, 793), (796, 797, 798, 799, 800), (7301, 7302, 7303, 7304, 7305)


def episode(ev, child, tasks, program, tag):
    from nexus import wave31_evaluator as E
    child.send({"cmd": "l_reset"}); child.recv()
    rows, learn = [], 0
    for k, t in enumerate(tasks):
        r = ev.lsolve(child, t, program, f"{tag}:{k}")
        rows.append(r)
        cert = r["label"] == "exhaustive_UNIQUE"
        c0 = E.instructions(child.p.pid)
        child.send({"cmd": "l_update", "program": program, "candidate": r.get("candidate"),
                    "view": {"public": t["public"], "query": t["query"]}, "certified": cert})
        child.recv()
        learn += E.instructions(child.p.pid) - c0
    return rows, learn


def run_learner(ev, program, tasks, tag, hashseed="0"):
    from nexus import wave31_evaluator as E
    ch = E.Child(hashseed)
    rows, learn = episode(ev, ch, tasks, program, tag)
    ch.close()
    return rows, learn


def score(ev, program, seeds, off):
    from nexus import wave33_tasks as T3
    from nexus import wave32_detectors as D
    ratios, rows_all, correct, wrong = [], [], 0, 0
    for s in seeds:
        for regime, tasks in T3.evo_streams(s).items():
            rows, learn = run_learner(ev, program, tasks, f"w33B:{s}:{regime}")
            work = sum(r["ext"]["evaluator_work"] for r in rows) + learn
            ratios.append(work / off[f"{s}:{regime}"])
            correct += sum(r["correct"] for r in rows); wrong += sum(r["wrong"] is not None for r in rows); rows_all += rows
    m = sum(ratios) / len(ratios)
    return dict(mean=m, work=m, max=max(ratios), correct=correct, wrong=wrong, detectors=D.scan(rows_all)), rows_all


def off_table(ev, seeds):
    from nexus import wave33_tasks as T3
    from nexus import wave33_metalearner as M
    off = {}
    for s in seeds:
        for regime, tasks in T3.evo_streams(s).items():
            rows, learn = run_learner(ev, M.GEN0_OFF, tasks, f"w33B:{s}:{regime}")
            off[f"{s}:{regime}"] = sum(r["ext"]["evaluator_work"] for r in rows) + learn
    return off


def key(e):
    return (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["mean"])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", required=True); a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    from nexus import wave33_metalearner as M
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if a.phase == "evolve":
        R.claim("wave33", "dev", list(FIT), run_id="w33B-evolve", record=False)
        if "off" not in st:
            st.update(off=off_table(ev, FIT), archive=[], log=[], gen=-1)
        seen = {json.dumps(e["program"], sort_keys=True) for e in st["log"]}
        while st["gen"] < 8 and time.perf_counter() - t0 < 700:
            gen = st["gen"] + 1
            rng = random.Random(f"w33B-evolve:{gen}")
            gfp = D.fingerprint()
            if gen == 0:
                kids = [(None, M.GEN0_ON), (None, M.GEN0_OFF), (None, M.SEED_PRIOR)]
            else:
                kids = []
                while len(kids) < 6:
                    p = A.pick_parent(st["archive"], rng); q = M.mutate(p["program"], rng)
                    k = json.dumps(q, sort_keys=True)
                    if k not in seen and k not in {json.dumps(x, sort_keys=True) for _, x in kids}:
                        kids.append((p["id"], q))
            rep_i = rng.randrange(len(kids))
            for i, (parent, q) in enumerate(kids):
                fit, rows = score(ev, q, FIT, st["off"])
                replay = None
                if i == rep_i:
                    from nexus import wave33_tasks as T3
                    tasks = T3.evo_streams(FIT[0])["2rep"]
                    rows2, _ = run_learner(ev, q, tasks, f"w33B:{FIT[0]}:2rep", "1")
                    replay = W.digest(rows2) == W.digest(rows[:len(rows2)])
                ok = fit["wrong"] == 0 and sum(fit["detectors"].values()) == 0 and replay is not False
                ent = dict(id=f"b{gen}c{i}", gen=gen, parent=parent, program=q, fit=fit, replay=replay, admitted=ok)
                st["log"].append(ent); seen.add(json.dumps(q, sort_keys=True))
                if ok:
                    st["archive"].append(ent)
                print(ent["id"], parent, ok, replay, "mean %.4f max %.4f" % (fit["mean"], fit["max"]), flush=True)
            if D.scan([], gfp)["D4_integrity"]:
                raise SystemExit("D4 integrity violation")
            st["gen"] = gen
            STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
    elif a.phase == "select":
        R.claim("wave33", "valsel", list(VALSEL), run_id="w33B-select", record=False)
        off = off_table(ev, VALSEL)
        sel = []
        for e in sorted(st["archive"], key=key)[:5]:
            fit, _ = score(ev, e["program"], VALSEL, off)
            sel.append(dict(id=e["id"], program=e["program"], fit=fit))
            print("valsel", e["id"], "mean %.4f max %.4f wrong %d" % (fit["mean"], fit["max"], fit["wrong"]), flush=True)
        ok = [s for s in sel if s["fit"]["wrong"] == 0 and sum(s["fit"]["detectors"].values()) == 0]
        win = min(ok, key=lambda s: s["fit"]["mean"])
        st.update(selection=sel, winner=win["program"], winner_id=win["id"], off_valsel=off)
        print("WINNER", win["id"], json.dumps(win["program"]))
    else:
        from nexus import wave33_tasks as T3
        R.claim("wave33", "test", list(TEST), run_id="w33B-test")
        gate = next(e["genome"] for e in json.loads((ROOT / "artifacts/wave32_adaptive_state.json").read_text())["archive"]
                    if e["id"] == "a0c2")
        v3b = {"Gen0-ON": dict(A.GEN0_V3C), "Gen0-OFF": dict(A.GEN0_V3C, online=False), "frozen-a0c2": gate}
        out = {"winner_id": st["winner_id"], "winner": st["winner"], "cells": {}}
        for rep in (2, 3):
            cell = out["cells"][f"F2/{rep}rep"] = {}
            for s in TEST:
                tasks = T3.f2_stream(s, rep)
                rows, learn = run_learner(ev, st["winner"], tasks, f"w33B-test:{s}:{rep}")
                cell.setdefault("Evolved", {})[s] = dict(F.summ(rows, learn, 0), digest=W.digest(rows))
                for name, g in v3b.items():
                    ch = E.Child("0")
                    rws, li, rb = A.episode_v3b(ev, ch, tasks, g, f"w33B-test:{s}:{rep}:{name}")
                    ch.close()
                    cell.setdefault(name, {})[s] = F.summ(rws, li, rb)
        rows2, _ = run_learner(ev, st["winner"], T3.f2_stream(7303, 3), "w33B-test:7303:3", "1")
        out["replay_7303_rep3"] = W.digest(rows2) == out["cells"]["F2/3rep"]["Evolved"][7303]["digest"]
        out["D4"] = D.scan([], fp)["D4_integrity"]
        (ROOT / "artifacts/wave33B_test.json").write_text(json.dumps(out, sort_keys=True, default=repr))
        arms = ("Evolved", "Gen0-ON", "Gen0-OFF", "frozen-a0c2")
        tot = {a_: sum(out["cells"][c][a_][s]["work"] for c in out["cells"] for s in TEST) for a_ in arms}
        for c in out["cells"]:
            print(c, {a_: (round(sum(out["cells"][c][a_][s]["work"] for s in TEST) / 1e9, 2),
                          sum(out["cells"][c][a_][s]["wrong"] for s in TEST),
                          sum(sum(out["cells"][c][a_][s]["detectors"].values()) for s in TEST)) for a_ in arms})
        for a_ in arms[1:]:
            wins = sum(sum(out["cells"][c]["Evolved"][s]["work"] for c in out["cells"]) <
                       sum(out["cells"][c][a_][s]["work"] for c in out["cells"]) for s in TEST)
            print("Evolved /", a_, "%.4f" % (tot["Evolved"] / tot[a_]), "seeds", wins, "/5")
        print("replay", out["replay_7303_rep3"], "D4", out["D4"])
    STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"w33B-{a.phase}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
