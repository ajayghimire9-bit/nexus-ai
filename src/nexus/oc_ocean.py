"""The micro-project ocean (NOT LOCKED): hundreds of small, independent lifecycle-learning episodes on CPU.

An episode = one random per-key lifecycle machine (the hidden mechanism) + one fault regime, a short training stream, a
held-out stream, a counted oracle (membership queries), and a DECLARED grey-box contract.

Machine (same representation the learner targets, so the target is realisable once the hypothesis space has grown
enough): modes 2-4; event kinds 3-6; 1-2 numeric registers; per (mode, kind): next mode, emitted rows (label + up to two
value slots, each = a register BEFORE the update or the event's value), and register updates drawn from primitives over
(acc, x) up to size 5 (keep, x, 0, acc + x, acc - x, acc + 1, acc + x + x, x - acc, ...). Unused (mode, kind) pairs reject
with ('q:invalid', None, None).
Regimes: 'base' | 'new_kind' (one extra kind appears in the second half of the training stream and in the held-out stream).
Domains: 'lifecycle' (acyclic-ish workflows with terminal modes) | 'protocol' (cyclic session protocols; Part 3's second
domain, generated with different structural statistics and its own vocabulary).
Grey-box contract (what a schema / pipeline contract would declare): for every kind, whether it READS the value field and
which labels it MAY emit. It never reveals modes, registers or updates."""
from __future__ import annotations

import random

from nexus import u5_statesplit as SP

VOCAB = {"lifecycle": ["OPEN", "ADD", "HOLD", "RELEASE", "CLOSE", "VOID", "AMEND", "FLUSH", "TICK", "SETTLE"],
         "protocol": ["HELLO", "AUTH", "PING", "CMD", "ACK", "NACK", "SYNC", "BYE", "RETRY", "KEEP"]}
LABELS = {"lifecycle": ["total", "settled", "voided", "flushed"], "protocol": ["session", "ack", "summary", "fault"]}
UPDATES = {"keep": ("var", "acc"), "set": ("var", "x"), "zero": ("const", 0), "add": ("b", "+", ("var", "acc"), ("var", "x")),
           "sub": ("b", "-", ("var", "acc"), ("var", "x")), "inc": ("b", "+", ("var", "acc"), ("const", 1)),
           "add2": ("b", "+", ("b", "+", ("var", "acc"), ("var", "x")), ("var", "x")),
           "rsub": ("b", "-", ("var", "x"), ("var", "acc"))}
DEPTH5 = {"add2", "rsub"}


def _random_machine(rnd, domain):
    nm = rnd.randint(2, 4) if domain == "lifecycle" else rnd.randint(3, 4)
    nk = rnd.randint(3, 5)
    kinds = rnd.sample(VOCAB[domain], nk + 1)
    base, extra = kinds[:nk], kinds[nk]
    nr = rnd.choice([1, 1, 2])
    labels = rnd.sample(LABELS[domain], 2)
    delta, lam, upd = {}, {}, [dict() for _ in range(nr)]
    used = {}
    for q in range(nm):
        for k in base + [extra]:
            valid = rnd.random() < (0.55 if domain == "lifecycle" else 0.7)
            if q == 0 and k == base[0]:
                valid = True                                        # every machine can start
            if not valid:
                continue
            if domain == "lifecycle":
                q2 = min(nm - 1, q + rnd.choice([0, 0, 1])) if rnd.random() < 0.8 else rnd.randrange(nm)
            else:
                q2 = rnd.randrange(nm)                              # cyclic protocols
            delta[(q, k)] = q2
            rows = []
            if rnd.random() < 0.35:
                lab = rnd.choice(labels)
                v1 = ("reg", 0)
                v2 = ("reg", 1) if nr == 2 and rnd.random() < 0.6 else (("cur", None) if rnd.random() < 0.3 else None)
                rows.append((lab, v1, v2))
            lam[(q, k)] = rows
            for i in range(nr):
                u = rnd.choices(list(UPDATES), weights=[5, 2, 1, 3, 1, 2, 1, 1])[0]
                if rows and rnd.random() < 0.5:
                    u = "zero"                                       # emitting transitions often reset
                if u != "keep":
                    upd[i][(q, k)] = u
            used[k] = used.get(k, 0) + 1
    return dict(modes=nm, base=base, extra=extra, regs=nr, delta=delta, lam=lam, upd=upd, labels=labels, domain=domain)


def run(machine, events, key="key", kind="kind", val="v", use_extra=True):
    """Reference semantics (the hidden mechanism). Rows use values BEFORE the update; updates use acc and the event value."""
    st, regs, out = {}, {}, []
    for e in events:
        k, s = e[key], e[kind]
        x = e.get(val, 0)
        x = x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0
        q = st.get(k, 0)
        if (q, s) not in machine["delta"] or (s == machine["extra"] and not use_extra):
            out.append([("q:invalid", None, None)])
            continue
        r = regs.get(k, [0] * machine["regs"])
        rows = []
        for lab, v1, v2 in machine["lam"][(q, s)]:
            vs = []
            for v in (v1, v2):
                vs.append(None if v is None else (x if v[0] == "cur" else r[v[1]]))
            rows.append((lab, vs[0], vs[1]))
        new = list(r)
        for i in range(machine["regs"]):
            u = machine["upd"][i].get((q, s))
            if u:
                new[i] = round(SP.S.ev(UPDATES[u], {"acc": r[i], "x": x}), 6)
        regs[k] = new
        st[k] = machine["delta"][(q, s)]
        out.append(rows)
    return out


def contract(machine):
    """Declared grey-box contract per kind: reads_value, may_emit labels."""
    c = {}
    for k in machine["base"] + [machine["extra"]]:
        reads = any(machine["upd"][i].get((q, kk)) in ("set", "add", "sub", "add2", "rsub")
                    for i in range(machine["regs"]) for (q, kk) in machine["delta"] if kk == k)
        reads = reads or any(v is not None and v[0] == "cur" for (q, kk), rows in machine["lam"].items() if kk == k
                             for r in rows for v in r[1:])
        emits = sorted({r[0] for (q, kk), rows in machine["lam"].items() if kk == k for r in rows})
        c[k] = dict(reads_value=reads, may_emit=emits)
    return c


def _stream(machine, rnd, n_keys, kinds, key_base=0, p_valid=0.8, max_len=10):
    evs = []
    per = []
    for i in range(n_keys):
        q, seq = 0, []
        for _ in range(rnd.randint(3, max_len)):
            valid = [k for k in kinds if (q, k) in machine["delta"]]
            k = rnd.choice(valid) if valid and rnd.random() < p_valid else rnd.choice(kinds)
            if (q, k) in machine["delta"]:
                q = machine["delta"][(q, k)]
            seq.append({"key": f"k{key_base + i}", "kind": k, "v": round(rnd.uniform(1, 99), 2)})
        per.append(seq)
    idx = [0] * n_keys
    live = list(range(n_keys))
    while live:
        i = rnd.choice(live)
        evs.append(per[i][idx[i]])
        idx[i] += 1
        if idx[i] >= len(per[i]):
            live.remove(i)
    for j, e in enumerate(evs):
        e["seq"] = j
    return evs


class Episode:
    def __init__(self, seed, domain="lifecycle", regime=None, n_train_keys=20, n_test_keys=100):
        rnd = random.Random(f"oc-ep-{domain}-{seed}")
        self.seed, self.domain = seed, domain
        self.regime = regime or rnd.choice(["base", "new_kind"])
        for _ in range(200):
            m = _random_machine(rnd, domain)
            reach = {0}
            for _ in range(m["modes"]):
                reach |= {m["delta"][(q, k)] for (q, k) in m["delta"] if q in reach}
            emits = any(rows for rows in m["lam"].values())
            if len(reach) == m["modes"] and emits:
                break
        self.machine = m
        kinds_train = m["base"] + ([m["extra"]] if self.regime == "new_kind" else [])
        tr = _stream(m, rnd, n_train_keys, m["base"])
        if self.regime == "new_kind":
            tr += _stream(m, rnd, n_train_keys // 2, kinds_train, key_base=1000)
            for j, e in enumerate(tr):
                e["seq"] = j
        self.train = tr
        self.test = _stream(m, rnd, n_test_keys, kinds_train, key_base=5000)
        self.y_train = run(m, self.train)
        self.contract = contract(m)
        self.n_queries = self.n_query_events = 0
        self.needs = dict(regs=m["regs"], depth5=any(u in DEPTH5 for d in m["upd"] for u in d.values()), modes=m["modes"])

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
        ok = [SP._rows_eq(g, w) for g, w in zip(got, want)]
        bad = {e["key"] for e, o in zip(self.test, ok) if not o}
        keys = {e["key"] for e in self.test}
        return dict(exact=all(ok), key_acc=1 - len(bad) / len(keys))


def suite(kind, domain="lifecycle", n=None, start=0):
    from nexus import oc_seeds  # noqa: F401
    from nexus import seed_registry as R
    seeds = list(R.REGISTRY[("oc", kind)])
    seeds = seeds[start:start + n] if n else seeds
    return [Episode(s, domain) for s in seeds]
