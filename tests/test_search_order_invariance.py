"""Wave 40 Step 3: search-order invariance of the repaired shared search (src/nexus/w40_search.py).

On small, exhaustively checkable problems from all four internal program domains and PROSE-dev primitives (quarantined
development data), run to completion:
  * every ordering - uniform (Fresh), hand-designed (Fixed-v5), learned (Repr-v5), permuted (Placebo-v5), Fixed+Repr-v5,
    an adversarial ordering (no-op encoders cheapest; the Step 1 failure pattern) and eight random cost matrices - recovers
    EXACTLY the brute-force set of fitting value vectors (all chains up to the depth, no dedup, no pruning);
  * the first candidate each ordering returns gets a byte-identical Checker v5 verdict (label, k, answers, per-input extra
    answer counts, warnings, witnesses, work counters).
A regression test shows the Wave 39 search violates invariance on the same problems (so the suite can detect the defect).
Sub-scopes: the teacher's tools + every `fill` tool of the declared scope + a seeded sample of the declared v5 scope."""
import itertools
import json
import random
from pathlib import Path

import pytest

from nexus import checker_kernel_v5 as V5
from nexus import w38_domains as D
from nexus import w38_learn as K
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w39_search as Q39
from nexus import w40_learn as W
from nexus import w40_search as Q

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(D.MECH)                       # all 35 internal mechanisms (4 domains)


def _ck(t):
    return json.dumps(t, sort_keys=True)


def subscope(tools, keep, n, seed):
    rng = random.Random(seed)
    base = {_ck(t) for t in keep} | {_ck(t) for t in tools if t["op"] == "fill"}
    rest = [t for t in tools if _ck(t) not in base]
    pick = {_ck(t) for t in rng.sample(rest, min(n, len(rest)))} | base
    return [t for t in tools if _ck(t) in pick]


def internal_problems():
    """Each mechanism twice: with its 3 public pairs, and with only 1 public pair (under-determined: several fitting answers,
    so AMBIGUOUS certificates and multi-element solution sets are exercised)."""
    out = []
    for i, (d, m) in enumerate(CASES):
        t = D.make_task(d, m, random.Random(f"w40-inv:{d}:{m}"))
        if t is None:
            continue
        depth = min(3, len(t["teacher"]))
        sc = S.scope(t["public"], t["query"], depth)
        keep = [x for x in t["teacher"] if _ck(x) in {_ck(y) for y in sc["tools"]}]
        tools = subscope(sc["tools"], keep, 22 if depth == 3 else 80, i)
        out.append((f"{d}/{m}", t["public"], t["query"], tools, depth))
        out.append((f"{d}/{m}/1pub", t["public"][:1], t["query"], tools, depth))
    return out


def prose_problems():
    out = []
    for f in sorted((ROOT / "artifacts/external/prose").glob("*.json"))[::5]:
        ex = json.loads(f.read_text())["Examples"]
        if len(ex) < 4 or any(len(e["Input"]) != 1 for e in ex):
            continue
        pub = [[e["Input"][0], e["Output"]] for e in ex[:3]]
        q = ex[3]["Input"][0]
        sc = S.scope(pub, q, 2)
        tools = subscope(sc["tools"], [], 110, f.stem)
        out.append((f"prose/{f.stem}", pub, q, tools, 2))
        out.append((f"prose/{f.stem}/1pub", pub[:1], q, tools, 2))
    return out


PROBLEMS = internal_problems() + prose_problems()


def brute(public, query, tools, depth):
    xs = [x for x, _ in public] + [query]
    tg = [L.key(y) for _, y in public]
    found = set()
    for d in range(1, depth + 1):
        for chain in itertools.product(range(len(tools)), repeat=d):
            outs = []
            for x in xs:
                o = L.run([tools[i] for i in chain], x)
                if o == L.ERROR:
                    break
                outs.append(o)
            if len(outs) == len(xs):
                kk = tuple(L.key(o) for o in outs)
                if list(kk[:len(public)]) == tg:
                    found.add(kk)
    return found


def orderings(tools):
    progs = [t["teacher"] for t in D.stream("w40-inv-src", D.DOMAINS, "source", 1)]
    rp = K.fit_repr(progs)
    pl = K.placebo(K.fit(progs), "w40-inv")
    T = len(tools)
    out = {"Fresh": None, "Fixed-v5": {"kind": "fixed5"}, "Repr-v5": rp, "Placebo-v5": pl,
           "Fixed+Repr-v5": {"kind": "fixed_repr", "repr": rp}}
    cms = {k: W.cost_matrix(v, tools) for k, v in out.items()}
    adv = [[0.01 if t["op"] in ("fill", "uniq", "flat", "rev") else 3.0 for t in tools] for _ in range(T + 1)]
    cms["adversarial-noop-first"] = {"cost": adv}
    for s in range(8):
        rng = random.Random(f"w40-rand:{s}")
        cms[f"random-{s}"] = {"cost": [[rng.uniform(0.01, 5.0) for _ in range(T)] for _ in range(T + 1)]}
    return cms


@pytest.mark.parametrize("name,public,query,tools,depth", PROBLEMS, ids=[p[0] for p in PROBLEMS])
def test_reachable_solution_sets_are_order_invariant(name, public, query, tools, depth):
    truth = brute(public, query, tools, depth)
    for oname, cm in orderings(tools).items():
        got = Q.reachable_fitting(public, query, tools, depth, cm)
        assert got == truth, f"{name}: ordering {oname} recovered {len(got)} of {len(truth)} fitting value vectors"


@pytest.mark.parametrize("name,public,query,tools,depth", PROBLEMS, ids=[p[0] for p in PROBLEMS])
def test_first_candidate_certificates_are_order_invariant(name, public, query, tools, depth):
    extra = [query + "z"] if isinstance(query, str) else []
    verdicts = {}
    for oname, cm in orderings(tools).items():
        cand = Q.search(public, query, tools, depth, cm, budget=10**9)
        if cand is None:
            verdicts[oname] = "NO_CANDIDATE"
            continue
        ev = {"checker_version": 5, "public": public, "query": query, "claimed_answer": L.run(cand, query), "candidate": cand,
              "scope": {"kind": "exhaustive", "tools": tools, "max_depth": depth}, "extra_queries": extra}
        v = V5.check(json.loads(json.dumps(ev)))
        verdicts[oname] = json.dumps(v, sort_keys=True)
    assert len(set(verdicts.values())) == 1, f"{name}: certificates differ across orderings: {sorted(set(verdicts.values()))[:2]}"
    if brute(public, query, tools, depth):
        assert verdicts["Fresh"] != "NO_CANDIDATE"


def test_old_search_violates_invariance_somewhere():
    """Regression evidence: with the same orderings, the Wave 39 search fails to find a reachable solution on some problem."""
    misses = 0
    for name, public, query, tools, depth in PROBLEMS:
        if not brute(public, query, tools, depth):
            continue
        for oname, cm in orderings(tools).items():
            if Q39.search(public, query, tools, depth, cm, budget=10**9) is None:
                misses += 1
            assert Q.search(public, query, tools, depth, cm, budget=10**9) is not None
    assert misses > 0


def test_new_search_matches_old_under_uniform_prior():
    """Uniform best-first pops states in depth order, so the repair changes nothing for Fresh (same candidate, same execs)."""
    for name, public, query, tools, depth in PROBLEMS:
        cm = K.cost_matrix(None, tools)
        m0, m1 = {}, {}
        assert Q39.search(public, query, tools, depth, cm, budget=10**9, meter=m0) == \
            Q.search(public, query, tools, depth, cm, budget=10**9, meter=m1)
        assert m0["execs"] == m1["execs"], name


TRACED = [(39, 7831, 6), (39, 7832, 6), (38, 7801, 6), (38, 7801, 7), (38, 7803, 6)]


@pytest.mark.parametrize("wave,seed,j", TRACED)
def test_traced_fixed_losses_are_recovered_at_full_scope(wave, seed, j):
    """The Fixed losses traced in Step 1, each with its own wave's language / declared scope / Fixed prior and budget: the old
    search finds nothing, the repaired search finds a fitting chain with the same query answer as Fresh."""
    from nexus import w38_lang as L4, w38_scope as S4, w38_search as Q38
    t = D.stream(f"{seed}:tgt:tables", ("tables",), "all", 2)[j]
    depth = len(t["teacher"])
    if wave == 39:
        lang, rule, old, budget = L, True, Q39.search, 4_000_000
        tools = S.scope(t["public"], t["query"], depth)["tools"]
        fx = W.cost_matrix({"kind": "fixed5"}, tools)
    else:
        lang, rule, old, budget = L4, False, Q38.search, 2_000_000
        tools = S4.scope(t["public"], t["query"], depth)["tools"]
        fx = K.cost_matrix({"kind": "fixed"}, tools)
    fresh = Q.search(t["public"], t["query"], tools, depth, K.cost_matrix(None, tools), budget=budget, lang=lang, last_rule=rule)
    assert old(t["public"], t["query"], tools, depth, fx, budget=budget) is None
    got = Q.search(t["public"], t["query"], tools, depth, fx, budget=budget, lang=lang, last_rule=rule)
    assert got is not None and lang.key(lang.run(got, t["query"])) == lang.key(lang.run(fresh, t["query"]))
