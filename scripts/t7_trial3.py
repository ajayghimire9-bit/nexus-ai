"""Trial 3 (NOT LOCKED). Source families U, T (t7/tsrc 0 streams); withheld families S (savepoints; new symbols) and C
(composition), learned from a t7/tsrc 1 stream and scored exactly on fresh held-out streams t7/tdev 0-2.
(a) joint invention: bounded-space UNSAT proofs for U and T (complete search) + ddmin -> minimal failure constraints;
    joint search for ONE representation (stack | queue | none) explaining both (retrodiction-cut op domains); the tool =
    (representation, the op vocabulary the joint solution uses); withheld family = search with the representation fixed
    and ops restricted to the tool vocabulary.
(b) deeper direct search: every representation x every op, NO tool, NO retrodiction, CPU budget per withheld family =
    (a)'s total CPU (proofs + invention, amortised over the 2 withheld families) + (a)'s own withheld-family CPU.
(c) library from successes: the bounded space (one register) - the only tasks it solves are its own successes.
(d) random abstraction: a random representation and a random op vocabulary of the tool's size.
KEEP iff (a) solves strictly more withheld held-out streams than (b), (c) and (d) at equal compute and its tool is used
by the withheld family S, whose symbols never occur in U or T (not memorisation)."""
import json, random, sys, time
sys.path.insert(0, "src")
from pathlib import Path
from nexus import t7_seeds, t7_jointtool as J, seed_registry as R  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/t7_dev"
S0, S1 = list(R.REGISTRY[("t7", "tsrc")])[:2]
EVAL = list(R.REGISTRY[("t7", "tdev")])[:3]


def data(fam, seed):
    ev = J.gen(fam, seed)
    return ev, J.reference(fam, ev)


def score(fam, rep, a):
    if rep is None:
        return 0
    n = 0
    for s in EVAL:
        ev, out = data(fam, s)
        a2 = dict(a)
        a2.update({("emit", k): v for k, v in J.emits(ev, out).items()})
        got = J.run_program(rep, a2, ev)
        n += all([tuple(r) for r in g] == [tuple(r) for r in w] for g, w in zip(got, out))
    return n


t0 = time.process_time()
proof = {}
mins = {}
for fam in "UT":
    ev, out = data(fam, S0)
    H = J.histories(ev, out)
    uns, nodes = J.bounded_unsat(H, J.FAMS[fam])
    mins[fam] = J.ddmin_unsat(H, J.FAMS[fam]) if uns else []
    proof[fam] = dict(unsat=uns, nodes=nodes, minimal_histories=len(mins[fam]), of=len(H))
# joint: one representation must explain BOTH tasks (full data), with retrodiction-cut domains
tool = None
for rep in ("none", "queue", "stack"):
    sols = {}
    for fam in "UT":
        ev, out = data(fam, S0)
        H = J.histories(ev, out)
        dom = J.retrodict_domains(H, J.FAMS[fam])
        r, a, nodes, ex = J.search(mins[fam] + H, J.FAMS[fam], (rep,), 120.0, dom)
        sols[fam] = a
    if all(sols.values()):
        vocab = sorted({op for a in sols.values() for op in a.values()})
        tool = dict(rep=rep, vocab=vocab, sols=sols)
        break
inv_cpu = time.process_time() - t0
res = {}
for fam in "SC":
    ev, out = data(fam, S1)
    H = J.histories(ev, out)
    row = {}
    t1 = time.process_time()
    if tool:
        dom = {s: set(tool["vocab"]) for s in J.FAMS[fam]}
        rep, a, nodes, ex = J.search(H, J.FAMS[fam], (tool["rep"],), 300.0, dom)
        a_cpu = time.process_time() - t1
        row["a_joint"] = dict(solved_streams=score(fam, rep, a) if a else 0, cpu_s=round(a_cpu + inv_cpu / 2, 3), program=str(a),
                              exhausted=ex)
    else:
        a_cpu = 0.0
        row["a_joint"] = dict(solved_streams=0, cpu_s=round(inv_cpu / 2, 3), program=None)
    budget = row["a_joint"]["cpu_s"]
    t2 = time.process_time()
    rep, a, nodes, ex = J.search(H, J.FAMS[fam], ("none", "queue", "stack"), budget)
    row["b_direct"] = dict(solved_streams=score(fam, rep, a) if a else 0, cpu_s=round(time.process_time() - t2, 3), timed_out=not ex and a is None)
    t3 = time.process_time()
    rep, a, nodes, ex = J.search(H, J.FAMS[fam], ("none",), budget, {s: {(g, "none") for g in J.G} for s in J.FAMS[fam]})
    row["c_library_successes"] = dict(solved_streams=score(fam, rep, a) if a else 0, cpu_s=round(time.process_time() - t3, 3))
    rnd = random.Random(fam)
    rrep = rnd.choice(["none", "queue"])
    rv = rnd.sample(J.OPS, len(tool["vocab"]) if tool else 6)
    t4 = time.process_time()
    rep, a, nodes, ex = J.search(H, J.FAMS[fam], (rrep,), budget, {s: set(rv) for s in J.FAMS[fam]})
    row["d_random_abstraction"] = dict(solved_streams=score(fam, rep, a) if a else 0, cpu_s=round(time.process_time() - t4, 3), rep=rrep)
    res[fam] = row
    print(fam, {k: (v["solved_streams"], v["cpu_s"]) for k, v in row.items()}, flush=True)
A = sum(r["a_joint"]["solved_streams"] for r in res.values())
others = {k: sum(r[k]["solved_streams"] for r in res.values()) for k in ("b_direct", "c_library_successes", "d_random_abstraction")}
keep = tool is not None and all(A > v for v in others.values()) and res["S"]["a_joint"]["solved_streams"] > 0
src = J.class_source(tool["rep"], {**tool["sols"]["T"], ("emit", "READ"): True}, "T") if tool else None
(ART / "t3.json").write_text(json.dumps(dict(proof=proof, tool=dict(rep=tool["rep"], vocab=tool["vocab"], sols={k: str(v) for k, v in tool["sols"].items()}) if tool else None,
                                             invention_cpu_s=round(inv_cpu, 3), withheld=res, totals=dict(a_joint=A, **others),
                                             invented_class_T=src, verdict="KEPT" if keep else "REJECTED"), indent=1))
print("proof", proof, "tool", tool and (tool["rep"], tool["vocab"]), "totals", A, others, "VERDICT", "KEPT" if keep else "REJECTED")
