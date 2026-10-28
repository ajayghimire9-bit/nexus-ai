"""Unit tests for the bounded acceptance check (ba track; fast, no experiment is executed)."""
import random

from nexus import ba_accept as BA
from nexus import u5_statesplit as SP

INC = ("b", "+", ("var", "acc"), ("const", 1))
ZERO = ("const", 0)


def _machine(close_resets):
    upd = {(1, "READ"): INC}
    if close_resets:
        upd[(1, "CLOSE")] = ZERO
    return dict(key="k", ctrl="kind", n=2, init=0, alpha=["CLOSE", "OPEN", "READ"],
                delta={(0, "OPEN"): 1, (1, "READ"): 1, (1, "CLOSE"): 0},
                lam={(0, "OPEN"): [], (1, "READ"): [], (1, "CLOSE"): ["bill"]},
                regs=[dict(field="v", init=0, upd=upd)], sources={((1, "CLOSE"), 0, 1): ("reg", 0)})


class FakeL:
    """Oracle = the machine that resets on CLOSE; the learner's hypothesis may miss the reset (delayed effect)."""

    def __init__(self, machine):
        self.machine, self.alpha, self.n_mq, self.n = machine, machine["alpha"], 0, 0
        self.rnd = random.Random(0)
        self.truth = _machine(True)

    def make_events(self, word, fresh_values=False):
        self.n += 1
        return [{"k": f"p{self.n}", "kind": a, "v": round(self.rnd.uniform(1, 99), 2)} for a in word]

    def _query(self, evs):
        return SP.run_machine(self.truth, evs)


def test_missing_reset_is_caught_by_the_delayed_effect_tier():
    L = FakeL(_machine(False))
    cex, scope = BA.bounded_cex(L, cap_exhaustive=8)            # horizon 1: tier 1 alone cannot see it
    assert scope["exhaustive"]["horizon"] == 1
    assert cex and scope["stopped"] == "counterexample"
    assert any(w[-1] == "CLOSE" and w.count("CLOSE") >= 2 for _, _, w in cex)


def test_correct_machine_passes_with_a_scope_record():
    L = FakeL(_machine(True))
    cex, scope = BA.bounded_cex(L, cap_exhaustive=30)
    assert cex == [] and scope["label"] == "TESTED_WITHIN_STATED_LIMITS" and scope["stopped"] == "passed"
    assert scope["exhaustive"]["horizon"] == 3 and scope["exhaustive"]["words"] == 27
    assert scope["structural"]["tests"] > 0 and scope["queries"] == L.n_mq


def test_loaded_prefix_and_flush_paths():
    m = _machine(True)
    pre = BA.loaded_prefixes(m, m["alpha"])
    assert pre[(1, 1)] == ("OPEN", "READ")
    fl = BA.flush_paths(m, m["alpha"], 1, BA._emitters(m))
    assert fl[(0, 0)] == ("OPEN", "CLOSE") and fl[(1, 0)] == ("CLOSE",)
