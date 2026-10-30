"""Phase 11 Stage A: discover executable functions from experience, one numeric-seeded stream (NOT LOCKED).
  python scripts/agi11_stageA.py REP BUDGET_S [--dev] [--n=K]
REP 0 | 1: manifest11.source_stream(rep) (60 source tasks, 5-8 columns, 8 computational families in shuffled cycles; dev: agi11/dev seeds).
WAKE  each task is solved by synth11 with the FIXED search and the CURRENT library (empty at the start), the shared evidence policy
      (one evidence request) and the Stage A training budget (relational pops <= REL_A, micro-evaluations <= SC_A, wall <= WALL_A);
      the submission is verified natively (DuckDB) on the task's hidden batches as TRAINING FEEDBACK (source data only).
      The learner sees anonymous task ids; the family name is logged for analysis only and never reaches synth11 or abstr11.
SLEEP every SLEEP_EVERY tasks: abstr11.candidates over every VERIFIED solution so far (distinct projects) -> abstr11.admit (k_min = 3
      verified projects, validation batches, positive compression, <= 3 per sleep) -> the library grows. No dreams are used.
Rows appended + flushed (artifacts/agi11_stageA/rep{r}.tasks.jsonl, .abstraction.jsonl); the final library / programs / acquisition
record are written atomically to rep{r}.final.json. A stream that hits its budget stops launching tasks and reports the tasks reached."""
import json, os, sys, time
T0 = time.time()
from pathlib import Path  # noqa: E402
from nexus.de_phase11 import abstr11 as A, core11 as C, manifest11 as M, synth11 as S, tasks11 as T, verify11 as V  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
REL_A, SC_A, WALL_A, SLEEP_EVERY = 6000, 1200000, 12.0, 10     # WORK caps bind (pops, micro-evaluations); the wall cap is a logged safety


def jdump(x):
    return json.dumps(x, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o))


def write_atomic(p, obj):
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(jdump(obj))
    os.replace(tmp, p)


def main(rep, budget, *flags):
    rep, budget, dev = int(rep), float(budget), "--dev" in flags
    n = next((int(f.split("=")[1]) for f in flags if f.startswith("--n=")), M.N_A)
    out = ROOT / ("artifacts/agi11_dev/stageA" if dev else "artifacts/agi11_stageA")
    out.mkdir(parents=True, exist_ok=True)
    if dev:
        b = M.RANGES[("agi11", "dev")].start + 400 + 200 * rep
        tasks = [(T.SOURCE[i % len(T.SOURCE)], b + i) for i in range(n)]
    else:
        tasks = M.source_stream(rep)[:n]
        if (out / f"rep{rep}.final.json").exists():
            raise SystemExit("streams are never rerun")
    lib, programs, admin, vis, acq, alog_all = {}, [], {}, {}, [], []
    tf, af = open(out / f"rep{rep}.tasks.jsonl", "a"), open(out / f"rep{rep}.abstraction.jsonl", "a")
    reached = 0
    for i, (kind, seed) in enumerate(tasks):
        if time.time() - T0 > budget:
            tf.write(jdump(dict(event="deadline", i=i)) + "\n")
            tf.flush()
            break
        learner, adm, hidden = T.build(kind, seed)
        r = S.solve(learner, lib, S.Costs(), S.Budget(REL_A, SC_A, WALL_A), evidence=lambda adm=adm: adm["evidence"])
        v = V.verify(r["program"], lib, hidden) if r["program"] is not None else None
        verified, wrong = bool(v and v["ok"]), bool(v and not v["ok"])
        row = dict(i=i, task=learner["id"], family=kind, outcome=r["outcome"], verified=verified, wrong=wrong, counters=r["counters"], log=r["log"],
                   wall=r["wall"], wall_bound=r["wall_bound"], size=r.get("size"), library=sorted(lib), program=r["program"], expanded=r["expanded"],
                   uses=sorted({f for f in lib if f in jdump(r["program"])}) if r["program"] is not None else [], native_executions=(v or {}).get("native_executions", 0),
                   conformance_mismatch=(v or {}).get("conformance_mismatch"), t=round(time.time() - T0, 1))
        tf.write(jdump(row) + "\n")
        tf.flush()
        reached = i + 1
        if verified:
            programs.append((learner["id"], r["expanded"]))
            admin[learner["id"]] = adm["valid"]
            vis[learner["id"]] = [(learner["inputs"][k], learner["expected"][k]) for k in ("vis_a", "vis_b")]
        if (i + 1) % SLEEP_EVERY == 0 and programs:
            ts = time.time()
            cands, pairs = A.candidates(programs, lib)
            alog = []
            new = A.admit(cands, programs, admin, lib, vis, alog)
            for name, fn, rec in new:
                lib[name] = fn
                acq.append(dict(rec, acquired_after_task=i + 1, t=round(time.time() - T0, 1)))
            for rec in alog:
                af.write(jdump(dict(rec, sleep_after=i + 1, candidates=len(cands), pairs=pairs, sleep_s=round(time.time() - ts, 2))) + "\n")
            af.flush()
            alog_all += alog
    tf.close()
    af.close()
    final = dict(rep=rep, dev=dev, tasks_planned=len(tasks), tasks_reached=reached, verified=len(programs), library=lib, acquisitions=acq,
                 programs=programs, wall=round(time.time() - T0, 1), limits=dict(REL_A=REL_A, SC_A=SC_A, WALL_A=WALL_A, SLEEP_EVERY=SLEEP_EVERY, K_MIN=A.K_MIN))
    write_atomic(out / f"rep{rep}.final.json", final)
    rows = [json.loads(l) for l in open(out / f"rep{rep}.tasks.jsonl") if '"event"' not in l]
    print(f"rep{rep}", "reached", reached, "verified", sum(x["verified"] for x in rows), "wrong", sum(x["wrong"] for x in rows), "library",
          {k: (v["class"], v["kind"], v["ops"]) for k, v in lib.items()}, "wall", final["wall"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
