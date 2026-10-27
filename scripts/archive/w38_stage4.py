"""Wave 38 Stage 4 (NOT LOCKED): long-duration continual study + external PROSE ledger.
--part program: a 6-phase program stream (strings -> graphs -> tables -> strings (return) -> graphs (return) -> grids), fresh
            instances, from an EMPTY library: Fresh vs Learner-no-gate vs Learner-regime-memory (frozen at cd02435).
--part world : a 10,000-step SwitchGrid stream (noise 0.15, slip 0.1, hazard 1/200): N1 vs fixed-model vs reactive.
--part prose : external ledger, run once: all usable PROSE Transformation.Text tasks (first 3 examples public, the rest
            held out); Fresh vs Repr (prior fitted from internal strings + tables source tasks); held-out pass rate."""
import argparse, glob, json, os, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--part", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from nexus import w38_eval as WE, w38_online as O, w38_lang as L
    import w38_online as D
    t0 = time.perf_counter(); p = Path(a.out)
    res = json.loads(p.read_text()) if p.exists() else {}
    ev = WE.Eval()
    if a.part == "program":
        phases = ["strings", "graphs", "tables", "strings", "graphs", "grids"]
        if "phase_of" not in res:
            ts, ph = [], []
            for i, dom in enumerate(phases):
                seg = D.program_stream(f"stage4:{i}", (dom,), "all", 1)
                ts += seg; ph += [i] * len(seg)
            res["phase_of"] = ph
            Path(ROOT / "artifacts/w38_stage4_tasks.json").write_text(json.dumps(ts, default=repr))
        ts = json.loads(Path(ROOT / "artifacts/w38_stage4_tasks.json").read_text())
        for name, g in (("Fresh", None), ("Learner-regime-memory", dict(O.BASELINE_80F9CC2, gate="regime")),
                        ("Learner-no-gate", O.BASELINE_80F9CC2)):
            if name in res:
                continue
            c = D.stream_cost(ev, ts, g, "stage4")
            c["phase_work"] = [sum(w for w, q in zip(c["curve"], res["phase_of"]) if q == i) for i in range(len(phases))]
            res[name] = c; p.write_text(json.dumps(res, sort_keys=True, default=repr))
            print(name, round(c["work"] / 1e9, 1), [round(x / 1e9, 1) for x in c["phase_work"]], c["correct"], c["n"], "wrong", c["wrong"],
                  "declared", c["declared"], flush=True)
            if time.perf_counter() - t0 > 600:
                break
    elif a.part == "world":
        import w38_world_long as WL
        from nexus.wave31_evaluator import instructions
        for ag in ("reactive", "fixed-model", "N1-BOCPD"):
            res[ag] = WL.run(ag, "stage4-world", T=10000, instr=lambda: instructions(os.getpid()))
            print(ag, res[ag], flush=True)
        p.write_text(json.dumps(res, sort_keys=True, default=repr))
    else:
        from nexus import w38_domains as Dm
        progs = [t["teacher"] for t in Dm.stream("stage4-prose-src", ("strings", "tables"), "source", 2)]
        ch = ev.child(); rep = ev.call(ch, {"cmd": "fit", "kind": "repr", "programs": progs}); ch.close()
        for f in sorted(glob.glob(str(ROOT / "artifacts/external/prose/*.json"))):
            name = Path(f).stem
            if name in res:
                continue
            ex = json.load(open(f))["Examples"]
            if len(ex) < 4 or any(len(e["Input"]) != 1 for e in ex):
                res[name] = {"label": "SKIPPED_FORMAT"}; continue
            t = {"public": [[e["Input"][0], e["Output"]] for e in ex[:3]], "query": ex[3]["Input"][0], "answer": ex[3]["Output"],
                 "teacher": None, "heldout": [[e["Input"][0], e["Output"]] for e in ex[3:]]}
            res[name] = {}
            for arm, prior in (("Fresh", None), ("Repr", rep["prior"])):
                ch = ev.child()
                tt = dict(t, teacher=[{"op": "strip"}])            # no oracle for external tasks: probes are refused
                r = ev.solve(ch, tt, 3, f"prose:{name}", prior=prior, budget=2_000_000)
                ch.close()
                held = None
                if r.get("candidate"):
                    held = sum(L.key(L.run(r["candidate"], x)) == L.key(y) for x, y in t["heldout"]) / len(t["heldout"])
                res[name][arm] = dict(label=r["label"], heldout_pass=held, work=r["work"])
            p.write_text(json.dumps(res, sort_keys=True, default=repr))
        for arm in ("Fresh", "Repr"):
            rs = [v[arm] for v in res.values() if arm in v]
            print(arm, "tasks", len(rs), "UNIQUE", sum(r["label"] == "exhaustive_UNIQUE" for r in rs),
                  "held-out all-pass", sum(r["heldout_pass"] == 1.0 for r in rs if r["heldout_pass"] is not None),
                  "UNIQUE but held-out fail", sum(r["label"] == "exhaustive_UNIQUE" and (r["heldout_pass"] or 0) < 1 for r in rs),
                  "work %.1fG" % (sum(r["work"] for r in rs) / 1e9))
    WE.ledger_append(dict(run=f"w38-stage4-{a.part}", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
