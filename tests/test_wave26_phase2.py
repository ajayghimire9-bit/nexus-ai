"""Wave 26 Phase 2: opaque tools, noise-tolerant certificate rule (dev / synthetic only)."""
import math
import random

from nexus.wave25_factored import Mech, Order
from nexus.wave26_phase2 import DELTA, Opaque, _opaque_for, binom_upper, corrupt, grammar2, group_status


def test_opaque_tools_hide_code_but_match_semantics():
    rng = random.Random(0)
    for _ in range(200):
        xs = [{"a": rng.randint(0, 9), "b": rng.randint(0, 3)} for _ in range(rng.randint(0, 6))]
        for m in (Mech("S", (2, Order("a", True))), Mech("S", (3, Order("#"))), Mech("Sort", (Order("b"),))):
            op = _opaque_for(m, 0)
            assert isinstance(op, Opaque) and op.role == "Opaque" and op.slots == ()
            assert op(xs) == m(xs)


def test_grammar_swaps_selection_and_sort_for_opaque_callables():
    xs = [[{"f": 1, "g": 2, "h": True}, {"f": 3, "g": 0, "h": False}]] * 3
    roles = {t.fn.role for t in grammar2(xs)}
    assert "Opaque" in roles and "S" not in roles and "Sort" not in roles and "F" in roles


def test_likelihood_ratio_certificate_threshold():
    thresh = math.log((1 - DELTA) / DELTA)
    yq = ["a", "a", "b"]
    _, s = group_status(yq, [0, 1, 2], 3, 0.10)          # gap 2 at eps 0.1: ratio 81 < 99
    assert s < thresh
    _, s = group_status(yq, [0, 1, 3], 3, 0.10)          # gap 3: ratio 729 >= 99
    assert s >= thresh
    _, s = group_status(yq, [0, 0, 1], 1, 0.01)          # gap 1 at eps 0.01: ratio 99
    assert s >= thresh - 1e-9


def test_corruption_and_binomial_bound():
    rng = random.Random(1)
    assert corrupt([1, 2, 3], rng) != [1, 2, 3]
    assert binom_upper(100, 0.01) >= 2 and binom_upper(0, 0.01) == 0
