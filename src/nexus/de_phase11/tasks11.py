"""Phase 11 task generator (NOT LOCKED). GENERATOR INTERNALS ONLY: the reference program of each task is used here to compute the
expected outputs and is NEVER placed in the learner-facing task (synth11 receives anonymous ids, visible inputs / outputs, the output
schema and the evidence callback; admission receives validation batches; the evaluator receives hidden batches).

Batches per task: vis_a, vis_b (visible), evidence (released on one request), valid (admission only), hid1, hid2 (evaluator only).
Column names are drawn from a neutral pool (base or held-out) and shuffled; distractor columns pad every relation.
THRESHOLD CONSTANTS: a threshold is chosen among the published QUANTILE CONSTANTS of its column on the visible batches (synth11.mine:
min, quartiles, max), i.e. the task world guarantees that thresholds are reachable by that general mining rule (disclosed).

SOURCE FAMILIES (Stage A; 5-8 columns): coalesce, condsum (conditional sum / count-if), dedup (latest per key), preagg (pre-aggregated
left join + default), upsert (pure next-state upsert), json (extract + explicit cast), flag (threshold label), filtmap (filter +
arithmetic projection).
COMPOSITIONS (Stage B training, 10-14 columns, 2-3 relations): B1 dedup->preagg, B2 upsert->flag, B3 filter->condsum, B4 dedup->coalesce,
B5 preagg + flag, B6 dedup->json. WITHHELD (Suite 1 only; never in Stage A / B, admission or development tuning): W1 dedup->upsert,
W2 upsert->preagg, W3 filter->dedup->coalesce, W4 json->flag, W5 dedup->condsum, W6 json + coalesce, W7 dedup->flag, W8 upsert->coalesce."""
from __future__ import annotations

import json

from nexus.de_phase10c.rng10c import rng as rng10c
from nexus.de_phase11 import core11 as C

NAMES = dict(base=["acct", "ref", "amt", "qty", "seq", "code", "flag", "note", "grp", "val", "cat", "tag", "num", "cnt", "lvl", "pos", "src", "kind",
                   "unit", "rate", "zone", "slot", "mark", "step"],
             heldout=["alpha", "bravo", "delta", "echo", "golf", "hotel", "india", "kilo", "lima", "mike", "oscar", "papa", "romeo", "sierra",
                      "tango", "victor", "xray", "yank", "zulu", "nova", "orbit", "pixel", "quark", "radix"])
SOURCE = ("coalesce", "condsum", "dedup", "preagg", "upsert", "json", "flag", "filtmap")
COMPOSE = ("B1", "B2", "B3", "B4", "B5", "B6")
WITHHELD = ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8")
BATCHES = (("vis_a", 10), ("vis_b", 10), ("evidence", 10), ("valid", 10), ("hid1", 18), ("hid2", 18))
I, S = C.INT, C.STR


def quantiles(vals):
    v = sorted(set(x for x in vals if x is not None))
    if not v:
        return []
    return sorted({v[round(q * (len(v) - 1))] for q in (0, 0.25, 0.5, 0.75, 1)})


class Namer:
    def __init__(self, r, pool):
        self.r, self.pool = r, list(NAMES[pool])
        self.r.shuffle(self.pool)
        self.i = 0

    def __call__(self):
        n = self.pool[self.i % len(self.pool)] + ("" if self.i < len(self.pool) else str(self.i // len(self.pool)))
        self.i += 1
        return n


def col(n):
    return ("col", n)


def const(v, t):
    return ("const", v, t)


def coalesce(a, b):
    return ("branch", ("isnull", a), b, a)


# ------------------------------------------------------------------ relation data builders
def distractors(r, nm, k):
    out = []
    for _ in range(k):
        t = r.choice([I, S])
        out.append((nm(), t))
    return out


def dval(r, t):
    return r.randint(0, 999) if t == I else r.choice(["a", "b", "c", "x", "y"]) + str(r.randint(0, 9))


class Fam:
    """A generated task family instance: schemas, a reference program and a batch generator."""

    def __init__(self, schemas, ref, gen, out_names=None):
        self.schemas, self.ref, self.gen, self.out_names = schemas, ref, gen, out_names


def _rel(schema, rows):
    return C.Rel([n for n, _ in schema], [t for _, t in schema], rows)


def fam_coalesce(r, nm, width, base=None):
    k, a, b = nm(), nm(), nm()
    t = r.choice([I, S])
    D = distractors(r, nm, max(0, width - 3))
    rn = base or nm()
    sch = [(k, I), (a, t), (b, t)] + D
    r.shuffle(sch)
    vk, vv = nm(), nm()
    ref = ("map", ("rel", rn), ((vk, col(k)), (vv, coalesce(col(a), col(b)))))

    def gen(rr, n):
        rows = []
        ids = rr.sample(range(1, 500), n)
        for i in range(n):
            av = None if rr.random() < 0.4 else dval(rr, t)
            row = {k: ids[i], a: av, b: dval(rr, t)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[c] for c, _ in sch))
        return {rn: _rel(sch, rows)}
    return Fam({rn: sch}, ref, gen)


def fam_condsum(r, nm, width, base=None):
    g, c, x = nm(), nm(), nm()
    D = distractors(r, nm, max(0, width - 3))
    rn = base or nm()
    sch = [(g, S), (c, S), (x, I)] + D
    r.shuffle(sch)
    gv = ["g" + str(i) for i in range(3)]
    cv = r.sample(["p", "q", "r", "s", "t"], 3)
    target = cv[0]
    countif = r.random() < 0.35
    og, on = nm(), nm()
    meas = ("branch", ("cmp", "eq", col(c), const(target, S)), const(1, I) if countif else col(x), const(0, I))
    ref = ("map", ("fold", ("rel", rn), (g,), ((on, "sum", meas),)), ((og, col(g)), (on, col(on))))

    def gen(rr, n):
        rows = []
        for i in range(n):
            row = {g: gv[i % 3], c: cv[0] if i % 2 == 0 else rr.choice(cv), x: rr.randint(1, 40)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[cc] for cc, _ in sch))
        return {rn: _rel(sch, rows)}
    return Fam({rn: sch}, ref, gen)


def fam_dedup(r, nm, width, base=None):
    k, s, v = nm(), nm(), nm()
    D = distractors(r, nm, max(0, width - 3))
    rn = base or nm()
    sch = [(k, I), (s, I), (v, I)] + D
    r.shuffle(sch)
    ok, ov = nm(), nm()
    ref = ("map", ("rank", ("rel", rn), (k,), ((col(s), True),), 1), ((ok, col(k)), (ov, col(v))))

    def gen(rr, n):
        rows, seqs = [], rr.sample(range(1, 900), n)
        keys = [rr.randint(1, max(2, n // 2)) for _ in range(n)]
        for i in range(n):
            row = {k: keys[i], s: seqs[i], v: rr.randint(0, 99)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[cc] for cc, _ in sch))
        return {rn: _rel(sch, rows)}
    return Fam({rn: sch}, ref, gen)


def fam_preagg(r, nm, width, base=None):
    pid, pa, fk, q = nm(), nm(), nm(), nm()
    D1 = distractors(r, nm, max(0, width // 2 - 2))
    D2 = distractors(r, nm, max(0, width // 2 - 2))
    L, R = nm(), nm()
    sl = [(pid, I), (pa, S)] + D1
    sr = [(fk, I), (q, I)] + D2
    r.shuffle(sl)
    r.shuffle(sr)
    o1, o2, o3 = nm(), nm(), nm()
    agg = ("fold", ("rel", R), (fk,), (("m", "sum", col(q)),))
    ref = ("map", ("join", "left", ("rel", L), agg, (pid,), (fk,)), ((o1, col(pid)), (o2, col(pa)), (o3, coalesce(col("m"), const(0, I)))))

    def gen(rr, n):
        ids = rr.sample(range(1, 300), max(3, n // 2))
        lrows = []
        for i in ids:
            row = {pid: i, pa: rr.choice(["u", "v", "w"])}
            row.update({d: dval(rr, dt) for d, dt in D1})
            lrows.append(tuple(row[c] for c, _ in sl))
        rrows = []
        for _ in range(n):
            row = {fk: rr.choice(ids[: max(1, len(ids) - 2)]), q: rr.randint(1, 20)}
            row.update({d: dval(rr, dt) for d, dt in D2})
            rrows.append(tuple(row[c] for c, _ in sr))
        return {L: _rel(sl, lrows), R: _rel(sr, rrows)}
    return Fam({L: sl, R: sr}, ref, gen)


def fam_upsert(r, nm, width, base=None):
    k, v, w = nm(), nm(), nm()
    D = distractors(r, nm, max(0, width - 3))
    O, N = nm(), nm()
    sch = [(k, I), (v, I), (w, S)] + D
    r.shuffle(sch)
    ref = ("union", ("join", "anti", ("rel", O), ("rel", N), (k,), (k,)), ("rel", N))

    def gen(rr, n):
        keys = rr.sample(range(1, 400), n)
        new = rr.sample(keys, max(2, n // 3)) + rr.sample(range(400, 500), 2)

        def row(kk):
            d = {k: kk, v: rr.randint(0, 99), w: rr.choice(["s1", "s2", "s3"])}
            d.update({x: dval(rr, t) for x, t in D})
            return tuple(d[c] for c, _ in sch)
        return {O: _rel(sch, [row(kk) for kk in keys]), N: _rel(sch, [row(kk) for kk in new])}
    return Fam({O: sch, N: sch}, ref, gen)


def fam_json(r, nm, width, base=None):
    pid, pl = nm(), nm()
    D = distractors(r, nm, max(0, width - 2))
    rn = base or nm()
    sch = [(pid, I), (pl, S)] + D
    r.shuffle(sch)
    ka, kb = r.sample(["a", "b", "c", "d"], 2)
    o1, o2 = nm(), nm()
    ref = ("map", ("rel", rn), ((o1, col(pid)), (o2, ("cast", ("json", col(pl), (ka,)), I))))

    def gen(rr, n):
        rows, ids = [], rr.sample(range(1, 600), n)
        for i in range(n):
            o = {kb: rr.choice(["x", "y"])}
            if rr.random() > 0.2:
                o[ka] = rr.randint(0, 500)
            row = {pid: ids[i], pl: json.dumps(o)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[c] for c, _ in sch))
        return {rn: _rel(sch, rows)}
    return Fam({rn: sch}, ref, gen)


def fam_flag(r, nm, width, base=None, vis_vals=None):
    pid, x = nm(), nm()
    D = distractors(r, nm, max(0, width - 2))
    rn = base or nm()
    sch = [(pid, I), (x, I)] + D
    r.shuffle(sch)
    hi, lo = r.choice([("hi", "lo"), ("y", "n"), ("big", "small"), ("on", "off")])
    o1, o2 = nm(), nm()
    holder = {}

    def ref_of(c):
        return ("map", ("rel", rn), ((o1, col(pid)), (o2, ("branch", ("cmp", "ge", col(x), const(c, I)), const(hi, S), const(lo, S)))))

    def gen(rr, n):
        rows, ids = [], rr.sample(range(1, 600), n)
        for i in range(n):
            row = {pid: ids[i], x: rr.randint(0, 99)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[c] for c, _ in sch))
        return {rn: _rel(sch, rows)}
    f = Fam({rn: sch}, None, gen)
    f.ref_of, f.threshold_col, f.threshold_rel = ref_of, x, rn
    return f


def fam_filtmap(r, nm, width, base=None):
    pid, p, q, z = nm(), nm(), nm(), nm()
    D = distractors(r, nm, max(0, width - 4))
    rn = base or nm()
    sch = [(pid, I), (p, I), (q, I), (z, I)] + D
    r.shuffle(sch)
    o1, o2 = nm(), nm()

    def ref_of(c):
        return ("map", ("filter", ("rel", rn), ("cmp", "gt", col(z), const(c, I))), ((o1, col(pid)), (o2, ("arith", "mul", col(p), col(q)))))

    def gen(rr, n):
        rows, ids = [], rr.sample(range(1, 600), n)
        for i in range(n):
            row = {pid: ids[i], p: rr.randint(1, 12), q: rr.randint(1, 12), z: rr.randint(0, 99)}
            row.update({d: dval(rr, dt) for d, dt in D})
            rows.append(tuple(row[c] for c, _ in sch))
        return {rn: _rel(sch, rows)}
    f = Fam({rn: sch}, None, gen)
    f.ref_of, f.threshold_col, f.threshold_rel = ref_of, z, rn
    return f


SOURCE_FAM = dict(coalesce=fam_coalesce, condsum=fam_condsum, dedup=fam_dedup, preagg=fam_preagg, upsert=fam_upsert, json=fam_json, flag=fam_flag,
                  filtmap=fam_filtmap)


# ------------------------------------------------------------------ compositions (multi-table, wider)
def _items(r, nm, width):
    """A child relation with re-delivered lines: (line id with duplicates, parent ref, quantity, load sequence) + distractors."""
    iid, fk, q, s = nm(), nm(), nm(), nm()
    D = distractors(r, nm, max(0, width - 4))
    sch = [(iid, I), (fk, I), (q, I), (s, I)] + D
    r.shuffle(sch)
    return sch, iid, fk, q, s, D


def compose(kind, r, nm, width):
    """-> Fam for a composition kind (B* training or W* withheld)."""
    if kind in ("B1", "W2"):
        pid, pa = nm(), nm()
        D1 = distractors(r, nm, max(0, width // 2 - 2))
        sl = [(pid, I), (pa, S)] + D1
        r.shuffle(sl)
        L = nm()
        sch, iid, fk, q, s, D2 = _items(r, nm, width // 2 + 2)
        o1, o2, o3 = nm(), nm(), nm()
        if kind == "B1":
            Rn = nm()
            child = ("rank", ("rel", Rn), (iid,), ((col(s), True),), 1)
            rels = {L: sl, Rn: sch}
        else:
            Rn, Nn = nm(), nm()
            child = ("union", ("join", "anti", ("rel", Rn), ("rel", Nn), (iid,), (iid,)), ("rel", Nn))
            rels = {L: sl, Rn: sch, Nn: sch}
        agg = ("fold", child, (fk,), (("m", "sum", col(q)),))
        ref = ("map", ("join", "left", ("rel", L), agg, (pid,), (fk,)), ((o1, col(pid)), (o2, col(pa)), (o3, coalesce(col("m"), const(0, I)))))

        def gen(rr, n):
            ids = rr.sample(range(1, 300), max(3, n // 2))
            lrows = []
            for i in ids:
                row = {pid: i, pa: rr.choice(["u", "v", "w"])}
                row.update({d: dval(rr, dt) for d, dt in D1})
                lrows.append(tuple(row[c] for c, _ in sl))

            def line(lid, par, seq):
                row = {iid: lid, fk: par, q: rr.randint(1, 20), s: seq}
                row.update({d: dval(rr, dt) for d, dt in D2})
                return tuple(row[c] for c, _ in sch)
            lines, seqs = [], iter(rr.sample(range(1, 900), 3 * n))
            for lid in range(1, n + 1):
                par = rr.choice(ids[: max(1, len(ids) - 2)])
                lines.append(line(lid, par, next(seqs)))
                if kind == "B1" and rr.random() < 0.4:
                    lines.append(line(lid, par, next(seqs)))
            env = {L: _rel(sl, lrows), Rn: _rel(sch, lines)}
            if kind == "W2":
                upd = rr.sample(range(1, n + 1), max(2, n // 3))
                env[Nn] = _rel(sch, [line(lid, rr.choice(ids[: max(1, len(ids) - 2)]), next(seqs)) for lid in upd])
            return env
        return Fam(rels, ref, gen)
    if kind in ("B2", "W8"):
        k, v, w = nm(), nm(), nm()
        a = nm()
        D = distractors(r, nm, max(0, width - 4))
        O, N = nm(), nm()
        sch = [(k, I), (v, I), (w, S), (a, I)] + D
        r.shuffle(sch)
        up = ("union", ("join", "anti", ("rel", O), ("rel", N), (k,), (k,)), ("rel", N))
        o1, o2 = nm(), nm()
        hi, lo = r.choice([("hi", "lo"), ("y", "n"), ("on", "off")])

        def gen(rr, n):
            keys = rr.sample(range(1, 400), n)
            new = rr.sample(keys, max(2, n // 3)) + rr.sample(range(400, 500), 2)

            def row(kk):
                d = {k: kk, v: rr.randint(0, 99), w: rr.choice(["s1", "s2", "s3"]), a: None if rr.random() < 0.4 else rr.randint(0, 99)}
                d.update({x: dval(rr, t) for x, t in D})
                return tuple(d[c] for c, _ in sch)
            return {O: _rel(sch, [row(kk) for kk in keys]), N: _rel(sch, [row(kk) for kk in new])}
        f = Fam({O: sch, N: sch}, None, gen)
        if kind == "B2":
            f.ref_of = lambda c: ("map", up, ((o1, col(k)), (o2, ("branch", ("cmp", "ge", col(v), const(c, I)), const(hi, S), const(lo, S)))))
            f.threshold_col, f.threshold_rel = v, O
        else:
            f.ref = ("map", up, ((o1, col(k)), (o2, coalesce(col(a), col(v)))))
        return f
    if kind == "B3":
        g, c, x, st = nm(), nm(), nm(), nm()
        D = distractors(r, nm, max(0, width - 4))
        rn = nm()
        sch = [(g, S), (c, S), (x, I), (st, S)] + D
        r.shuffle(sch)
        cv = r.sample(["p", "q", "r", "s"], 3)
        og, on = nm(), nm()
        filt = ("filter", ("rel", rn), ("cmp", "ne", col(st), const("void", S)))
        ref = ("map", ("fold", filt, (g,), ((on, "sum", ("branch", ("cmp", "eq", col(c), const(cv[0], S)), col(x), const(0, I))),)), ((og, col(g)), (on, col(on))))

        def gen(rr, n):
            rows = []
            for i in range(n):
                row = {g: "g" + str(i % 3), c: cv[0] if i % 2 == 0 else rr.choice(cv), x: rr.randint(1, 40), st: "void" if rr.random() < 0.3 else rr.choice(["ok", "new"])}
                row.update({d: dval(rr, dt) for d, dt in D})
                rows.append(tuple(row[cc] for cc, _ in sch))
            return {rn: _rel(sch, rows)}
        return Fam({rn: sch}, ref, gen)
    if kind in ("B4", "W3", "W7", "W5"):
        k, s, a, b = nm(), nm(), nm(), nm()
        st, cc, x = nm(), nm(), nm()
        D = distractors(r, nm, max(0, width - 7))
        rn = nm()
        sch = [(k, I), (s, I), (a, I), (b, I), (st, S), (cc, S), (x, I)] + D
        r.shuffle(sch)
        o1, o2 = nm(), nm()
        base = ("rel", rn)
        if kind == "W3":
            base = ("filter", base, ("cmp", "ne", col(st), const("void", S)))
        dd = ("rank", base, (k,), ((col(s), True),), 1)
        f = None
        hi, lo = r.choice([("hi", "lo"), ("y", "n"), ("on", "off")])
        cv = ["p", "q", "r"]

        def gen(rr, n):
            rows, seqs = [], rr.sample(range(1, 900), n)
            keys = [rr.randint(1, max(2, n // 2)) for _ in range(n)]
            for i in range(n):
                row = {k: keys[i], s: seqs[i], a: None if rr.random() < 0.4 else rr.randint(0, 99), b: rr.randint(0, 99),
                       st: "void" if rr.random() < 0.25 else "ok", cc: rr.choice(cv), x: rr.randint(1, 40)}
                row.update({d: dval(rr, dt) for d, dt in D})
                rows.append(tuple(row[c2] for c2, _ in sch))
            return {rn: _rel(sch, rows)}
        f = Fam({rn: sch}, None, gen)
        if kind in ("B4", "W3"):
            f.ref = ("map", dd, ((o1, col(k)), (o2, coalesce(col(a), col(b)))))
        elif kind == "W7":
            f.ref_of = lambda c: ("map", dd, ((o1, col(k)), (o2, ("branch", ("cmp", "ge", col(b), const(c, I)), const(hi, S), const(lo, S)))))
            f.threshold_col, f.threshold_rel = b, rn
        else:
            f.ref = ("map", ("fold", dd, (cc,), ((o2, "sum", col(x)),)), ((o1, col(cc)), (o2, col(o2))))
        return f
    if kind in ("B5",):
        pid, pa, xa = nm(), nm(), nm()
        D1 = distractors(r, nm, max(0, width // 2 - 3))
        sl = [(pid, I), (pa, S), (xa, I)] + D1
        r.shuffle(sl)
        L, R = nm(), nm()
        fk, q = nm(), nm()
        D2 = distractors(r, nm, max(0, width // 2 - 2))
        sr = [(fk, I), (q, I)] + D2
        r.shuffle(sr)
        o1, o2, o3 = nm(), nm(), nm()
        hi, lo = r.choice([("hi", "lo"), ("y", "n"), ("on", "off")])
        agg = ("fold", ("rel", R), (fk,), (("m", "sum", col(q)),))

        def gen(rr, n):
            ids = rr.sample(range(1, 300), max(3, n // 2))
            lrows = []
            for i in ids:
                row = {pid: i, pa: rr.choice(["u", "v"]), xa: rr.randint(0, 99)}
                row.update({d: dval(rr, dt) for d, dt in D1})
                lrows.append(tuple(row[c] for c, _ in sl))
            rrows = []
            for _ in range(n):
                row = {fk: rr.choice(ids[: max(1, len(ids) - 2)]), q: rr.randint(1, 20)}
                row.update({d: dval(rr, dt) for d, dt in D2})
                rrows.append(tuple(row[c] for c, _ in sr))
            return {L: _rel(sl, lrows), R: _rel(sr, rrows)}
        f = Fam({L: sl, R: sr}, None, gen)
        f.ref_of = lambda c: ("map", ("join", "left", ("rel", L), agg, (pid,), (fk,)),
                              ((o1, col(pid)), (o2, coalesce(col("m"), const(0, I))), (o3, ("branch", ("cmp", "ge", col(xa), const(c, I)), const(hi, S), const(lo, S)))))
        f.threshold_col, f.threshold_rel = xa, L
        return f
    if kind in ("B6", "W4", "W6"):
        k, s, pl, a, b = nm(), nm(), nm(), nm(), nm()
        D = distractors(r, nm, max(0, width - 5))
        rn = nm()
        sch = [(k, I), (s, I), (pl, S), (a, I), (b, I)] + D
        r.shuffle(sch)
        ka = r.choice(["a", "b", "c"])
        o1, o2, o3 = nm(), nm(), nm()
        hi, lo = r.choice([("hi", "lo"), ("y", "n"), ("on", "off")])

        def gen(rr, n):
            rows, seqs = [], rr.sample(range(1, 900), n)
            keys = [rr.randint(1, max(2, n // 2)) for _ in range(n)] if kind == "B6" else rr.sample(range(1, 600), n)
            for i in range(n):
                o = {"z": "w"}
                if rr.random() > 0.2:
                    o[ka] = rr.randint(0, 99)
                row = {k: keys[i], s: seqs[i], pl: json.dumps(o), a: None if rr.random() < 0.4 else rr.randint(0, 99), b: rr.randint(0, 99)}
                row.update({d: dval(rr, dt) for d, dt in D})
                rows.append(tuple(row[c] for c, _ in sch))
            return {rn: _rel(sch, rows)}
        f = Fam({rn: sch}, None, gen)
        jx = ("cast", ("json", col(pl), (ka,)), I)
        if kind == "B6":
            f.ref = ("map", ("rank", ("rel", rn), (k,), ((col(s), True),), 1), ((o1, col(k)), (o2, jx)))
        elif kind == "W6":
            f.ref = ("map", ("rel", rn), ((o1, col(k)), (o2, jx), (o3, coalesce(col(a), col(b)))))
        else:
            f.ref_of = lambda c: ("map", ("rel", rn), ((o1, col(k)), (o2, jx), (o3, ("branch", ("cmp", "ge", col(b), const(c, I)), const(hi, S), const(lo, S)))))
            f.threshold_col, f.threshold_rel = b, rn
        return f
    if kind == "W1":
        k, s, v = nm(), nm(), nm()
        D = distractors(r, nm, max(0, width - 3))
        O, N = nm(), nm()
        sch = [(k, I), (s, I), (v, I)] + D
        r.shuffle(sch)
        ref = ("union", ("join", "anti", ("rel", O), ("rank", ("rel", N), (k,), ((col(s), True),), 1), (k,), (k,)), ("rank", ("rel", N), (k,), ((col(s), True),), 1))

        def gen(rr, n):
            keys = rr.sample(range(1, 400), n)
            seqs = iter(rr.sample(range(1, 2000), 4 * n))

            def row(kk):
                d = {k: kk, s: next(seqs), v: rr.randint(0, 99)}
                d.update({x: dval(rr, t) for x, t in D})
                return tuple(d[c] for c, _ in sch)
            new = rr.sample(keys, max(2, n // 3))
            new = new + rr.sample(new, max(1, len(new) // 2)) + rr.sample(range(400, 500), 2)
            return {O: _rel(sch, [row(kk) for kk in keys]), N: _rel(sch, [row(kk) for kk in new])}
        return Fam({O: sch, N: sch}, ref, gen)
    raise ValueError(kind)


# ------------------------------------------------------------------ task assembly
def build(kind, seed, pool="base", width=None):
    """-> (learner_task, admin, hidden). All randomness: rng10c((seed, 0, k)) numeric tuples."""
    r = rng10c(seed, 0, 1)
    nm = Namer(r, pool)
    if kind in SOURCE_FAM:
        fam = SOURCE_FAM[kind](r, nm, width or r.randint(5, 8))
    else:
        fam = compose(kind, r, nm, width or r.randint(10, 14))
    envs = {b: fam.gen(rng10c(seed, 1 + i, 2), n) for i, (b, n) in enumerate(BATCHES)}
    ref = fam.ref
    if ref is None:
        vis = [v for b in ("vis_a", "vis_b") for v in (rr[fam.threshold_col] for rr in _as_dicts(envs[b][fam.threshold_rel]))]
        qs = quantiles(vis)
        ref = fam.ref_of(qs[len(qs) // 2] if qs else 50)
    expected = {b: C.evaluate(ref, envs[b]) for b in envs}
    if any(v is C.ERR for v in expected.values()):
        raise RuntimeError("reference evaluation error")
    out_schema = C.rel_schema(ref, {k: v.schema() for k, v in envs["vis_a"].items()})
    tid = f"T{seed}"
    learner = dict(id=tid, inputs={b: envs[b] for b in ("vis_a", "vis_b")}, expected={b: expected[b] for b in ("vis_a", "vis_b")}, out_schema=out_schema)
    admin = dict(valid=(envs["valid"], expected["valid"]), evidence=(envs["evidence"], expected["evidence"]))
    hidden = dict(kind=kind, seed=seed, ref=ref, hid=[(envs[b], expected[b]) for b in ("hid1", "hid2")], width=sum(len(s) for s in fam.schemas.values()))
    return learner, admin, hidden


def _as_dicts(R):
    return [dict(zip(R.cols, r)) for r in R.rows]
