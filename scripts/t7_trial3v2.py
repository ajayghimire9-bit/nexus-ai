"""Trial 3 v2 (NOT LOCKED; priority B, after the owner addendum). Corrections vs v1: the invented TOOL is the
representation (a stack of snapshots of x) plus its reusable operations (push / pop_restore / pop_discard) - callers may
combine them with ANY primitive update g in G (v1 wrongly restricted callers to the op combinations seen in U and T).
Every arm has the same primitive grammar (G x stack actions x representation in {none, queue, stack}) and the same CPU per
withheld family. Retrodiction is a candidate-explanation filter (it only orders / cuts op domains consistent with the
abduced emitted states; several mechanisms may still fit). Scoring: exact outputs on FRESH held-out streams (t7/tdev 0-2:
new keys, new continuations) - never used during learning.
Arms per withheld family (S: savepoints with new symbols; C: composition):
  a  tool: representation fixed to the invented one; ops = G x tool actions; retrodiction-cut domains
  b  direct: all representations x all ops; no tool, no retrodiction
  b2 direct + retrodiction (isolates retrodiction from the tool)
  c  library from successes: one register only (the bounded space)
  d  random representation (queue or none) with the full op grammar
Budget per family = max(a's CPU, 2 s) given to every arm. PROMOTION CANDIDATE iff a solves strictly more held-out streams
than b, b2, c and d in total AND solves S (new symbols)."""
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
    if rep is None or a is None:
        return 0
    n = 0
    for s in EVAL:
        ev, out = data(fam, s)
        a2 = dict(a)
        a2.update({("emit", k): v for k, v in J.emits(ev, out).items()})
        n += all([tuple(r) for r in g] == [tuple(r) for r in w] for g, w in zip(J.run_program(rep, a2, ev), out))
    return n


t0 = time.process_time()
proof, mins = {}, {}
for fam in "UT":
    ev, out = data(fam, S0)
    H = J.histories(ev, out)
    uns, nodes = J.bounded_unsat(H, J.FAMS[fam])
    mins[fam] = J.ddmin_unsat(H, J.FAMS[fam]) if uns else []
    proof[fam] = dict(unsat_by_complete_search=uns, nodes=nodes, minimal_histories=len(mins[fam]), of=len(H))
tool = None
for rep in ("none", "queue", "stack"):
    sols = {}
    for fam in "UT":
        ev, out = data(fam, S0)
        H = J.histories(ev, out)
        r, a, nodes, ex = J.search(mins[fam] + H, J.FAMS[fam], (rep,), 120.0, J.retrodict_domains(H, J.FAMS[fam]))
        sols[fam] = a
    if all(sols.values()):
        actions = sorted({sa for a in sols.values() for g, sa in a.values()})
        tool = dict(rep=rep, actions=actions, sols=sols)
        break
inv_cpu = time.process_time() - t0
res = {}
for fam in "SC":
    ev, out = data(fam, S1)
    H = J.histories(ev, out)
    syms = J.FAMS[fam]
    t1 = time.process_time()
    dom_tool = {s: {(g, sa) for g in J.G for sa in tool["actions"]} for s in syms}
    rd = J.retrodict_domains(H, syms)
    dom_a = {s: dom_tool[s] & rd[s] or dom_tool[s] for s in syms}
    rep, a, nodes, ex = J.search(H, syms, (tool["rep"],), 300.0, dom_a)
    cpu_a = time.process_time() - t1
    budget = max(cpu_a, 2.0)
    row = dict(a_tool=dict(solved=score(fam, rep, a), cpu_s=round(cpu_a, 3), program={k: v for k, v in (a or {}).items()}, rep=rep))
    for name, reps, dom in (("b_direct", ("none", "queue", "stack"), None), ("b2_direct_retro", ("none", "queue", "stack"), rd),
                            ("c_library_successes", ("none",), {s: {(g, "none") for g in J.G} for s in syms}),
                            ("d_random_rep", (random.Random(fam).choice(["none", "queue"]),), None)):
        t2 = time.process_time()
        rep2, a2, nodes, ex = J.search(H, syms, reps, budget, dom)
        row[name] = dict(solved=score(fam, rep2, a2), cpu_s=round(time.process_time() - t2, 3), rep=rep2, timed_out=a2 is None and not ex)
    res[fam] = row
    print(fam, {k: (v["solved"], v["cpu_s"], v.get("rep")) for k, v in row.items()}, flush=True)
tot = {k: sum(r[k]["solved"] for r in res.values()) for k in res["S"]}
promo = tool is not None and all(tot["a_tool"] > v for k, v in tot.items() if k != "a_tool") and res["S"]["a_tool"]["solved"] > 0
outcome = "PROMOTION CANDIDATE" if promo else ("REJECTED FOR THIS SETTING" if tool else "INCONCLUSIVE")
(ART / "t3v2.json").write_text(json.dumps(dict(proof=proof, tool=dict(rep=tool["rep"], actions=tool["actions"], sols={k: str(v) for k, v in tool["sols"].items()}),
                                               invention_cpu_s=round(inv_cpu, 3), withheld={f: {k: dict(v, program=str(v.get("program"))) for k, v in r.items()} for f, r in res.items()},
                                               totals=tot, outcome=outcome), indent=1, default=str))
print("proof", proof, "tool", tool["rep"], tool["actions"], "inv_cpu", round(inv_cpu, 2), "totals", tot, "OUTCOME", outcome)
