"""Wave 34 meta-evolution of payoff-driven learner programs (DSL v2, wave34_learner). NOT LOCKED.
Phases:
  devevolve  --seeds devA : DSL iteration run on development data (state file per tag)
  diagnose   --tag X      : the tag's automatic winner vs Gen 0 ON / OFF / frozen a0c2 on DEV mixed + F2 streams (devA)
  evolve / select / test  : the LOCKED final run (see docs/NEXUS_WAVE34_LEARNING_ALGORITHMS.md for the locked criterion)
Stream score r = learner evaluator_work (incl. every metered update) / min(SEED_ON, SEED_OFF) on that stream (both run
through the same interpreter). Program score = mean(r) + mean(max(0, r - 1)) (losses are penalised twice).
Archive: seeds SEED_ON, SEED_OFF, SEED_PRIOR (trivial); children by mutation (70%) or crossover (30%) of parents picked
by fitness tournament (50%) or novelty tournament (50%; behaviour = per-stream component-usage rates + score vector, novelty =
mean distance to the 3 nearest archive members). Admission: wrong == 0, all detectors 0, replay match when replayed."""
import argparse, json, math, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
SEEDS = {"devA": (801, 802, 803, 804), "fit": (805, 806, 807, 808), "valsel": (809, 810, 811, 812, 813),
         "test_f3": (7401, 7402, 7403, 7404, 7405), "test_mixed": (7406, 7407, 7408, 7409, 7410)}


def episode(ev, child, tasks, prog, tag):
    from nexus import wave31_evaluator as E
    child.send({"cmd": "l2_reset"}); child.recv()
    rows, learn = [], 0
    for k, t in enumerate(tasks):
        r = ev.lsolve(child, t, prog, f"{tag}:{k}", cmd="l2_solve")
        rows.append(r)
        c0 = E.instructions(child.p.pid)
        child.send({"cmd": "l2_update", "program": prog, "candidate": r.get("candidate"), "rec": r.get("rec"),
                    "view": {"public": t["public"], "query": t["query"]}, "certified": r["label"] == "exhaustive_UNIQUE"})
        child.recv()
        learn += E.instructions(child.p.pid) - c0
    return rows, learn


def run_prog(ev, prog, tasks, tag, hashseed="0"):
    from nexus import wave31_evaluator as E
    ch = E.Child(hashseed)
    rows, learn = episode(ev, ch, tasks, prog, tag)
    ch.close()
    return rows, learn


def streams(seed):
    from nexus import wave34_tasks as T4
    return T4.train_streams(seed)


def baseline(ev, seeds):
    from nexus import wave34_learner as L
    out = {}
    for s in seeds:
        for name, tasks in streams(s).items():
            w = []
            for p in (L.SEED_ON, L.SEED_OFF):
                rows, learn = run_prog(ev, p, tasks, f"w34:{s}:{name}")
                w.append(sum(r["ext"]["evaluator_work"] for r in rows) + learn)
            out[f"{s}:{name}"] = min(w)
    return out


def score(ev, prog, seeds, base):
    from nexus import wave32_detectors as D
    rs, rows_all, wrong, correct, beh = [], [], 0, 0, []
    for s in seeds:
        for name, tasks in streams(s).items():
            rows, learn = run_prog(ev, prog, tasks, f"w34:{s}:{name}")
            r = (sum(x["ext"]["evaluator_work"] for x in rows) + learn) / base[f"{s}:{name}"]
            rs.append(r); rows_all += rows
            wrong += sum(x["wrong"] is not None for x in rows); correct += sum(x["correct"] for x in rows)
            u = [x.get("rec", {}) or {} for x in rows]
            beh += [sum(bool(z.get("use", {}).get(c)) for z in u) / max(1, len(u)) for c in ("m", "p", "x")]
    sc = sum(rs) / len(rs) + sum(max(0.0, r - 1) for r in rs) / len(rs)
    return dict(score=sc, work=sc, mean=sum(rs) / len(rs), max=max(rs), losses=sum(r >= 1 for r in rs), n_streams=len(rs),
                wrong=wrong, correct=correct, detectors=D.scan(rows_all), behaviour=beh + rs), rows_all


def novelty(e, arch):
    d = sorted(math.dist(e["fit"]["behaviour"], o["fit"]["behaviour"]) for o in arch if o is not e)
    return sum(d[:3]) / max(1, len(d[:3]))


def pick(arch, rng):
    a, b = rng.sample(arch, 2) if len(arch) > 1 else (arch[0], arch[0])
    if rng.random() < 0.5:
        return a if (a["fit"]["wrong"], a["fit"]["score"]) <= (b["fit"]["wrong"], b["fit"]["score"]) else b
    return a if novelty(a, arch) >= novelty(b, arch) else b


def evolve(ev, st, seeds, gens, kids_n, path, t0, budget_s):
    from nexus import wave32_detectors as D
    from nexus import wave34_learner as L
    if "base" not in st:
        st.update(base=baseline(ev, seeds), archive=[], log=[], gen=-1)
    seen = {json.dumps(e["program"], sort_keys=True) for e in st["log"]}
    while st["gen"] < gens and time.perf_counter() - t0 < budget_s:
        gen = st["gen"] + 1
        rng = random.Random(f"w34-evolve:{path.name}:{gen}")
        gfp = D.fingerprint()
        if gen == 0:
            kids = [(None, L.SEED_ON), (None, L.SEED_OFF), (None, L.SEED_PRIOR)]
        else:
            kids = []
            while len(kids) < kids_n:
                p = pick(st["archive"], rng)
                q = L.crossover(p["program"], pick(st["archive"], rng)["program"], rng) if rng.random() < 0.3 else \
                    L.mutate(p["program"], rng)
                if rng.random() < 0.5:
                    q = L.mutate(q, rng)
                k = json.dumps(q, sort_keys=True)
                if k not in seen and k not in {json.dumps(x, sort_keys=True) for _, x in kids}:
                    kids.append((p["id"], q))
        rep_i = rng.randrange(len(kids))
        for i, (parent, q) in enumerate(kids):
            fit, rows = score(ev, q, seeds, st["base"])
            replay = None
            if i == rep_i:
                tasks = streams(seeds[0])["2rep"]
                rows2, _ = run_prog(ev, q, tasks, f"w34:{seeds[0]}:2rep", "1")
                replay = W.digest(rows2) == W.digest(rows[:len(rows2)])
            ok = fit["wrong"] == 0 and sum(fit["detectors"].values()) == 0 and replay is not False
            ent = dict(id=f"g{gen}c{i}", gen=gen, parent=parent, program=q, fit=fit, replay=replay, admitted=ok)
            st["log"].append(ent); seen.add(json.dumps(q, sort_keys=True))
            if ok:
                st["archive"].append(ent)
            print(ent["id"], parent, ok, replay, "score %.4f mean %.4f max %.4f losses %d/%d" % (
                fit["score"], fit["mean"], fit["max"], fit["losses"], fit["n_streams"]), flush=True)
        if D.scan([], gfp)["D4_integrity"]:
            raise SystemExit("D4 integrity violation")
        st["gen"] = gen
        path.write_text(json.dumps(st, sort_keys=True, default=repr))


def select(ev, st, seeds):
    base = baseline(ev, seeds)
    sel = []
    for e in sorted(st["archive"], key=lambda e: (e["fit"]["wrong"], e["fit"]["score"]))[:5]:
        fit, _ = score(ev, e["program"], seeds, base)
        sel.append(dict(id=e["id"], program=e["program"], fit=fit))
        print("valsel", e["id"], "score %.4f mean %.4f losses %d/%d wrong %d" % (fit["score"], fit["mean"], fit["losses"],
                                                                              fit["n_streams"], fit["wrong"]), flush=True)
    ok = [s for s in sel if s["fit"]["wrong"] == 0 and sum(s["fit"]["detectors"].values()) == 0]
    win = min(ok, key=lambda s: s["fit"]["score"])
    st.update(selection=sel, winner=win["program"], winner_id=win["id"], base_valsel=base)
    print("WINNER", win["id"], json.dumps(win["program"]))


def compare(ev, prog, suite):
    """Winner vs Gen 0 ON / Gen 0 OFF / frozen a0c2 (original implementations) on {name: tasks} per seed."""
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    gate = next(e["genome"] for e in json.loads((ROOT / "artifacts/wave32_adaptive_state.json").read_text())["archive"]
                if e["id"] == "a0c2")
    v3b = {"Gen0-ON": dict(A.GEN0_V3C), "Gen0-OFF": dict(A.GEN0_V3C, online=False), "frozen-a0c2": gate}
    out = {}
    for s, cells in suite.items():
        out[s] = {}
        for cell, tasks in cells.items():
            rows, learn = run_prog(ev, prog, tasks, f"w34cmp:{s}:{cell}")
            out[s][cell] = {"Evolved": dict(F.summ(rows, learn, 0), digest=W.digest(rows))}
            for name, g in v3b.items():
                ch = E.Child("0")
                rws, li, rb = A.episode_v3b(ev, ch, tasks, g, f"w34cmp:{s}:{cell}:{name}")
                ch.close()
                out[s][cell][name] = F.summ(rws, li, rb)
    return out


def report(res, label):
    arms = ("Evolved", "Gen0-ON", "Gen0-OFF", "frozen-a0c2")
    seeds = sorted(res, key=str)
    tot = {a: sum(res[s][c][a]["work"] for s in seeds for c in res[s]) for a in arms}
    print(label, {a: round(tot[a] / 1e9, 2) for a in arms},
          "wrong", sum(res[s][c][a]["wrong"] for s in seeds for c in res[s] for a in arms),
          "flags", sum(sum(res[s][c][a]["detectors"].values()) for s in seeds for c in res[s] for a in arms))
    for a in arms[1:]:
        wins = sum(sum(res[s][c]["Evolved"]["work"] for c in res[s]) < sum(res[s][c][a]["work"] for c in res[s]) for s in seeds)
        print(f"  Evolved/{a} {tot['Evolved'] / tot[a]:.4f} seeds {wins}/{len(seeds)}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", required=True); ap.add_argument("--tag", default="final")
    ap.add_argument("--gens", type=int, default=16); ap.add_argument("--kids", type=int, default=8)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_detectors as D
    from nexus import wave34_tasks as T4
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    path = ROOT / f"artifacts/wave34_{a.tag}_state.json"
    st = json.loads(path.read_text()) if path.exists() else {}
    if a.phase == "devevolve":
        R.claim("wave34", "devA", list(SEEDS["devA"][:2]), run_id="w34-devevolve", record=False)
        evolve(ev, st, SEEDS["devA"][:2], a.gens, a.kids, path, t0, 760)
        if st["gen"] >= a.gens and "winner" not in st:
            R.claim("wave34", "devA", list(SEEDS["devA"][2:]), run_id="w34-devselect", record=False)
            select(ev, st, SEEDS["devA"][2:])
    elif a.phase == "diagnose":
        R.claim("wave34", "devA", list(SEEDS["devA"]), run_id="w34-diagnose", record=False)
        mixed = {s: T4.mixed_test_streams(s) for s in SEEDS["devA"]}
        f2 = {s: {"F2x2": __import__("nexus.wave33_tasks", fromlist=["x"]).f2_stream(f"diag{s}", 2),
                  "F2x3": __import__("nexus.wave33_tasks", fromlist=["x"]).f2_stream(f"diag{s}", 3)} for s in SEEDS["devA"]}
        st["diagnose"] = {"mixed": compare(ev, st["winner"], mixed), "F2": compare(ev, st["winner"], f2)}
        report(st["diagnose"]["mixed"], "DEV mixed"); report(st["diagnose"]["F2"], "DEV F2")
    elif a.phase == "evolve":
        R.claim("wave34", "fit", list(SEEDS["fit"]), run_id="w34-evolve", record=False)
        evolve(ev, st, SEEDS["fit"], a.gens, a.kids, path, t0, 760)
    elif a.phase == "select":
        R.claim("wave34", "valsel", list(SEEDS["valsel"]), run_id="w34-select", record=False)
        select(ev, st, SEEDS["valsel"])
    elif a.phase == "test":
        R.claim("wave34", "test_f3", list(SEEDS["test_f3"]), run_id="w34-test-f3")
        R.claim("wave34", "test_mixed", list(SEEDS["test_mixed"]), run_id="w34-test-mixed")
        f3 = {s: {"F3x2": T4.family_stream(T4.F3, s, 2, "F3"), "F3x3": T4.family_stream(T4.F3, s, 3, "F3")}
              for s in SEEDS["test_f3"]}
        mixed = {s: T4.mixed_test_streams(s) for s in SEEDS["test_mixed"]}
        res = {"winner_id": st["winner_id"], "winner": st["winner"], "F3": compare(ev, st["winner"], f3),
               "mixed": compare(ev, st["winner"], mixed)}
        rows2, _ = run_prog(ev, st["winner"], f3[7403]["F3x3"], "w34cmp:7403:F3x3", "1")
        res["replay_7403_F3x3"] = W.digest(rows2) == res["F3"][7403]["F3x3"]["Evolved"]["digest"]
        res["D4"] = D.scan([], fp)["D4_integrity"]
        (ROOT / "artifacts/wave34_test.json").write_text(json.dumps(res, sort_keys=True, default=repr))
        report(res["F3"], "TEST F3"); report(res["mixed"], "TEST mixed")
        print("replay", res["replay_7403_F3x3"], "D4", res["D4"])
    path.write_text(json.dumps(st, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"w34-{a.phase}-{a.tag}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
