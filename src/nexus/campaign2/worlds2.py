"""Phase 2 world registry (NOT LOCKED): the six Phase 1 worlds unchanged, plus two wholly untouched mechanism families in
World C (C5, C6) and two in World E (E5, E6). The new families are defined here once, before any Phase 2 experiment, and
are used ONLY by the one-use Stage 4 untouched-mechanism panel: no learner runs on them in development, source learning,
admission or improver rollouts (only generator self-checks run before Stage 4).
  C5 colour-histogram statistics: per-colour cell counts (colours 1..4), majority colour, number of distinct colours
  C6 ray extension: every coloured cell paints its colour rightward / downward until the next coloured cell or the border
  E5 gated mediation: X -> M -> Y where the mediator acts only when a visible gate is open; do() on X, M or Y
  E6 two-parent mixing: Y = (X1 + k * X2) mod 4 with X1, X2 confounded through the context; do() on either parent
World F draft withholding (Phase 2 protocol): an F task with an ODD seed is a pure input-output synthesis task (the
learner's view has no draft); an even seed keeps the Phase 1 repair protocol (draft given)."""
import random

from nexus.campaign.worlds import WORLDS as W1, FAMILIES as F1
from nexus.campaign.worlds.base import Mech, build_task, TaskView
from nexus.campaign.worlds import world_c_spatial as WC, world_e_causal as WE


def _hist(rng):
    v = rng.choice(("counts", "majority", "distinct"))
    f = {"counts": lambda g: tuple(sum(1 for r in g for x in r if x == c) for c in (1, 2, 3, 4)),
         "majority": lambda g: max((1, 2, 3, 4), key=lambda c: (sum(1 for r in g for x in r if x == c), -c))
         if any(x > 0 for r in g for x in r) else 0,
         "distinct": lambda g: len({x for r in g for x in r if x > 0})}[v]
    return f, ("l" if v == "counts" else "i"), f"hist[{v}]"


def _rays(rng):
    v = rng.choice(("right", "down"))

    def right(g):
        out = []
        for r in g:
            cur, row = 0, []
            for x in r:
                cur = x if x > 0 else cur
                row.append(cur)
            out.append(tuple(row))
        return tuple(out)
    if v == "right":
        return right, "rays[right]"
    return (lambda g: WC._T(right(WC._T(g))) if g else g), "rays[down]"


class _CExt:
    WORLD, FAMILIES, Q_BUDGET = "C", F1["C"] + ("C5", "C6"), WC.Q_BUDGET

    @staticmethod
    def gen(family, rng, level):
        if family == "C5":
            f, out, d = _hist(rng)
            return Mech(fn=lambda x: f(x[0]), sig=("L",), out=out, descr=d, train=WC._tr, iface=WC._if)
        if family == "C6":
            f, d = _rays(rng)
            return Mech(fn=lambda x: f(x[0]), sig=("L",), out="L", descr=d, train=WC._tr, iface=WC._if)
        return WC.gen(family, rng, level)

    @staticmethod
    def posts(family, rng):
        return [] if family in ("C5", "C6") else WC.posts(family, rng)


class _EExt:
    WORLD, FAMILIES, Q_BUDGET = "E", F1["E"] + ("E5", "E6"), WE.Q_BUDGET

    @staticmethod
    def gen(family, rng, level):
        obs = lambda r: ((-1, -1, -1), WE._ctx(r, 3))           # noqa: E731
        itv = lambda r: (WE._do(r, 3), WE._ctx(r, 3))         # noqa: E731
        if family == "E5":
            k = rng.randint(1, 3)
            gate = rng.randrange(3)

            def f(x):
                d, c = x
                X = WE._co(d[0], c[0])
                M = WE._co(d[1], (X + k) % 4 if c[gate] >= 2 else c[1])
                return WE._co(d[2], M)
            return Mech(fn=f, sig=("l", "l"), out="i", descr=f"mediate[gate=c{gate}>=2,M=X+{k}]", train=obs, iface=itv,
                        verify_kind="interventional")
        if family == "E6":
            k = rng.randint(2, 3)

            def g(x):
                d, c = x
                X1 = WE._co(d[0], c[0])
                X2 = WE._co(d[1], (c[0] + c[1]) % 4)
                return WE._co(d[2], (X1 + k * X2) % 4)
            return Mech(fn=g, sig=("l", "l"), out="i", descr=f"mix[Y=X1+{k}X2]", train=obs, iface=itv,
                        verify_kind="interventional")
        return WE.gen(family, rng, level)

    @staticmethod
    def posts(family, rng):
        return [] if family in ("E5", "E6") else WE.posts(family, rng)


WORLDS = dict(W1, C=_CExt, E=_EExt)
FAMILIES = {w: m.FAMILIES for w, m in WORLDS.items()}
UNTOUCHED = (("C", "C5"), ("C", "C6"), ("E", "E5"), ("E", "E6"))


class TaskView2(TaskView):
    def __init__(self, task, pure):
        super().__init__(task)
        if pure:
            self.draft = None


def make_task2(world, family, level, seed, role, partners):
    t = build_task(WORLDS, world, family, level, seed, role, partners, WORLDS[world].Q_BUDGET)
    pure = world == "F" and seed % 2 == 1
    t.meta["pure_synthesis"] = pure
    t.view = lambda t=t, pure=pure: TaskView2(t, pure)
    return t
