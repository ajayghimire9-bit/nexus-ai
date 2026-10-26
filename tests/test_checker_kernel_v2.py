"""Checker v2 validation: hand-derived cases, bounded exhaustive property checks, adversarial evidence."""
import hashlib
import itertools
import random
from pathlib import Path

from nexus import checker_kernel as K1
from nexus import checker_kernel_v2 as K

ROOT = Path(__file__).resolve().parents[1]
KNIGHT = [[1, 2], [2, 1], [-1, 2], [-2, 1], [1, -2], [2, -1], [-1, -2], [-2, -1]]
KING = [[0, 1], [1, 0], [0, -1], [-1, 0], [1, 1], [1, -1], [-1, 1], [-1, -1]]


def r(chain, x):
    return K.run(chain, x)[0]


def test_v2_pinned_and_v1_untouched():
    assert hashlib.sha256((ROOT / "src/nexus/checker_kernel_v2.py").read_bytes()).hexdigest() == \
        (ROOT / "src/nexus/checker_kernel_v2.sha256").read_text().split()[0]
    assert hashlib.sha256((ROOT / "src/nexus/checker_kernel.py").read_bytes()).hexdigest().startswith("5082402f")


# ---------------- hand-derived cases
def test_hand_coord():
    g = [[1, 2, 3], [4, 5, 6], [7, 8, 9 - 9]]
    # a=1,b=1 (shift rows up by one, wrapped), c=2,d=0 (columns 0,2,1)
    assert r([{"op": "grid_coord", "a": 1, "b": 1, "c": 2, "d": 0}], g) == [[4, 6, 5], [7, 0, 8], [1, 3, 2]]


def test_hand_knight_connectivity():
    g = [[2, 0, 0, 0],
         [0, 0, 1, 0],
         [0, 1, 0, 1],
         [0, 0, 0, 0]]
    # seed (0,0): knight -> (1,2) [passable 1] -> from (1,2): (2,0)? (1+1,2-2)=(2,0) is 0; (3,1)? 0; (3,3) 0;
    # (0,0) seed; (2,4) out. -> (2,1)? not a knight move from (1,2) [(+1,-1)]. From seed also (2,1): (0+2,0+1)=(2,1)=1.
    # From (2,1): (0,2)=0,(1,3)=0,(3,3)=0,(4,..) out,(0,0) seed,(1,-1) out,(3,-1) out,(4,2) out. (2,3) never reached.
    out = r([{"op": "grid_connect", "moves": KNIGHT, "passable": 1, "seed": 2, "fill": 5}], g)
    assert out == [[2, 0, 0, 0], [0, 0, 5, 0], [0, 5, 0, 1], [0, 0, 0, 0]]


def test_hand_cellwise_z2xz2():
    table = [[a, b, a ^ b] for a in range(4) for b in range(4)]
    g = [[1, 2, 3], [0, 3, 3]]
    # right neighbour wrapped: row0 -> 1^2=3, 2^3=1, 3^1=2 ; row1 -> 0^3=3, 3^3=0, 3^0=3
    assert r([{"op": "grid_cellwise", "table": table, "dr": 0, "dc": 1}], g) == [[3, 1, 2], [3, 0, 3]]


def test_hand_adapters():
    g = [[0, 3, 3], [0, 0, 3], [4, 0, 0]]
    enc = r([{"op": "enc_objects", "conn": 4, "background": 0}], g)
    assert enc == {"objects": [{"color": 3, "cells": [[0, 1], [0, 2], [1, 2]]}, {"color": 4, "cells": [[2, 0]]}]}
    big = [{"op": "enc_objects", "conn": 4, "background": 0}, {"op": "ir_objects_filter_size", "min": 2, "max": 9},
           {"op": "ir_objects_recolor", "color": 7}, {"op": "dec_objects", "background": 0, "shape": [3, 3]}]
    assert r(big, g) == [[0, 7, 7], [0, 0, 7], [0, 0, 0]]
    assert r([{"op": "enc_counter", "path": "."}, {"op": "ir_counter_top", "k": 1}, {"op": "dec_counter"}],
             [5, 3, 5, 9, 5, 3]) == [[5, 3]]
    gg = [[1, 0, 1], [0, 0, 1]]
    assert r([{"op": "enc_graph", "moves": [[0, 1], [1, 0], [0, -1], [-1, 0]], "passable": 1},
              {"op": "ir_graph_reach", "seeds": [2]}], gg) == [2, 5]


# ---------------- bounded exhaustive property checks
def test_coord_identity_and_closure_exhaustive():
    grids = [[[a, b], [c, d]] for a, b, c, d in itertools.product((0, 1), repeat=4)]
    params = list(itertools.product(range(1, 3), range(2), range(1, 3), range(2)))
    for g in grids:
        assert r([{"op": "grid_coord", "a": 1, "b": 0, "c": 1, "d": 0}], g) == g
        for (a1, b1, c1, d1), (a2, b2, c2, d2) in itertools.product(params, repeat=2):
            two = r([{"op": "grid_coord", "a": a1, "b": b1, "c": c1, "d": d1},
                     {"op": "grid_coord", "a": a2, "b": b2, "c": c2, "d": d2}], g)
            # out2[i] = out1[(a2 i + b2)] = g[a1 (a2 i + b2) + b1]
            one = r([{"op": "grid_coord", "a": a1 * a2, "b": a1 * b2 + b1, "c": c1 * c2, "d": c1 * d2 + d1}], g)
            assert two == one


def test_connectivity_properties_exhaustive():
    for bits in itertools.product((0, 1), repeat=9):
        g = [list(bits[0:3]), list(bits[3:6]), list(bits[6:9])]
        g[0][0] = 2
        full = r([{"op": "grid_connect", "moves": KING, "passable": 1, "seed": 2, "fill": 5}], [[2, 1, 1], [1, 1, 1], [1, 1, 1]])
        assert all(c == 5 for row in full for c in row if c != 2)
        a = r([{"op": "grid_connect", "moves": KING[:4], "passable": 1, "seed": 2, "fill": 5}], g)
        b = r([{"op": "grid_connect", "moves": KING, "passable": 1, "seed": 2, "fill": 5}], g)
        assert all(not (x == 5 and y != 5) for ra, rb in zip(a, b) for x, y in zip(ra, rb))   # monotone in moves


def test_objects_roundtrip_exhaustive():
    for bits in itertools.product((0, 1), repeat=9):
        g = [list(bits[0:3]), list(bits[3:6]), list(bits[6:9])]
        for conn in (4, 8):
            assert r([{"op": "enc_objects", "conn": conn, "background": 0},
                      {"op": "dec_objects", "background": 0, "shape": [3, 3]}], g) == g


def test_v2_list_semantics_regression_vs_frozen_v1():
    rng = random.Random(4)
    specs = [{"op": "comp", "path": "#", "desc": True, "cond": "head", "cparam": 2, "transform": "id", "tparam": None},
             {"op": "prefix_sum"}, {"op": "diff"}, {"op": "rotate", "k": 2}, {"op": "run_heads"},
             {"op": "S", "k": 2, "path": ".", "desc": True}, {"op": "repeat", "n": 2, "body": {"op": "diff"}}]
    for _ in range(200):
        x = [rng.randint(-5, 9) for _ in range(rng.randint(1, 7))]
        for s in specs:
            try:
                a = K1.key(K1.apply(s, x))
            except Exception:
                a = None
            b = K.run([s], x)[0]
            assert (a is None and b == K.ERROR) or a == K.key(b)


# ---------------- adversarial evidence
def _ev(public, query, claimed, cand, tools, depth=1, kind="exhaustive", lemmas=(), version=2):
    return {"checker_version": version, "public": public, "query": query, "claimed_answer": claimed,
            "candidate": cand, "scope": {"kind": kind, "tools": tools, "max_depth": depth}, "lemmas": list(lemmas)}


def test_disagreeing_consistent_programs_give_ambiguous_with_witnesses():
    rot = {"op": "rotate", "k": 1}
    rev = {"op": "comp", "path": "#", "desc": True, "cond": "all", "cparam": None, "transform": "id", "tparam": None}
    pub = [[[1, 2], [2, 1]]]                       # rotate-1 and reverse agree on [1,2] ...
    v = K.check(_ev(pub, [1, 2, 3], [2, 3, 1], [rot], [rot, rev]))
    assert v["label"] == "AMBIGUOUS" and v["k"] == 2 and v["k_exact"]   # ... but not on [1,2,3]
    assert {K.key(K.run([[rot, rev][i] for i in w["chain"]], [1, 2, 3])[0]) for w in v["witnesses"]} == \
        {w["answer"] for w in v["witnesses"]}
    p = K.check(_ev(pub, [1, 2, 3], [2, 3, 1], [rot], [rot, rev], kind="proposal"))
    assert p["label"] == "AMBIGUOUS" and not p["k_exact"]


def test_adversarial_rejections():
    rot = {"op": "rotate", "k": 1}
    pub = [[[1, 2, 3], [2, 3, 1]]]
    good = _ev(pub, [4, 5, 6], [5, 6, 4], [rot], [rot])
    assert K.check(good)["label"] == "exhaustive_UNIQUE"
    assert K.check(dict(good, claimed_answer=[6, 5, 4]))["label"] == "ABSTAIN"
    assert K.check(dict(good, checker_version=1))["reason"] == "wrong_checker_version"
    assert K.check(dict(good, candidate=[{"op": "teleport"}]))["reason"] == "unsupported"
    assert K.check(dict(good, lemmas=[{"tool": 0, "post": ["len_le", 1], "public_index": 0}]))["reason"] == "bad_lemma"
    gc = {"op": "grid_coord", "a": 1, "b": 0, "c": 1, "d": 0}
    g = [[1, 2], [3, 4]]
    ge = _ev([[g, g]], g, g, [gc], [gc])
    assert K.check(ge)["label"] == "exhaustive_UNIQUE"
    assert K.check(dict(ge, lemmas=[{"tool": 0, "post": ["len_le", 1], "public_index": 0}]))["reason"] == "bad_lemma"
    big = [[1] * 13 for _ in range(13)]
    # a 13x13 array is not a Grid (spec §1) but a nested List; grid ops on it are execution errors
    vb = K.check(_ev([[big, big]], big, big, [gc], [gc]))
    assert vb["label"] == "ABSTAIN" and vb["reason"] in ("unsupported_value", "candidate_fails")
    huge = list(range(65))
    assert K.check(_ev([[huge, huge]], huge, huge, [{"op": "run_heads"}], [{"op": "run_heads"}]))["reason"] == "unsupported_value"
    ragged = [[1, 2], [3]]
    assert K.check(_ev([[ragged, ragged]], ragged, ragged, [gc], [gc]))["label"] == "ABSTAIN"
    # every fitting program errors on the query -> query_error
    d = {"op": "diff"}
    assert K.check(_ev([[[1, 3], [2]]], ["a", "b"], [2], [d], [d]))["label"] == "ABSTAIN"


def test_order_invariance():
    tools = [{"op": "rotate", "k": 1}, {"op": "rotate", "k": 2}, {"op": "run_heads"}, {"op": "diff"},
             {"op": "comp", "path": "#", "desc": True, "cond": "all", "cparam": None, "transform": "id", "tparam": None}]
    pub = [[[1, 2, 3, 4], [2, 3, 4, 1]], [[5, 5, 7], [5, 7, 5]]]
    base = K.check(_ev(pub, [9, 8, 7], [8, 7, 9], [tools[0]], tools, depth=2))
    for s in range(4):
        t2, p2 = tools[:], pub[:]
        random.Random(s).shuffle(t2)
        random.Random(9 + s).shuffle(p2)
        v = K.check(_ev(p2, [9, 8, 7], [8, 7, 9], [tools[0]], t2, depth=2))
        assert (v["label"], v.get("k"), v["fitting"]) == (base["label"], base.get("k"), base["fitting"])
