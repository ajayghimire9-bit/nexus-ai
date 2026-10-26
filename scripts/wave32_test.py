"""Wave 32 selection (dev 774-775) and one-use held-out test (grids, wave32 test 7201-7205), NOT LOCKED.
Arms: Gen 0, Gen k, and both with online learning off. Each starts from an empty library, metered by the external meter
only, with detectors on every arm and a replay of one test seed for Gen k."""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
TEST_SEEDS = (7201, 7202, 7203, 7204, 7205)


def summ(rows, learn):
    from nexus import wave32_archive as A
    f = A.fitness(rows, learn)
    f["child"] = sum(r["ext"]["child_instr"] for r in rows) + learn
    f["kernel_instr"] = sum(r["ext"]["eval_instr"] for r in rows)
    return f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--phase", choices=("select", "test"), required=True)
    a = ap.parse_args()
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave32_archive as A
    from nexus import wave32_detectors as D
    st = json.loads(W.STATE.read_text())
    ev = E.Evaluator(depth=3)
    t0 = time.perf_counter()
    fp = D.fingerprint()
    if a.phase == "select":
        R.claim("wave32", "dev", list(W.SEL_SEEDS), run_id="wave32-select", record=False)
        top = sorted(st["archive"], key=lambda e: (e["fit"]["wrong"], -e["fit"]["correct"], e["fit"]["work"]))[:3]
        sel = []
        for e in top + [next(x for x in st["archive"] if x["id"] == "g0c0")]:
            rows, learn = W.run_genome(ev, e["genome"], W.SEL_SEEDS, W.EVOL_DOMAINS)
            sel.append(dict(id=e["id"], genome=e["genome"], fit=summ(rows, learn), detectors=D.scan(rows)))
            print(e["id"], json.dumps(sel[-1]["fit"]), sel[-1]["detectors"], flush=True)
        cands = [s for s in sel if s["id"] != "g0c0" and sum(s["detectors"].values()) == 0 and s["fit"]["wrong"] == 0]
        champ = min(cands, key=lambda s: (-s["fit"]["correct"], s["fit"]["work"]))
        st["selection"] = dict(rows=sel, champion=champ["id"], champion_genome=champ["genome"])
        W.STATE.write_text(json.dumps(st, sort_keys=True, default=repr))
        print("champion", champ["id"], champ["genome"])
    else:
        R.claim("wave32", "test", list(TEST_SEEDS), run_id="wave32-test")
        g0 = dict(A.GEN0); gk = dict(st["selection"]["champion_genome"])
        arms = {"Gen0": g0, "Genk": gk, "Gen0_no_online": dict(g0, online=False), "Genk_no_online": dict(gk, online=False)}
        out = {"champion": st["selection"]["champion"], "genomes": arms, "per_seed": {}, "pooled": {}}
        pooled = {k: ([], 0) for k in arms}
        for s in TEST_SEEDS:
            out["per_seed"][s] = {}
            for name, g in arms.items():
                rows, learn = W.run_genome(ev, g, (s,), ("grids",), n_per=3)
                out["per_seed"][s][name] = dict(fit=summ(rows, learn), detectors=D.scan(rows), digest=W.digest(rows))
                pooled[name] = (pooled[name][0] + rows, pooled[name][1] + learn)
        for name, (rows, learn) in pooled.items():
            out["pooled"][name] = dict(fit=summ(rows, learn), detectors=D.scan(rows),
                                       labels=sorted({r["label"] for r in rows}))
        rows2, _ = W.run_genome(ev, gk, (7203,), ("grids",), hashseed="1", n_per=3)
        out["replay_7203_genk"] = W.digest(rows2) == out["per_seed"][7203]["Genk"]["digest"]
        out["D4_integrity"] = D.scan([], fp)["D4_integrity"]
        Path(ROOT / "artifacts/wave32_test.json").write_text(json.dumps(out, sort_keys=True, default=repr))
        for k, v in out["pooled"].items():
            print(k, json.dumps(v["fit"]), v["detectors"], v["labels"])
        for s in TEST_SEEDS:
            p = out["per_seed"][s]
            print(s, "Genk/Gen0 %.4f" % (p["Genk"]["fit"]["work"] / p["Gen0"]["fit"]["work"]))
        print("replay", out["replay_7203_genk"], "D4", out["D4_integrity"])
    E.ledger_append(dict(run=f"wave32-{a.phase}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
