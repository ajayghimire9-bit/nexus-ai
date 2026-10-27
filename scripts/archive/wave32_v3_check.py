"""Wave 32 targeted check under Checker v3 (NOT LOCKED). It runs only because the predeclared gate was met in the Wave 31 v3
matrix (Experienced-v3 < Fresh-v3 target-only in 5/5 val_v3 seeds, pooled -6.2%).
Small evolution (Gen 0 + 4 generations x 4 children) of the v3 genome on depth-4 streams of the evolution domains
(records, strings, graphs; fitness dev 771-773, selection 774-775). Online learning starts from an EMPTY library, all
5 detectors and one replay run per generation, and fitness comes from the external meter only. Then a one-use test
on held-out grids (wave32 test_v3 7206-7210): Gen k vs Gen 0 (learning OFF) vs Gen 0 (learning ON)."""
import argparse, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
STATE = ROOT / "artifacts/wave32_v3_archive.json"
EVOL, FIT, SEL, TEST = ("records", "strings", "graphs"), (771, 772, 773), (774, 775), (7206, 7207, 7208, 7209, 7210)


def stream3(seed, domains, n_per=2):
    from nexus import wave31_tasks as T
    tasks = [t for d in domains for t in T.target_stream3(seed, d, n_per)]
    random.Random(f"w32v3-order:{seed}").shuffle(tasks)
    return tasks


def run(ev, g, seeds, domains, hashseed="0", n_per=2):
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    rows, learn = [], 0
    for s in seeds:
        ch = E.Child(hashseed)
        r, li = A.episode(ev, ch, stream3(s, domains, n_per), g, f"w32v3:{s}")
        ch.close(); rows += r; learn += li
    return rows, learn


def summ(rows, learn):
    from nexus import wave32_archive as A
    f = A.fitness(rows, learn)
    f["child"] = sum(r["ext"]["child_instr"] for r in rows) + learn
    f["checker"] = sum(r["ext"]["eval_instr"] for r in rows)
    return f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", choices=("evolve", "select", "test"), required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter(); fp = D.fingerprint()
    st = json.loads(STATE.read_text()) if STATE.exists() else {"archive": [], "log": [], "integrity": []}
    if a.phase == "evolve":
        R.claim("wave32", "dev", list(FIT), run_id="wave32v3-evolve", record=False)
        seen = set()
        for gen in range(5):
            rng = random.Random(f"w32v3-evolve:{gen}")
            gfp = D.fingerprint()
            if gen == 0:
                kids = [(None, dict(A.GEN0_V3))]
            else:
                kids = []
                while len(kids) < 4:
                    p = A.pick_parent(st["archive"], rng); g = A.mutate(p["genome"], rng)
                    if A.gkey(g) not in seen and A.gkey(g) not in {A.gkey(k) for _, k in kids}:
                        kids.append((p["id"], g))
            rep = rng.randrange(len(kids))
            for i, (parent, g) in enumerate(kids):
                rows, learn = run(ev, g, FIT, EVOL)
                fit, det = summ(rows, learn), D.scan(rows)
                replay = None
                if i == rep:
                    rows2, _ = run(ev, g, FIT[:1], EVOL, hashseed="1")
                    replay = W.digest(rows2) == W.digest(rows[:len(rows2)])
                ok = sum(det.values()) == 0 and fit["wrong"] == 0 and replay is not False
                ent = dict(id=f"v{gen}c{i}", gen=gen, parent=parent, genome=g, key=A.gkey(g), fit=fit, detectors=det,
                           replay=replay, admitted=ok)
                st["log"].append(ent); seen.add(ent["key"])
                if ok:
                    st["archive"].append(ent)
                print(ent["id"], parent, ok, replay, "work %.2fG child %.2fG correct %d" % (fit["work"] / 1e9, fit["child"] / 1e9, fit["correct"]), flush=True)
            d4 = D.scan([], gfp)["D4_integrity"]
            st["integrity"].append(dict(gen=gen, D4=d4))
            if d4:
                raise SystemExit("D4 integrity violation")
    elif a.phase == "select":
        R.claim("wave32", "dev", list(SEL), run_id="wave32v3-select", record=False)
        top = sorted(st["archive"], key=lambda e: (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["work"]))[:3]
        sel = []
        for e in top:
            rows, learn = run(ev, e["genome"], SEL, EVOL)
            sel.append(dict(id=e["id"], genome=e["genome"], fit=summ(rows, learn), detectors=D.scan(rows)))
            print(e["id"], e["genome"], json.dumps(sel[-1]["fit"]), flush=True)
        ok = [s for s in sel if sum(s["detectors"].values()) == 0 and s["fit"]["wrong"] == 0]
        champ = min(ok, key=lambda s: (-s["fit"]["correct"], s["fit"]["work"]))
        st["selection"] = dict(rows=sel, champion=champ["id"], champion_genome=champ["genome"])
        print("champion", champ["id"], champ["genome"])
    else:
        R.claim("wave32", "test_v3", list(TEST), run_id="wave32v3-test")
        g0 = dict(A.GEN0_V3); gk = dict(st["selection"]["champion_genome"])
        arms = {"Gen0_learning_ON": g0, "Gen0_learning_OFF": dict(g0, online=False), "Genk": gk,
                "Genk_learning_OFF": dict(gk, online=False)}
        out = dict(champion=st["selection"]["champion"], genomes=arms, per_seed={}, pooled={})
        pooled = {k: ([], 0) for k in arms}
        for s in TEST:
            out["per_seed"][s] = {}
            for name, g in arms.items():
                rows, learn = run(ev, g, (s,), ("grids",), n_per=3)
                out["per_seed"][s][name] = dict(fit=summ(rows, learn), detectors=D.scan(rows), digest=W.digest(rows))
                pooled[name] = (pooled[name][0] + rows, pooled[name][1] + learn)
        for name, (rows, learn) in pooled.items():
            out["pooled"][name] = dict(fit=summ(rows, learn), detectors=D.scan(rows), labels=sorted({r["label"] for r in rows}))
        rows2, _ = run(ev, gk, (7208,), ("grids",), hashseed="1", n_per=3)
        out["replay_7208_genk"] = W.digest(rows2) == out["per_seed"][7208]["Genk"]["digest"]
        out["D4_integrity"] = D.scan([], fp)["D4_integrity"]
        Path(ROOT / "artifacts/wave32_v3_test.json").write_text(json.dumps(out, sort_keys=True, default=repr))
        for k, v in out["pooled"].items():
            print(k, json.dumps(v["fit"]), v["detectors"], v["labels"])
        for s in TEST:
            p = out["per_seed"][s]
            print(s, "Genk/Gen0ON %.4f Genk/Gen0OFF %.4f Gen0ON/Gen0OFF %.4f" % (
                p["Genk"]["fit"]["work"] / p["Gen0_learning_ON"]["fit"]["work"],
                p["Genk"]["fit"]["work"] / p["Gen0_learning_OFF"]["fit"]["work"],
                p["Gen0_learning_ON"]["fit"]["work"] / p["Gen0_learning_OFF"]["fit"]["work"]))
        print("replay", out["replay_7208_genk"], "D4", out["D4_integrity"])
    STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
    E.ledger_append(dict(run=f"wave32v3-{a.phase}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
