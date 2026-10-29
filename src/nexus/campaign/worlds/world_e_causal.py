"""World E - active causal discovery [WHOLLY HELD-OUT TARGET WORLD] (NOT LOCKED).
Deterministic structural causal models over small integer variables (0..3). An input is an intervention vector d
(entry -1 = not intervened, otherwise do(V_i = d_i)) plus the visible exogenous context c. Training evidence is
OBSERVATIONAL ONLY (d all -1), where confounding makes several mechanisms indistinguishable; only interventions (queries)
separate them. Verification: exact interventional prediction on 30 hidden inputs with random do(.) interventions;
E4 is interactive control (the 'valid' protocol: success iff the chosen intervention achieves the goal).
  E1 hidden latent switches / structure identification   E2 interventional do(X) vs observational response
  E3 delayed causal chains (lagged / accumulated effects) E4 budgeted experiments, then a goal-directed control decision"""
from .base import Mech, Post

WORLD = "E"
FAMILIES = ("E1", "E2", "E3", "E4")
Q_BUDGET = 6


def _ctx(r, n):
    return tuple(r.randint(0, 3) for _ in range(n))


def _do(r, n, p=0.5):
    return tuple(r.randint(0, 3) if r.random() < p else -1 for _ in range(n))


def _co(d, v):
    return d if d >= 0 else v


def _resp(rng):
    v = rng.choice(("add", "mul", "max", "copy"))
    k = rng.randint(1, 3)
    f = {"add": lambda a, b: (a + b) % 4, "mul": lambda a, b: (a * b) % 4, "max": max, "copy": lambda a, b: a}[v]
    return f, v, k


def gen(family, rng, level):
    obs2 = lambda r: ((-1, -1), _ctx(r, 3))               # noqa: E731
    int2 = lambda r: (_do(r, 2), _ctx(r, 3))              # noqa: E731
    if family == "E1":
        a, b = rng.sample(range(3), 2)
        h = rng.randint(0, 1)

        def f(x):
            d, c = x
            X = _co(d[0], c[a])
            return _co(d[1], X if h else c[b])
        return Mech(fn=f, sig=("l", "l"), out="i", descr=f"switch[X=c{a},Y<-{'X' if h else f'c{b}'}]", train=obs2,
                    iface=int2, verify_kind="interventional")
    if family == "E2":
        g, v, _ = _resp(rng)
        j = rng.randrange(3)

        def f(x):
            d, c = x
            X = _co(d[0], c[0])
            return _co(d[1], g(X, c[j]))
        return Mech(fn=f, sig=("l", "l"), out="i", descr=f"do[X=c0,Y={v}(X,c{j})]", train=obs2, iface=int2,
                    verify_kind="interventional")
    if family == "E3":
        lag = rng.randint(1, 2)
        acc = rng.random() < 0.4

        def f(x):
            d, nat = x
            X = tuple(_co(a, b) for a, b in zip(d, nat))
            if acc:
                return tuple(sum(X[:max(0, t - lag + 1)]) for t in range(len(X)))
            return ((0,) * lag + X)[:len(X)]

        def tr(r):
            n = r.randint(4, 7)
            return ((-1,) * n, _ctx(r, n))

        def it(r):
            n = r.randint(2, 8)
            return (_do(r, n, 0.4), _ctx(r, n))
        return Mech(fn=f, sig=("l", "l"), out="l", descr=f"chain[{'acc' if acc else 'lag'}={lag}]", train=tr, iface=it,
                    verify_kind="interventional")
    if family == "E4":
        m = rng.choice((1, 3))
        j = rng.randrange(2)
        extra = level >= 3

        def outcome(c, a):
            y = (a * m + c[j]) % 4
            return (y + c[2]) % 4 if extra else y

        def demo(x):
            c = x[0]
            return min(a for a in range(4) if outcome(c, a) == c[3])
        return Mech(fn=demo, sig=("l",), out="i", descr=f"control[Y=({m}a+c{j}){'+c2' if extra else ''},goal=c3]",
                    protocol="valid", valid=lambda x, y: isinstance(y, int) and 0 <= y <= 3 and outcome(x[0], y) == x[0][3],
                    train=lambda r: (_ctx(r, 4),), iface=lambda r: (_ctx(r, 4),), verify_kind="interactive_control",
                    own_levels=True)
    raise KeyError(family)


def posts(family, rng):
    if family in ("E1", "E2"):
        g, v, k = _resp(rng)
        return [Post(lambda y: g(y % 4, k), "i", "i", f"resp[{v},{k}]")]
    if family == "E3":
        lag = rng.randint(1, 2)
        return [Post(lambda l: ((0,) * lag + l)[:len(l)], "l", "l", f"lag[{lag}]")]
    return []
