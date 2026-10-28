"""x7 Part 2 diagnosis, second stage (NOT LOCKED; dev 13327 only). Separates 'missing expressiveness / wrong control' from
'search exhaustion': (1) map the learned control hypothesis onto the documented modes through its access words and check that
the documented register program (written here by the developer for the DIAGNOSIS ONLY - never given to a learner) is
consistent with the learner's histories under the learner's own traces; (2) rerun the unchanged register search with a 10x
time budget and record time-to-solution or exhaustion; (3) count the backtracking nodes. Writes artifacts/x7_dev/diag13327b.json."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import sc_platform as SCP, t7_repair as TR, u5_statesplit as SP, u5_stateful as SF
ROOT = Path(__file__).resolve().parents[1]
S = SP.S


def main(seed=13327, long_s=600.0):
    P = SCP.Project(seed, "sc_dev")
    evs = [e for t in range(1, SCP.PL.BUILD_TICKS + 1) for e in P.ticks[t]["B"]]
    outs = P.oracle_B(evs, "build_labels")
    view, _ = SCP.NexusArmSchema.learning_view(evs)
    L = TR.Learner2(view, outs, lambda x: P.oracle_B(x), seed=seed, max_s=60.0)
    hyp = L.learn_control()
    L.hyp = hyp
    ref_mode = {}
    for q, acc in hyp["access"].items():
        st = SF.INIT[P.sfam]
        for a in acc:
            st, _ = SF.step(P.sfam, st, a, 1.0, P.x3)
        ref_mode[q] = st[0]
    acc_, x_ = ("var", "acc"), ("var", "x")
    plus = lambda a, b: ("b", "+", a, b)                            # noqa: E731
    true = {"count": {}, "sum": {}}
    for (q, a) in hyp["delta"]:
        m = ref_mode[q]
        valid = SF.step(P.sfam, (m, 0, 0), a, 1.0, P.x3)[1] != [SF.Q]
        if a == "READ" and m == "open":
            true["count"][(q, a)], true["sum"][(q, a)] = plus(acc_, ("const", 1)), plus(acc_, x_)
        elif a == "ADJUST" and m == "open":
            true["sum"][(q, a)] = plus(acc_, x_)
        elif valid and (a in ("OPEN", "CLOSE")):
            true["count"][(q, a)] = true["sum"][(q, a)] = ("const", 0)
    L.hyp_lam = hyp["lam"]
    hist = L.histories() + L.extra_hist
    traces = [L._trace(hyp, e) for e, _ in hist]
    cons = {}
    for name, col in (("count", 1), ("sum", 2)):
        rg = dict(field=P.schema.val, init=0, upd=true[name])
        bad = n = 0
        for hi, ((e, o), tr) in enumerate(zip(hist, traces)):
            for p, rows in enumerate(o):
                for r in rows:
                    if r[0] in ("bill", "disputed") and r[col] is not None:
                        n += 1
                        bad += not SP._veq(L._reg_value(rg, e, tr, p), r[col])
        cons[name] = dict(slots=n, inconsistent=bad)
    nodes = [0]
    orig = TR.Learner2._bt

    def bt(self, *a, **k):
        nodes[0] += 1
        return orig(self, *a, **k)
    TR.Learner2._bt = bt
    c = time.process_time()
    regs = L.learn_registers(hyp, max_s=long_s)
    long_cpu = time.process_time() - c
    TR.Learner2._bt = orig
    out = dict(seed=seed, hyp_states=hyp["n"], ref_mode_of_state={str(k): v for k, v in ref_mode.items()},
               transitions=len(hyp["delta"]), grammar5_size=len(TR.GRAMMAR5), histories=len(hist),
               documented_program_consistent_with_learner_traces=cons,
               long_search=dict(budget_s=long_s, ok=regs is not None, cpu_s=round(long_cpu, 2), bt_nodes=nodes[0],
                                regs=None if regs is None else [dict(field=r["field"], upd={str(k): S.src(g) for k, g in r["upd"].items()})
                                                                 for r in regs[0]]))
    (ROOT / "artifacts/x7_dev/diag13327b.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, default=str)[:3000])


if __name__ == "__main__":
    main()
