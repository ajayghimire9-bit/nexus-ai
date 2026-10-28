"""Method-invention (mi) micro-episodes (NOT LOCKED): oc_ocean's per-key lifecycle machines (structure generator reused) with
register-update MECHANISM FAMILIES, some outside the existing learner's hypothesis class (updates over (acc, x) with + and -,
size <= 5, constants 0 / 1).

Families (frozen in the mi pre-registration before any learner runs on them):
  K   known       the oc updates: keep, set, zero, acc + x, acc - x, acc + 1, acc + x + x, x - acc
  dev-unfamiliar  (discovery and validation)  MUL  acc * x        ADDC  acc + c, c in {3, 5, 10}       SUBH  acc - x / 2
  WITHHELD        (confirmation only)          SCL  acc * c + x, c in {2, 3}   AVG  (acc + x) / 2   MAX  x if acc < x else acc
An episode of family F has at least one CONSEQUENTIAL F-update (replacing every F-update by acc + x changes the training outputs);
its other updates are drawn from K. Episode = training stream + oracle outputs, counted membership-query oracle, held-out stream;
scored exact on the held-out stream (evaluator outside every learner)."""
from __future__ import annotations

import random

from nexus import oc_ocean as OC
from nexus import u5_statesplit as SP

A, X_ = ("var", "acc"), ("var", "x")


def _b(op, a, b):
    return ("b", op, a, b)


def _c(k):
    return ("const", k)


FAMILIES = {
    "K": None,
    "MUL": lambda rnd: _b("*", A, X_),
    "ADDC": lambda rnd: _b("+", A, _c(rnd.choice([3, 5, 10]))),
    "SUBH": lambda rnd: _b("-", A, _b("/", X_, _c(2))),
    "SCL": lambda rnd: _b("+", _b("*", A, _c(rnd.choice([2, 3]))), X_),
    "AVG": lambda rnd: _b("/", _b("+", A, X_), _c(2)),
    "MAX": lambda rnd: ("if", _b("<", A, X_), X_, A),
}
DEV_FAMILIES = ("K", "MUL", "ADDC", "SUBH")
WITHHELD = ("SCL", "AVG", "MAX")


def run(machine, events):
    """Reference semantics: rows use register values BEFORE the update; updates are expressions over (acc, x)."""
    st, regs, out = {}, {}, []
    for e in events:
        k, s = e["key"], e["kind"]
        x = e.get("v", 0)
        x = x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0
        q = st.get(k, 0)
        if (q, s) not in machine["delta"]:
            out.append([("q:invalid", None, None)])
            continue
        r = regs.get(k, [0] * machine["regs"])
        rows = []
        for lab, v1, v2 in machine["lam"][(q, s)]:
            rows.append((lab, *[None if v is None else (x if v[0] == "cur" else r[v[1]]) for v in (v1, v2)]))
        new = list(r)
        for i in range(machine["regs"]):
            g = machine["upd"][i].get((q, s))
            if g is not None:
                val = SP.S.ev(g, {"acc": r[i], "x": x})
                new[i] = round(val, 6) if isinstance(val, (int, float)) else 0
        regs[k] = new
        st[k] = machine["delta"][(q, s)]
        out.append(rows)
    return out


def _as_expr(m):
    m = dict(m, upd=[{t: OC.UPDATES[u] for t, u in d.items()} for d in m["upd"]])
    return m


class Episode:
    def __init__(self, seed, family, n_train_keys=20, n_test_keys=100, max_tries=400):
        rnd = random.Random(f"mi-ep-{family}-{seed}")
        self.seed, self.family, self.regime = seed, family, "base"
        for _ in range(max_tries):
            m = OC._random_machine(rnd, "lifecycle")
            reach = {0}
            for _ in range(m["modes"]):
                reach |= {m["delta"][(q, k)] for (q, k) in m["delta"] if q in reach}
            if len(reach) != m["modes"] or not any(m["lam"].values()):
                continue
            m = _as_expr(m)
            m["extra"] = None
            tr = OC._stream(m, rnd, n_train_keys, m["base"])
            if FAMILIES[family] is not None:
                slots = [(i, t) for i in range(m["regs"]) for t in m["delta"] if t[0] in reach]
                rnd.shuffle(slots)
                placed = slots[:rnd.randint(1, 2)]
                for i, t in placed:
                    m["upd"][i][t] = FAMILIES[family](rnd)
                base = dict(m, upd=[dict(d) for d in m["upd"]])
                for i, t in placed:
                    base["upd"][i][t] = OC.UPDATES["add"]
                if run(base, tr) == run(m, tr):                       # the F-update must change the training outputs
                    continue
            y = run(m, tr)
            if not any(r for rows in y for r in rows if r[0] != "q:invalid"):
                continue
            break
        self.machine, self.train, self.y_train = m, tr, run(m, tr)
        self.test = OC._stream(m, rnd, n_test_keys, m["base"], key_base=5000)
        self.n_queries = self.n_query_events = 0
        self.contract = None
        self.needs = dict(regs=m["regs"], modes=m["modes"], family=family)

    def query(self, events):
        self.n_queries += 1
        self.n_query_events += len(events)
        return run(self.machine, events)

    def score(self, run_fn):
        want = run(self.machine, self.test)
        try:
            got = run_fn(self.test)
        except Exception:                                            # noqa: BLE001
            return dict(exact=False, key_acc=0.0)
        ok = [SP._rows_eq(list(map(tuple, g)), list(map(tuple, w))) for g, w in zip(got, want)]
        bad = {e["key"] for e, o in zip(self.test, ok) if not o}
        return dict(exact=all(ok), key_acc=1 - len(bad) / len({e["key"] for e in self.test}))
