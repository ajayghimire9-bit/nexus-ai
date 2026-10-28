"""u5 stateful lifecycle families (NOT LOCKED): one per domain, each a per-key machine with control modes AND data registers,
so no flat per-key dictionary lookup (last record per key -> output) can express it.

  L.barrier   logistics release barrier: an order is released only after BOTH payment and packing (either order); delivery
              only after release; cancel only before release. X3 (test only): RETURN after delivery.
  C.clearing  two-phase clearing: NEW / AMEND set the amount while open; PREPARE locks; COMMIT settles the LAST ACCEPTED
              amount; ABORT unlocks; CANCEL only while open. X3: PARTIAL fills while prepared (emit the fill; the settled
              amount at COMMIT is reduced by every fill).
  I.session   device sessions: READs inside a session accumulate count and sum; DISCONNECT (or a re-CONNECT) emits the
              session summary; READs outside a session are invalid. X3: SUSPEND / RESUME (READs while suspended are ignored).

Every event yields a list of rows (label, v1, v2). Invalid transitions emit ('q:invalid', None, None). The learner never
sees modes, register names or transition tables - only events, oracle outputs and its own membership queries."""
from __future__ import annotations

import random

Q = ("q:invalid", None, None)
FAM_KINDS = {"L.barrier": ["CREATE", "PAY", "PACK", "DELIVER", "CANCEL"],
             "C.clearing": ["NEW", "AMEND", "PREPARE", "COMMIT", "ABORT", "CANCEL"],
             "I.session": ["CONNECT", "READ", "DISCONNECT"]}
X3_KINDS = {"L.barrier": ["RETURN"], "C.clearing": ["PARTIAL"], "I.session": ["SUSPEND", "RESUME"]}
STATEFUL = tuple(FAM_KINDS)


def step(fam, st, kind, v, x3):
    """Reference transition: (state, kind, value) -> (state', rows). state = (mode, a, b)."""
    m, a, b = st
    if fam == "L.barrier":
        if kind == "CREATE":
            return (("created", v, 0), []) if m == "absent" else (st, [Q])
        if kind in ("PAY", "PACK"):
            first, other = ("paid", "packed") if kind == "PAY" else ("packed", "paid")
            if m == "created":
                return (first, a, 0), []
            if m == other:
                return ("released", a, 0), [("release", a, None)]
            return st, [Q]
        if kind == "DELIVER":
            return (("delivered", a, 0), [("delivered", a, None)]) if m == "released" else (st, [Q])
        if kind == "CANCEL":
            return (("cancelled", a, 0), [("cancelled", a, None)]) if m in ("created", "paid", "packed") else (st, [Q])
        if kind == "RETURN" and x3:
            return (("returned", a, 0), [("returned", v, None)]) if m == "delivered" else (st, [Q])
    if fam == "C.clearing":
        if kind == "NEW":
            return (("open", v, 0), []) if m == "absent" else (st, [Q])
        if kind == "AMEND":
            return (("open", v, 0), []) if m == "open" else (st, [Q])
        if kind == "PREPARE":
            return (("prepared", a, 0), []) if m == "open" else (st, [Q])
        if kind == "COMMIT":
            return (("settled", a, 0), [("settled", a, None)]) if m == "prepared" else (st, [Q])
        if kind == "ABORT":
            return (("open", a, 0), []) if m == "prepared" else (st, [Q])
        if kind == "CANCEL":
            return (("cancelled", a, 0), [("cancelled", a, None)]) if m == "open" else (st, [Q])
        if kind == "PARTIAL" and x3:
            return (("prepared", round(a - v, 6), 0), [("partial", v, None)]) if m == "prepared" else (st, [Q])
    if fam == "I.session":
        if kind == "CONNECT":
            if m in ("active", "suspended"):
                return ("active", 0, 0), [("session", a, b)]
            return ("active", 0, 0), []
        if kind == "READ":
            if m == "active":
                return ("active", a + 1, round(b + v, 6)), []
            if m == "suspended":
                return st, []
            return st, [Q]
        if kind == "DISCONNECT":
            return (("idle", 0, 0), [("session", a, b)]) if m in ("active", "suspended") else (st, [Q])
        if kind == "SUSPEND" and x3:
            return (("suspended", a, b), []) if m == "active" else (st, [Q])
        if kind == "RESUME" and x3:
            return (("active", a, b), []) if m == "suspended" else (st, [Q])
    return st, [Q]                                                   # unknown kind: invalid


INIT = {"L.barrier": ("absent", 0, 0), "C.clearing": ("absent", 0, 0), "I.session": ("idle", 0, 0)}

SYN = {"key": ["order_id", "trade_id", "device_id", "ref", "entity"], "kind": ["event", "type", "op", "action", "msg_type"],
       "val": ["amount", "qty_value", "reading", "value", "amt"], "seq": ["seq", "offset", "lsn", "ts"]}


class Schema:
    def __init__(self, rnd):
        self.key, self.kind, self.val, self.seq = (rnd.choice(SYN[r]) for r in ("key", "kind", "val", "seq"))
        if len({self.key, self.kind, self.val, self.seq}) < 4:
            self.key, self.kind, self.val, self.seq = "key_f", "kind_f", "val_f", "seq_f"
        self.distract = rnd.sample(["src", "shard", "batch", "retry"], 2)


def reference(fam, events, schema, x3=False):
    """Oracle: per-event output rows for an interleaved multi-key stream."""
    st, out = {}, []
    for e in events:
        k = e.get(schema.key)
        s = st.get(k, INIT[fam])
        v = e.get(schema.val)
        v = v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
        s2, rows = step(fam, s, e.get(schema.kind), v, x3)
        st[k] = s2
        out.append(rows)
    return out


def _value(fam, rnd):
    return round(rnd.uniform(1, 900), 2) if fam != "I.session" else round(rnd.uniform(-10, 60), 1)


def gen_stream(fam, rnd, schema, n_keys, x3=False, p_valid=0.85, max_len=9, key_base=0, seq0=0):
    kinds = FAM_KINDS[fam] + (X3_KINDS[fam] if x3 else [])
    per_key = []
    for i in range(n_keys):
        k = f"K{key_base + i:05d}"
        st, evs = INIT[fam], []
        for _ in range(rnd.randint(2, max_len)):
            valid = [kd for kd in kinds if step(fam, st, kd, 1.0, x3)[1] != [Q]]
            kd = rnd.choice(valid) if valid and rnd.random() < p_valid else rnd.choice(kinds)
            v = _value(fam, rnd)
            st, _ = step(fam, st, kd, v, x3)
            evs.append({schema.key: k, schema.kind: kd, schema.val: v})
        per_key.append(evs)
    events, idx = [], [0] * n_keys                                   # random interleaving, per-key order kept
    live = [i for i in range(n_keys) if per_key[i]]
    while live:
        i = rnd.choice(live)
        events.append(per_key[i][idx[i]])
        idx[i] += 1
        if idx[i] >= len(per_key[i]):
            live.remove(i)
    for j, e in enumerate(events):
        e[schema.seq] = seq0 + j
        for d in schema.distract:
            e[d] = rnd.randint(0, 9)
    return events


class StreamTask:
    """A Pillar 1 task: a training stream with oracle outputs, a held-out stream, and a counted query oracle."""

    def __init__(self, fam, seed, n_train_keys=40, n_test_keys=200, x3_test=False, x3_train=False):
        rnd = random.Random(f"u5-stream-{fam}-{seed}")
        self.fam, self.seed, self.x3_train, self.x3_test = fam, seed, x3_train, x3_test
        self.schema = Schema(rnd)
        self.train = gen_stream(fam, rnd, self.schema, n_train_keys, x3=x3_train)
        self.test = gen_stream(fam, rnd, self.schema, n_test_keys, x3=x3_test, key_base=50000, seq0=10 ** 6)
        self.y_train = reference(fam, self.train, self.schema, x3_train)
        self.n_queries = self.n_query_events = 0

    def query(self, events, x3=None):
        """Membership query: the oracle's outputs for a learner-constructed stream (counted)."""
        self.n_queries += 1
        self.n_query_events += len(events)
        return reference(self.fam, events, self.schema, self.x3_train if x3 is None else x3)

    def score(self, run_fn, x3=None):
        """run_fn(events) -> per-event rows. Returns (stream exact, event accuracy, key-level accuracy)."""
        x3 = self.x3_test if x3 is None else x3
        want = reference(self.fam, self.test, self.schema, x3)
        try:
            got = run_fn(self.test)
        except Exception:                                            # noqa: BLE001
            return dict(exact=False, event_acc=0.0, key_acc=0.0, crashed=True)
        ok = [rows_eq(g, w) for g, w in zip(got, want)] if len(got) == len(want) else [False] * len(want)
        bad_keys, keys = set(), set()
        for e, o in zip(self.test, ok):
            k = e[self.schema.key]
            keys.add(k)
            if not o:
                bad_keys.add(k)
        return dict(exact=all(ok), event_acc=sum(ok) / len(ok), key_acc=1 - len(bad_keys) / len(keys), crashed=False)


def _veq(a, b):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6 * max(1.0, abs(b))
    return a == b


def rows_eq(g, w):
    return len(g) == len(w) and all(len(x) == 3 and x[0] == y[0] and _veq(x[1], y[1]) and _veq(x[2], y[2]) for x, y in zip(g, w))
