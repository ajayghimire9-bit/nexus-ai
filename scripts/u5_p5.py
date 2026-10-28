"""Pillar 5 dev experiment (NOT LOCKED).  python scripts/u5_p5.py evolve | arm NAME | final
L0 = the learner promoted by Pillars 2-4 (as an evolvable_learner L; 1.5 s per task inside improvement).
evolve: meta_evolve M on META-TRAINING families only (L + C): improvement pool tsrc 5-9 (70 tasks), meta-validation
        tadm 2 (14 tasks); (1 + 3) evolution, 2 generations, b_meta = 60 CPU s per improver run. All CPU charged to
        M_evolved.
arm:    NAME in M0 | Scalar_Tuning | Random_Modification | M_evolved: from the SAME L0 with the SAME budget B = 120 CPU s
        on the UNSEEN IoT families (improvement pool: I x tsrc 0-4, 35 tasks), seeds 0, 1, 2; every descendant L is
        evaluated on I x tdev 0-2 (21 tasks; selection) and I x theld 0-2 (21 tasks; report), 2 s per task.
Promotion (predeclared): M_evolved's descendants are promoted iff their mean DEV generalising solves (over the 3 seeds)
exceed those of every other arm AND of L0 itself; then the deployed learner = M_evolved run once more from L0 (B = 120 s)
on a mixed pool (L + C + I, tsrc 0-1)."""
import copy, json, sys, time
from u5_common import LC, IOT, ALL, K, W, save, load, node_load, learner_cfg, suite, eval_suite
from nexus import evolvable_learner as EL, meta_improver as MI


def L0():
    P = load("p2_policy.json")
    pol = load("p2.json")["promoted"]
    p4 = load("p4.json")["promoted"]
    if p4 == "boundary":
        a = load("p4_boundary.json")
        cfg = learner_cfg(pol, dict(op_cost=a["op_cost"], weights=a["weights"], bias=a["bias"]))
        lib = [(f, p, node_load(b)) for f, p, b in a["library"]]
    else:
        cfg = learner_cfg(pol, P)
        p3 = load("p3.json")["promoted"]
        lib = [] if p3 == "none" else [(f, p, node_load(b)) for f, p, b in load("p3_libs.json")[p3]]
    if cfg["policy"] != "exec":                      # an evolvable L is an exec-policy learner; baseline/count = P 0
        cfg = dict(cfg, policy="exec", P=0)
    return EL.from_config(cfg, lib, per_task_s=1.5)


def evaluate_L(L, tasks):
    cfg, lib = EL.to_config(L)
    return eval_suite(tasks, cfg, lib, budget=2.0)


ARMS = {"M0": lambda: MI.M0, "Scalar_Tuning": MI.scalar_tuning, "Random_Modification": MI.random_modification}
cmd = sys.argv[1]
if cmd == "evolve":
    L = L0()
    pool, val = suite(LC, "tsrc", range(5, 10)), suite(LC, "tadm", range(2, 3))
    M, hist, cpu = MI.meta_evolve(L, pool, val, 60.0, gens=2, lam=3, seed=11, log_fn=lambda h: print(h, flush=True))
    save("p5_evolve.json", dict(M_evolved=M, history=hist, cpu_s=round(cpu, 3)))
    print("M_evolved", M, "cpu", round(cpu, 1))
elif cmd == "arm":
    name = sys.argv[2]
    M = load("p5_evolve.json")["M_evolved"] if name == "M_evolved" else ARMS[name]()
    L = L0()
    pool = suite(IOT, "tsrc", range(0, 5))
    dev, held = suite(IOT, "tdev", range(0, 3)), suite(IOT, "theld", range(0, 3))
    runs = []
    for seed in (0, 1, 2):
        Ld, log, cpu = MI.improve(M, L, pool, 120.0, seed=seed)
        runs.append(dict(seed=seed, improve_cpu_s=round(cpu, 3), n_rounds=len(log), accepted=sum(x["accepted"] for x in log),
                         edits=[x["edit"] for x in log if x["accepted"]], dev=evaluate_L(Ld, dev), held=evaluate_L(Ld, held),
                         L=json.loads(json.dumps(Ld, default=str))))
        print(name, seed, "dev", runs[-1]["dev"]["correct"], "held", runs[-1]["held"]["correct"], "accepted", runs[-1]["accepted"], flush=True)
    save(f"p5_{name}.json", dict(arm=name, M=M, runs=runs))
elif cmd == "base":
    L = L0()
    save("p5_L0.json", dict(dev=evaluate_L(L, suite(IOT, "tdev", range(0, 3))), held=evaluate_L(L, suite(IOT, "theld", range(0, 3)))))
elif cmd == "final":
    names = ("M0", "Scalar_Tuning", "Random_Modification", "M_evolved")
    ev = {n: load(f"p5_{n}.json") for n in names}
    base = load("p5_L0.json")
    mean = {n: sum(r["dev"]["correct"] for r in ev[n]["runs"]) / 3 for n in names}
    promoted = all(mean["M_evolved"] > mean[n] for n in names if n != "M_evolved") and mean["M_evolved"] > base["dev"]["correct"]
    table = {n: dict(dev_mean=round(mean[n], 3), dev=[r["dev"]["correct"] for r in ev[n]["runs"]],
                     held=[r["held"]["correct"] for r in ev[n]["runs"]], dev_cpu=[r["dev"]["cpu_s"] for r in ev[n]["runs"]],
                     held_cpu=[r["held"]["cpu_s"] for r in ev[n]["runs"]], accepted=[r["accepted"] for r in ev[n]["runs"]]) for n in names}
    table["L0"] = dict(dev=base["dev"]["correct"], held=base["held"]["correct"], dev_cpu=base["dev"]["cpu_s"], held_cpu=base["held"]["cpu_s"])
    out = dict(promoted=promoted, table=table, meta_evolution_cpu_s=load("p5_evolve.json")["cpu_s"])
    if promoted:
        Ld, log, cpu = MI.improve(ev["M_evolved"]["M"], L0(), suite(ALL, "tsrc", range(0, 2)), 120.0, seed=7)
        out["deployed_L"] = json.loads(json.dumps(Ld, default=str))
        out["deploy_cpu_s"] = round(cpu, 3)
    save("p5.json", out)
    print("PROMOTED", promoted, table)
