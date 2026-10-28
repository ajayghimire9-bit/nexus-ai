"""Pillar 4 dev experiment (NOT LOCKED).  python scripts/u5_p4.py start | arm KIND | final
start: the learner promoted by Pillars 2-3 wakes on SRC_TRAIN (hybrid, 4 s/task) -> shared start experience (charged to
       every arm alike; reported once).
arm:   KIND in none | random | fixed | boundary: practise for 240 CPU s (4 s per practice task; generation, quick
       boundary checks and solving all inside the 240 s), then the IDENTICAL update for every arm (count costs + affinity
       refit on all experience; library re-admitted by utility on ADM, <= 200 s) and the zero-forgetting acceptance
       (every src task solved at start must still be solved), then DEV (selection) and HELD (report) evaluation.
Promotion (predeclared): boundary is promoted iff its DEV generalising solves exceed every other arm's by >= 2, or tie
within 1 with >= 10% less DEV search CPU than every other arm; otherwise no curriculum is promoted (the start learner)."""
import pickle, sys, time
from pathlib import Path
from u5_common import ROOT, SRC_TRAIN, ADM, DEV, HELD, save, load, node_dump, node_load, learner_cfg, eval_suite
from nexus import u5_curriculum as CU

RUN = ROOT / "runs/experimental/u5"
P = load("p2_policy.json")
pol = load("p2.json")["promoted"]
p3 = load("p3.json")["promoted"]
libs = load("p3_libs.json")
cfg0 = learner_cfg(pol, P)
lib0 = [] if p3 == "none" else [(f, p, node_load(b)) for f, p, b in libs[p3]]
cmd = sys.argv[1]
if cmd == "start":
    c0 = time.process_time()
    exp, cpu = CU.wake(SRC_TRAIN(), cfg0, lib0, 4.0)
    pickle.dump(exp, open(RUN / "p4_exp0.pkl", "wb"))
    save("p4_start.json", dict(policy=pol, library=p3, solved=sorted(exp.solved_ids), n_solved=len(exp.solved_ids), weak=len(exp.weak),
                               max_size=exp.max_size, cpu_s=round(time.process_time() - c0, 3)))
    print("start solved", len(exp.solved_ids), "weak", len(exp.weak), "max_size", exp.max_size)
elif cmd == "arm":
    kind = sys.argv[2]
    exp = pickle.load(open(RUN / "p4_exp0.pkl", "rb"))
    solved0 = set(exp.solved_ids)
    src = SRC_TRAIN()
    c0 = time.process_time()
    exp, plog = CU.practise(kind, cfg0, lib0, src, exp, 240.0, 4.0, seed=0)
    t1 = time.process_time()
    cfg1 = CU.update(cfg0, exp)
    lib1, alog, acpu = CU.library_from(exp, ADM(), cfg1, 2.0, max_s=200.0)
    cfg2, lib2, lost = CU.accept_no_forgetting(cfg0, lib0, cfg1, lib1, src, solved0, 4.0)
    t2 = time.process_time()
    out = dict(kind=kind, practice=plog, practice_cpu_s=round(t1 - c0, 3), update_cpu_s=round(t2 - t1, 3), admission_cpu_s=round(acpu, 3),
               accepted=not lost, lost=lost, n_lib=len(lib2), library=[[f, p, node_dump(b)] for f, p, b in lib2],
               op_cost=cfg2["op_cost"], weights=cfg2["weights"], bias=cfg2["bias"],
               dev=eval_suite(DEV(), cfg2, lib2), held=eval_suite(HELD(), cfg2, lib2))
    save(f"p4_{kind}.json", out)
    print(kind, plog, "accepted", not lost, "dev", out["dev"]["correct"], out["dev"]["cpu_s"], "held", out["held"]["correct"], out["held"]["cpu_s"])
else:
    ev = {k: load(f"p4_{k}.json") for k in ("none", "random", "fixed", "boundary")}
    b = ev["boundary"]["dev"]
    others = [ev[k]["dev"] for k in ("none", "random", "fixed")]
    promoted = all(b["correct"] >= o["correct"] + 2 for o in others) or \
        all(abs(b["correct"] - o["correct"]) <= 1 and b["correct"] >= o["correct"] - 1 and b["cpu_s"] <= 0.9 * o["cpu_s"] for o in others)
    save("p4.json", dict(promoted="boundary" if promoted else "none_start_learner",
                         table={k: dict(dev=ev[k]["dev"]["correct"], dev_cpu=ev[k]["dev"]["cpu_s"], held=ev[k]["held"]["correct"],
                                        held_cpu=ev[k]["held"]["cpu_s"], dev_wrong=ev[k]["dev"]["wrong_generalisation"],
                                        held_wrong=ev[k]["held"]["wrong_generalisation"], practice=ev[k]["practice"], accepted=ev[k]["accepted"],
                                        n_lib=ev[k]["n_lib"]) for k in ev}))
    print("PROMOTED", promoted)
