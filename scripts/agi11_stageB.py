"""Phase 11 Stage B: transfer training with each stream's library FROZEN (NOT LOCKED).
  python scripts/agi11_stageB.py REP BUDGET_S [--dev] [--n=K]
The Stage A library of stream REP is loaded and frozen. 80 Stage B training tasks (manifest11.stageB_stream(rep): wider 10-14 column
multi-table compositions B1-B6; never a Suite 1 composition) are solved with the F1 configuration (fixed search + frozen library, shared
evidence policy, WALL_B) and verified natively on their hidden batches (training feedback). Then, from the SAME verified records:
  G_A0 = guide11.fit(primitive-EXPANDED programs)                  (no library productions)
  G_M  = guide11.fit(the same programs REWRITTEN with the library)  (abstr11.rewrite; library productions included)
Fitting is deterministic (counts + add-one smoothing): same records, same rule; the effective production counts of both are saved.
Rows appended + flushed; rep{r}.final.json written atomically."""
import json, os, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase11 import abstr11 as A, guide11 as G, manifest11 as M, synth11 as S, tasks11 as T, verify11 as V  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
REL_B, SC_B, WALL_B = 2000, 350000, 6.0       # WORK caps bind; the wall cap is a logged safety


def jdump(x):
    return json.dumps(x, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o))


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), M.N_B)
    srcA = ROOT / ("artifacts/agi11_dev/stageA" if dev else "artifacts/agi11_stageA") / f"rep{rep}.final.json"
    out = ROOT / ("artifacts/agi11_dev/stageB" if dev else "artifacts/agi11_stageB")
    out.mkdir(parents=True, exist_ok=True)
    if not dev and (out / f"rep{rep}.final.json").exists():
        raise SystemExit("streams are never rerun")
    lib = A.load_library(json.loads(srcA.read_text())["library"])
    if dev:
        b = M.RANGES[("agi11", "dev")].start + 700 + 100 * rep
        tasks = [(T.COMPOSE[i % len(T.COMPOSE)], b + i) for i in range(n)]
    else:
        tasks = M.stageB_stream(rep)[:n]
    rec, reached = [], 0
    with open(out / f"rep{rep}.tasks.jsonl", "a") as tf:
        for i, (kind, seed) in enumerate(tasks):
            if time.time() - T0 > budget:
                tf.write(jdump(dict(event="deadline", i=i)) + "\n")
                break
            learner, adm, hidden = T.build(kind, seed)
            r = S.solve(learner, lib, S.Costs(), S.Budget(REL_B, SC_B, WALL_B), evidence=lambda adm=adm: adm["evidence"])
            v = V.verify(r["program"], lib, hidden) if r["program"] is not None else None
            ok = bool(v and v["ok"])
            tf.write(jdump(dict(i=i, task=learner["id"], family=kind, outcome=r["outcome"], verified=ok, wrong=bool(v and not v["ok"]), counters=r["counters"],
                                wall=r["wall"], wall_bound=r["wall_bound"], size=r.get("size"), program=r["program"], expanded=r["expanded"],
                                uses=sorted({f for f in lib if f in jdump(r["program"])}) if r["program"] is not None else [], t=round(time.time() - T0, 1))) + "\n")
            tf.flush()
            reached = i + 1
            if ok:
                rec.append(r["expanded"])
    tg = time.time()
    ga0, ia0 = G.fit(rec, ())
    rw = [A.rewrite(p, lib) for p in rec]
    gm, im = G.fit(rw, sorted(lib))
    fit_s = round(time.time() - tg, 4)
    final = dict(rep=rep, dev=dev, tasks_planned=len(tasks), tasks_reached=reached, records=len(rec), G_A0=ga0, G_M=gm, info_A0=ia0, info_M=im,
                 rewritten_with_call=sum(A._has_call(p) for p in rw), fit_s=fit_s, library=sorted(lib), wall=round(time.time() - T0, 1))
    tmp = out / f"rep{rep}.final.json.tmp"
    tmp.write_text(jdump(final))
    os.replace(tmp, out / f"rep{rep}.final.json")
    rows = [json.loads(l) for l in open(out / f"rep{rep}.tasks.jsonl") if '"event"' not in l]
    print(f"rep{rep}", "reached", reached, "verified", sum(x["verified"] for x in rows), "wrong", sum(x["wrong"] for x in rows), "records", len(rec),
          "rewritten_with_call", final["rewritten_with_call"], "wall", final["wall"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
