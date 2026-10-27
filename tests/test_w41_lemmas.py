"""Wave 41 base static lemmas: differential soundness and lemma-pruned search completeness."""
import json
import random
from pathlib import Path

import pytest

from nexus import w38_domains as D
from nexus import w38_search as Q38
from nexus import w39_lang as L
from nexus import w39_scope as S
from nexus import w41_lemmas as M
from nexus import w41_search as Q

import test_search_order_invariance as INV

ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    out = []
    for i, (d, m) in enumerate(sorted(D.MECH)):
        t = D.make_task(d, m, random.Random(f"w41-lem:{d}:{m}"))
        if t:
            out.append((t["public"], t["query"]))
    for f in sorted((ROOT / "artifacts/external/prose").glob("*.json")):
        ex = json.loads(f.read_text())["Examples"]
        if len(ex) >= 4 and all(len(e["Input"]) == 1 for e in ex):
            out.append(([[e["Input"][0], e["Output"]] for e in ex[:3]], ex[3]["Input"][0]))
    return out


def test_intro_is_sound_by_differential_execution():
    """For every tool of every declared v5 scope (depth 3) and every value reachable by random tool steps (sampled, 8 random steps), the output's
    characters are within the input's characters, the tool's intro and NUM."""
    rng = random.Random(7)
    checked = 0
    for public, query in _inputs():
        tools = S.scope(public, query, 3)["tools"]
        vals = [x for x, _ in public] + [query]
        for _ in range(8):                                         # reachable intermediate values (random chains)
            t = rng.choice(tools)
            nxt = [L.run([t], v) for v in vals]
            vals += [v for v in nxt if v != L.ERROR]
            vals += [Q38.mutate(v, rng) for v in vals[:4]]
        for t in tools:
            it = M.intro(t)
            if it.any:
                continue
            for v in vals:
                o = L.run([t], v)
                if o == L.ERROR:
                    continue
                extra = M.chars_of(o) - M.chars_of(v) - M.NUM
                assert it.covers(frozenset(extra)), (t, v, o, extra)
                checked += 1
    assert checked > 100_000


def orderings_plus(tools):
    out = INV.orderings(tools)
    return {k: out[k] for k in ("Fresh", "Fixed-v5", "Repr-v5", "Fixed+Repr-v5", "adversarial-noop-first", "random-0", "random-3")}


@pytest.mark.parametrize("name,public,query,tools,depth", INV.PROBLEMS, ids=[p[0] for p in INV.PROBLEMS])
def test_lemma_pruned_search_recovers_bruteforce_set(name, public, query, tools, depth):
    truth = INV.brute(public, query, tools, depth)
    lem = M.TaskLemmas(public, tools)
    for oname, cm in orderings_plus(tools).items():
        got = Q.reachable_fitting(public, query, tools, depth, cm, lem=lem)
        assert got == truth, f"{name}/{oname}: {len(got)} vs {len(truth)}"


def test_lemmas_off_equals_wave40_walk():
    from nexus import w38_learn as K
    from nexus import w40_search as Q40
    for name, public, query, tools, depth in INV.PROBLEMS[:30]:
        cm = K.cost_matrix(None, tools)
        m0, m1 = {}, {}
        assert Q40.search(public, query, tools, depth, cm, budget=10**9, meter=m0) == \
            Q.search(public, query, tools, depth, cm, budget=10**9, meter=m1)
        assert m0["execs"] == m1["execs"]
