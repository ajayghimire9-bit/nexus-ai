"""Trial 6 (NOT LOCKED). Three independent sequences (seeded orders) of 24 tasks from families unfamiliar to the u5
learner: the energy domain (7 families) + I families, t7/tdev seeds 1-4. Every arm starts from the same memory-less count
learner; after task 8 the learner EVOLVES to L' (count + autopsy cuts) except arm (a). 3 s per task. CPU of evolution,
migration, replay and contract checking is charged.
(a) Unchanged_Learner        L throughout; memory = counts from its verified solutions
(b) Evolution_Memory_Reset   L' after task 8 with memory wiped (no counts; cuts compiled from later solved searches only)
(c) Evolution_Full_Replay    L' after task 8; ALL 8 past tasks re-solved with L to rebuild counts and autopsy evidence
(d) Joint_Translator         L' after task 8; T_mem carries counts, marks unsolved UNKNOWN, replays 2 stored tasks; the
                             contract is machine-checked
Metric: generalising solves on tasks 9-24 and total CPU. KEEP iff (d) has more solves than (a), or equal solves with
>= 10% less CPU; and (d) solves >= (c) with less total CPU; and (d)'s contract check passes."""
import json, random, sys, time
sys.path.insert(0, "scripts")
from u5_common import ROOT, K, W, load, learner_cfg
from nexus import t7_seeds, t7_world, t7_memory as M, seed_registry as R  # noqa: F401
ART = ROOT / "artifacts/t7_dev"
fams = [f for f in W.FAMILIES if f[0] in "EI"]
seeds = list(R.REGISTRY[("t7", "tdev")])[1:5]
BUD = 3.0


def cfg_from(counts):
    c = K.default_config("count")
    if counts:
        c["op_cost"] = _costs(counts)
    return c


def _costs(counts):
    from nexus.oop_synthesizer import BINARY, UNARY
    import math
    ops = UNARY + BINARY
    tot = sum(counts.get(o, 0) + 0.5 for o in ops)
    nl = {o: -math.log2((counts.get(o, 0) + 0.5) / tot) for o in ops}
    m = min(nl.values())
    return {o: int(min(3, 1 + round((nl[o] - m) / 2))) for o in ops}


def run(arm, seq):
    mem = dict(programs={}, counts={}, unsolved=[])
    cuts, searches_after = frozenset(), []
    byid = {t.tid: t for t in seq}
    solved, cpu, log = 0, 0.0, []
    contract = None
    for i, t in enumerate(seq):
        if i == 8 and arm != "a":
            t0 = time.process_time()
            if arm == "b":
                mem = dict(programs={}, counts={}, unsolved=[])
            elif arm == "c":
                reps = []
                for tid in list(mem["programs"]) + list(mem["unsolved"]):
                    node, s = M.solve(byid[tid], cfg_from(mem["counts"]), frozenset(), BUD)
                    if node is not None:
                        reps.append((s, node))
                cuts, _ = M.autopsy(reps)
                prot = set().union(*[M.subtree_patterns(p) for p in mem["programs"].values()]) if mem["programs"] else set()
                cuts = frozenset(cuts - prot)
            else:
                stored = [byid[tid] for tid in list(mem["programs"])[:2]]
                old = mem
                mem, n_rep = M.translate(mem, stored, cfg_from(mem["counts"]), BUD, M.solve)
                cuts = mem["cuts"]
                contract = M.check_contract(old, mem, byid)
            cpu += time.process_time() - t0
        t0 = time.process_time()
        node, s = M.solve(t, cfg_from(mem["counts"]), cuts, BUD)
        cpu += time.process_time() - t0
        ok = node is not None and W.correct_on(t, node) == 1.0
        if node is not None and all(K._ok(K._safe_ev(node, e), y) for e, y in zip(t.train, t.y_train)):
            mem["programs"][t.tid] = node
            mem["counts"] = dict(K.op_counts(list(mem["programs"].values())))
            if arm == "b" and i >= 8:
                searches_after.append((s, node))
                if len(searches_after) in (4, 8):                       # reset arm compiles cuts from new evidence only
                    c2, _ = M.autopsy(searches_after)
                    prot = set().union(*[M.subtree_patterns(p) for p in mem["programs"].values()])
                    cuts = frozenset(c2 - prot)
        else:
            mem["unsolved"].append(t.tid)
        if i >= 8:
            solved += ok
        log.append(dict(i=i, task=t.tid, ok=ok, cut=getattr(s, "n_cut", 0)))
    return dict(solved_after=solved, cpu_s=round(cpu, 3), n_cuts=len(cuts), contract=contract, log=log)


out = {}
for q in range(3):
    rnd = random.Random(f"t7-seq-{q}")
    pool = [(f, s) for f in fams for s in seeds]
    seq = [W.Task(f"{f}#{s}", f, s) for f, s in rnd.sample(pool, 24)]
    out[q] = {arm: run(arm, seq) for arm in "abcd"}
    print(q, {a: (r["solved_after"], r["cpu_s"], r["n_cuts"]) for a, r in out[q].items()}, out[q]["d"]["contract"], flush=True)
tot = {a: dict(solved=sum(out[q][a]["solved_after"] for q in out), cpu_s=round(sum(out[q][a]["cpu_s"] for q in out), 3)) for a in "abcd"}
d, a, c = tot["d"], tot["a"], tot["c"]
keep = ((d["solved"] > a["solved"]) or (d["solved"] == a["solved"] and d["cpu_s"] <= 0.9 * a["cpu_s"])) and \
    d["solved"] >= c["solved"] and d["cpu_s"] < c["cpu_s"] and all(out[q]["d"]["contract"][0] for q in out)
(ART / "t6.json").write_text(json.dumps(dict(sequences=out, totals=tot, verdict="KEPT" if keep else "REJECTED"), indent=1, default=str))
print("TOTALS", tot, "VERDICT", "KEPT" if keep else "REJECTED")
