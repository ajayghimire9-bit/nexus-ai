"""Wave 41 Step A: adversarial cross-specialist soundness of the certificate law (src/nexus/w41_hier.py).

* The 1 -> 2 counterexample: an Addition specialist (x+1) is locally unique (3), a Multiplication specialist (2x) is locally
  unique (4); the global verdict over the union is AMBIGUOUS. The controller must never emit GLOBAL_SCOPE_UNIQUE from a slice.
* Generated adversarial set: internal mechanisms (1 and 2 public pairs, 5 seeds; 150-tool sub-scopes) and PROSE-dev tasks (1 public pair) on
  exhaustively checkable sub-scopes, plus 70 synthetic rivalry tasks built on the 1 -> 2 pattern (add c vs mul m; span vs
  format vs slice on a one-character prefix); every (task, specialist slice) where Checker v5 says SCOPE_UNIQUE on the slice but AMBIGUOUS
  on the full scope is a trap. Required: >= 50 trap tasks; 0 false GLOBAL_SCOPE_UNIQUE; the rival-witness check (repaired,
  lemma-pruned search over the full scope in each hierarchical routing order) finds a disagreeing witness on every trap; and
  every routing's global label equals Flat's on every task (100% agreement)."""
import json
import random
from pathlib import Path

from nexus import checker_kernel_v5 as V5
from nexus import w38_domains as D
from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w40_learn as W
from nexus import w41_hier as H
from nexus import w41_lemmas as M
from nexus import w41_search as Q

import test_search_order_invariance as INV

ROOT = Path(__file__).resolve().parents[1]


def kernel(public, query, cand, tools, depth):
    ev = {"checker_version": 5, "public": public, "query": query, "claimed_answer": L.run(cand, query), "candidate": cand,
          "scope": {"kind": "exhaustive", "tools": tools, "max_depth": depth}, "extra_queries": []}
    return V5.check(json.loads(json.dumps(ev)))


def test_one_to_two_counterexample():
    add1 = {"op": "fn", "f": ["add", ["x"], ["c", 1]]}
    mul2 = {"op": "fn", "f": ["mul", ["x"], ["c", 2]]}
    pub, q = [[1, 2]], 2
    va = kernel(pub, q, [add1], [add1], 1)
    vm = kernel(pub, q, [mul2], [mul2], 1)
    assert va["label"] == "SCOPE_UNIQUE" and vm["label"] == "SCOPE_UNIQUE"
    assert L.run([add1], q) == 3 and L.run([mul2], q) == 4
    assert H.global_label(slice_verdict=va) == "LOCAL_SLICE_UNIQUE_ONLY"           # never laundered
    full = [add1, mul2]
    w = Q.disagreeing_witness(pub, q, full, 1, K.cost_matrix(None, full), 3)
    assert w == [mul2]
    assert H.global_label(slice_verdict=va, witness_found=True) == "AMBIGUOUS"
    vf = kernel(pub, q, [add1], full, 1)
    assert vf["label"] == "AMBIGUOUS" and H.global_label(kernel_full=vf) == "AMBIGUOUS"


def problems():
    out = []
    for rep in range(5):
        for i, (d, m) in enumerate(sorted(D.MECH)):
            t = D.make_task(d, m, random.Random(f"w41-trap:{rep}:{d}:{m}"))
            if t is None:
                continue
            depth = min(2, len(t["teacher"]))
            for npub in (1, 2):
                pub = t["public"][:npub]
                sc = S.scope(pub, t["query"], depth)["tools"]
                keep = [x for x in t["teacher"] if INV._ck(x) in {INV._ck(y) for y in sc}]
                out.append((f"{d}/{m}/{rep}/{npub}", pub, t["query"], INV.subscope(sc, keep, 150, f"{rep}{i}"), depth))
    rng = random.Random("w41-synthetic-traps")
    for k in range(40):                         # numeric rivalry (the 1 -> 2 pattern): add c vs mul m on one public pair
        m = rng.randint(2, 5); a = rng.randint(1, 9)
        c = a * m - a
        tools = [{"op": "fn", "f": ["add", ["x"], ["c", cc]]} for cc in range(1, 10)] + \
                [{"op": "fn", "f": ["mul", ["x"], ["c", mm]]} for mm in range(2, 6)] + \
                [{"op": "fn", "f": ["sub", ["x"], ["c", cc]]} for cc in range(1, 4)]
        if not 1 <= c <= 9:
            continue
        out.append((f"synthetic/num{k}", [[a, a * m]], a + rng.randint(1, 7), tools, 1))
    for k in range(30):                         # string rivalry: span (bef d) vs format (fst) vs slice (sl 0:1)
        d = rng.choice("-_:;/")
        w1 = rng.choice("abcdefgh")
        r = "".join(rng.choice("xyz") for _ in range(3))
        q = "".join(rng.choice("abcdefgh") for _ in range(3)) + d + r
        tools = [{"op": "fn", "f": ["bef", ["x"], d]}, {"op": "fn", "f": ["fst", ["x"]]}, {"op": "fn", "f": ["sl", ["x"], 0, 1]},
                 {"op": "fn", "f": ["low", ["x"]]}, {"op": "toks", "c": "a"}, {"op": "fn", "f": ["at", ["x"], 0]}]
        out.append((f"synthetic/str{k}", [[w1 + d + r, w1]], q, tools, 2))
    for f in sorted((ROOT / "artifacts/external/prose").glob("*.json")):
        ex = json.loads(f.read_text())["Examples"]
        if len(ex) < 2 or any(len(e["Input"]) != 1 for e in ex):
            continue
        pub, q = [[ex[0]["Input"][0], ex[0]["Output"]]], ex[1]["Input"][0]
        out.append((f"prose/{f.stem}", pub, q, INV.subscope(S.scope(pub, q, 2)["tools"], [], 150, f.stem), 2))
    return out


def routings(tools, public):
    progs = [t["teacher"] for t in D.stream("w41-trap-src", D.DOMAINS, "source", 1)]
    rp = K.fit_repr(progs)
    base = W.cost_matrix_fast({"kind": "fixed_repr", "repr": rp}, tools)
    sig = H.signature(public)
    lr = H.fit_routing(progs, [H.signature(t["public"]) for t in D.stream("w41-trap-src", D.DOMAINS, "source", 1)])
    return {"Flat": base, "Fixed_Hierarchy": H.routed_cost_matrix(base, tools, H.fixed_routing(sig), sig),
            "Learned_Hierarchy": H.routed_cost_matrix(base, tools, lr, sig),
            "Placebo_Hierarchy": H.routed_cost_matrix(base, tools, H.placebo_routing(lr, "t"), sig)}


def test_adversarial_cross_specialist_traps():
    traps, tasks_checked, agree, false_global = set(), 0, 0, 0
    for name, pub, q, tools, depth in problems():
        lem = M.TaskLemmas(pub, tools)
        rts = routings(tools, pub)
        labels = {}
        for rn, cm in rts.items():
            cand = Q.search(pub, q, tools, depth, cm, budget=10**8, lem=lem)
            labels[rn] = H.global_label(kernel_full=kernel(pub, q, cand, tools, depth)) if cand else "NO_CANDIDATE"
        tasks_checked += 1
        agree += len(set(labels.values())) == 1
        if labels["Flat"] != "AMBIGUOUS":
            continue
        fine = lambda t: (t["op"], t["f"][0] if isinstance(t.get("f"), list) and t["f"] else "")
        groups = sorted({fine(t) for t in tools})
        slices = [[t for t in tools if H.spec_of(t) in (a, b)] for a in H.SPECS for b in (None,) + H.SPECS]
        slices += [[t for t in tools if fine(t) == g] for g in groups]   # finer micro-specialists (op + lambda head)
        for sl in slices:                          # specialist slices, two-specialist decompositions, finer micro-specialists
                if not sl:
                    continue
                c = Q.search(pub, q, sl, depth, K.cost_matrix(None, sl), budget=10**8)
                if c is None:
                    continue
                v = kernel(pub, q, c, sl, depth)
                if v["label"] != "SCOPE_UNIQUE":
                    continue
                traps.add(name)
                lab = H.global_label(slice_verdict=v)
                false_global += lab == "GLOBAL_SCOPE_UNIQUE"
                assert lab == "LOCAL_SLICE_UNIQUE_ONLY"
                for rn, cm in rts.items():          # rival check over the full scope, every routing order
                    w = Q.disagreeing_witness(pub, q, tools, depth, cm, L.run(c, q), budget=10**8, lem=lem)
                    assert w is not None, (name, rn)
                    assert H.global_label(slice_verdict=v, witness_found=True) == "AMBIGUOUS"
    print(f"tasks {tasks_checked}, trap tasks {len(traps)}, routing agreement {agree}/{tasks_checked}, false global {false_global}")
    assert false_global == 0
    assert agree == tasks_checked
    assert len(traps) >= 50


def test_record_contract_keeps_alternatives():
    r = H.record(["c"], [["w1"], ["w2"]], {"support": "ok"}, {"sha256": "x"}, {"skips": 3}, {"execs": 5})
    assert r["alternatives"] == [["w1"], ["w2"]] and r["assumptions"] and r["declared_scope"] and len(r["token"]) == 16
