"""Multi-world campaign: shared task interface, learner view, level composition and independent verification (NOT LOCKED).

A world module supplies, per family, a Python reference mechanism (never shown to the learner), a training-range input
sampler, a declared-interface sampler (wider: unseen values / kinds / board sizes) and the protocol:
  'io'     labels are reference outputs; consistency = equality;
  'valid'  labels are demonstrations; consistency and verification use the world simulator's success predicate
           (plan validity / goal achievement), never equality with the demonstration.
Levels: L1 atomic mechanism; L2 composed with a same-world partner mechanism; L3 composed with a cross-world partner;
L4 same-world + cross-world partner and only 3 training examples (sparser evidence). 'valid' families implement their
levels internally (longer horizons, extra stages). Partners are restricted by the task's role (see seeds.partners_for).

The learner receives only a TaskView: input/output types, protocol, the labelled training pairs, an interface sampler,
a metered query (oracle) with a budget, the simulator predicate on inputs it has labels for, and (World F) a draft program.
Verification (`verify`) is independent: hidden test inputs from a separate RNG stream (plus a bounded exhaustive domain where
declared) against the Python reference / simulator."""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Mech:
    fn: Callable
    sig: tuple
    out: str
    descr: str
    train: Callable                  # rng -> input tuple (training range)
    iface: Callable                  # rng -> input tuple (declared interface)
    protocol: str = "io"
    valid: Optional[Callable] = None  # (x, y) -> bool (simulator success)
    draft: Optional[tuple] = None    # buggy program AST (World F)
    exhaustive: Optional[Callable] = None   # () -> list of inputs (bounded exhaustive domain)
    verify_kind: str = "finite_hidden"
    own_levels: bool = False         # the family builds its own L2-L4


@dataclass
class Post:
    fn: Callable
    tin: str
    tout: str
    descr: str


@dataclass
class Task:
    tid: str
    world: str
    family: str
    level: int
    seed: int
    role: str
    mech: Mech
    train_x: list
    hidden_x: list
    q_budget: int
    descr: str
    meta: dict = field(default_factory=dict)

    def ref(self, x):
        return self.mech.fn(x)

    def view(self):
        return TaskView(self)


class QueryBudgetExceeded(RuntimeError):
    pass


class TaskView:
    """What the learner may see. No world/family names, no reference, no hidden tests."""

    def __init__(self, task: Task):
        self._t = task
        self.sig, self.out, self.protocol = task.mech.sig, task.mech.out, task.mech.protocol
        self.q_budget = task.q_budget
        self.queries = 0
        self.draft = task.mech.draft
        self.train = [(x, self._label(x)) for x in task.train_x]
        self._labelled = {repr(x) for x in task.train_x}

    def _label(self, x):
        return self._t.mech.fn(x)

    def sample(self, rng):
        return self._t.mech.iface(rng)

    def query(self, x):
        if self.queries >= self.q_budget:
            raise QueryBudgetExceeded()
        self.queries += 1
        self._labelled.add(repr(x))
        return self._label(x)

    def ok(self, x, label, y):
        """Consistency of output y with a labelled input (equality, or the simulator predicate for 'valid')."""
        if self.protocol == "io":
            return y == label
        if repr(x) not in self._labelled:
            raise PermissionError("simulator feedback only on labelled inputs")
        return bool(self._t.mech.valid(x, y))

    def key(self):
        return f"{','.join(self.sig)}->{self.out}:{self.protocol}"


def verify(task: Task, fn) -> dict:
    """Independent verification of a submitted program fn(x) on hidden tests (+ bounded exhaustive domain)."""
    xs = list(task.hidden_x)
    kind = task.mech.verify_kind
    if task.mech.exhaustive is not None:
        xs += task.mech.exhaustive()
    fails = 0
    first = None
    for x in xs:
        try:
            y = fn(x)
        except Exception:                                    # noqa: BLE001
            y = None
        if task.mech.protocol == "io":
            good = y is not None and y == task.mech.fn(x)
        else:
            good = y is not None and bool(task.mech.valid(x, y))
        if not good:
            fails += 1
            first = first or repr(x)[:120]
    return dict(ok=fails == 0, kind=kind, n=len(xs), fails=fails, first_fail=first)


# ------------------------------------------------------------------ composition
def glue(tin, tneed, rng):
    """Generic type adapters used to chain mechanisms (part of the composed reference)."""
    if tin == tneed:
        return None
    if tin == "L" and tneed == "l":
        k = rng.randrange(2)
        return Post(lambda v, k=k: tuple(r[k] if k < len(r) else 0 for r in v), "L", "l", f"col{k}")
    if tin == "l" and tneed == "i":
        return Post(lambda v: sum(v), "l", "i", "sum")
    if tin == "L" and tneed == "i":
        return Post(lambda v: len(v), "L", "i", "len")
    return False


def compose(m: Mech, posts):
    fn, out, descr = m.fn, m.out, m.descr
    for p in posts:
        fn = (lambda f, g: (lambda x: g(f(x))))(fn, p.fn)
        out = p.tout
        descr = f"{p.descr}<{descr}>"
    return Mech(fn=fn, sig=m.sig, out=out, descr=descr, train=m.train, iface=m.iface, protocol=m.protocol, valid=m.valid,
                draft=m.draft, exhaustive=m.exhaustive, verify_kind=m.verify_kind)


def chain_post(cur_out, cands, rng):
    """Pick one partner post compatible with cur_out (with at most one glue step); returns [glue?, post] or None."""
    rng.shuffle(cands)
    for p in cands:
        g = glue(cur_out, p.tin, rng)
        if g is False:
            continue
        return ([g] if g else []) + [p]
    return None


def _flat(v, out):
    if isinstance(v, tuple):
        for z in v:
            _flat(z, out)
    else:
        out.add(v)
    return out


def sanity(m: Mech, train_x, hidden_x):
    """Reject unidentifiable or degenerate tasks: a crash; training outputs all identical; or outputs whose values
    collapse to a single scalar over train + hidden (e.g. a composition that is all zeros)."""
    try:
        yt = [m.fn(x) for x in train_x]
        yh = [m.fn(x) for x in hidden_x]
    except Exception:                                        # noqa: BLE001
        return False
    if len({repr(y) for y in yt}) < 2 or len({repr(y) for y in yt + yh}) < 2:
        return False
    vals = set()
    for y in yt + yh:
        _flat(y, vals)
    return len(vals) >= 2


def build_task(worlds, world, family, level, seed, role, partners, q_budget, n_hidden=30):
    """worlds: world letter -> module; partners: dict(same=[families], cross=[(world, family)])."""
    W = worlds[world]
    for attempt in range(40):
        rng = random.Random(f"agi|{world}|{family}|L{level}|{seed}|{attempt}")
        m = W.gen(family, rng, level)
        posts_desc = []
        if level >= 2 and not m.own_levels:
            chain = []
            cur = m.out
            same = [p for f in partners.get("same", []) for p in W.posts(f, rng)]
            cross = [p for (w, f) in partners.get("cross", []) for p in worlds[w].posts(f, rng)]
            for want in ({2: ("same",), 3: ("cross",), 4: ("same", "cross")}[level]):
                # a world without a compatible same-world partner falls back to a cross-world one (and vice versa)
                c = chain_post(cur, list(same if want == "same" else cross), rng) or \
                    chain_post(cur, list(cross if want == "same" else same), rng)
                if c is None:
                    break
                chain += c
                cur = c[-1].tout
            else:
                c = True
            if c is None:
                continue
            m = compose(m, chain)
            posts_desc = [p.descr for p in chain]
        n_train = 3 if level == 4 else 5
        trng = random.Random(f"agi-train|{world}|{family}|L{level}|{seed}|{attempt}")
        hrng = random.Random(f"agi-hidden|{world}|{family}|L{level}|{seed}|{attempt}")
        train_x = [m.train(trng) for _ in range(n_train)]
        hidden_x = [m.iface(hrng) for _ in range(n_hidden)]
        if not sanity(m, train_x, hidden_x):
            continue
        return Task(tid=f"{world}.{family}.L{level}.{seed}", world=world, family=family, level=level, seed=seed, role=role,
                    mech=m, train_x=train_x, hidden_x=hidden_x, q_budget=q_budget, descr=m.descr,
                    meta=dict(attempt=attempt, posts=posts_desc))
    raise RuntimeError(f"could not build {world}.{family}.L{level}.{seed}")


def exhaustive_lists(maxlen, vals):
    out = []
    for n in range(0, maxlen + 1):
        out += [(tuple(p),) for p in itertools.product(vals, repeat=n)]
    return out
