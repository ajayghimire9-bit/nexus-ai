"""Phase 12B task generator for Fresh_Phase12B_24 (NOT LOCKED; GENERATOR INTERNALS: the reference program computes expected outputs and
answers the budgeted reference interface - `generator-supervised interaction` - and never reaches the learner).

SIX MECHANISMS NOT USED IN PHASE 12 (neither its Suite 1 nor its development) and not the Phase 11 threshold / min-vs-latest:
  N1 sum_unit       per-group SUM of a quantity; visible quantities are all 1 (SUM = COUNT(*) = COUNT(col) visibly)
  N2 grain_single   per-parent SUM of child amounts joined to parents; every visible parent has ONE child (SUM = MAX = MIN visibly)
  N4 union_upsert   next state of two sources = pure upsert; visible new keys never overlap old keys (UNION ALL = upsert visibly)
  N6 dedup_need     latest row per key; every visible key occurs once (the rank is an invisible no-op visibly)
  N7 group_twin     per-group SUM grouped by g; a twin column h corresponds one-to-one with g on visible rows
  N8 hidden_filter  rows whose status is 'ok' only; every visible row has status 'ok' (the filter is invisible visibly)
Visible batches never contain the deciding case; hidden batches always do; the two static evidence batches (Fixed arm) contain it with
probability 1/2 each. Instances 0-1 plain, 2-3 multi-fault compositions (N1 N2 N7: input from the upsert of two sources; N4: plus an
invisible status filter; N6: the rank over an upsert source; N8: the filter over a left lookup join).
Learner view: anonymous id, two visible batches, output schema, declared contracts (unique / not-null columns)."""
from __future__ import annotations

from nexus.de_phase10c.rng10c import rng as rng10c
from nexus.de_phase11 import core11 as C
from nexus.de_phase11.tasks11 import Namer, distractors, dval

I, S = C.INT, C.STR
MECHS = ("N1", "N2", "N4", "N6", "N7", "N8")
SIZES = (("vis_a", 8), ("vis_b", 8), ("ev1", 8), ("ev2", 8), ("hid1", 16), ("hid2", 16))


def col(n):
    return ("col", n)


def _rel(schema, rows):
    return C.Rel([n for n, _ in schema], [t for _, t in schema], rows)


def _upsert(O, N, k):
    return ("union", ("join", "anti", ("rel", O), ("rel", N), (k,), (k,)), ("rel", N))


def family(mech, composed, r, nm):
    if mech in ("N2", "N8"):
        pid, pa, st, fk, q, attr = nm(), nm(), nm(), nm(), nm(), nm()
        D1, D2 = distractors(r, nm, 2), distractors(r, nm, 2)
        L, R = nm(), nm()
        sl = [(pid, I), (pa, S), (st, S)] + D1
        sr = [(fk, I), (q, I), (attr, S)] + D2
        r.shuffle(sl)
        r.shuffle(sr)
        o1, o2 = nm(), nm()
        if mech == "N2":
            base = ("filter", ("rel", L), ("cmp", "eq", col(st), ("const", "ok", S))) if composed else ("rel", L)
            ref = ("map", ("join", "inner", base, ("fold", ("rel", R), (fk,), (("m", "sum", col(q)),)), (pid,), (fk,)), ((o1, col(pid)), (o2, col("m"))))
        else:
            j = ("join", "left", ("rel", L), ("rel", R), (pid,), (fk,)) if composed else ("rel", L)
            ref = ("map", ("filter", j, ("cmp", "eq", col(st), ("const", "ok", S))), ((o1, col(pid)), (o2, col(attr if composed else pa))))
        contracts = {L: dict(unique=[pid], not_null=[pid, pa, st]), R: dict(unique=[fk] if mech == "N8" else [], not_null=[fk, q, attr])}

        def gen(rr, n, edge):
            ids = rr.sample(range(1, 300), max(4, n // 2))
            lrows = []
            for i in ids:
                status = "ok" if (mech == "N8" and not edge) else ("ok" if rr.random() < 0.7 else "hold")
                if mech == "N2" and not composed:
                    status = "ok"
                row = {pid: i, pa: rr.choice(["u", "v", "w"]), st: status}
                row.update({d: dval(rr, t) for d, t in D1})
                lrows.append(tuple(row[c] for c, _ in sl))
            if mech == "N8" and edge and all(x[[c for c, _ in sl].index(st)] == "ok" for x in lrows):
                i0 = [c for c, _ in sl].index(st)
                lrows[0] = lrows[0][:i0] + ("hold",) + lrows[0][i0 + 1:]
            rrows = []
            for p_ in ids:
                k = 1 if (mech == "N8" or not edge) else rr.choice([1, 2, 3])
                for _ in range(k):
                    row = {fk: p_, q: rr.randint(1, 30), attr: rr.choice(["a1", "b2", "c3"])}
                    row.update({d: dval(rr, t) for d, t in D2})
                    rrows.append(tuple(row[c] for c, _ in sr))
            if mech == "N2" and edge and len(rrows) == len(ids):
                rrows.append(rrows[0][:])
            return {L: _rel(sl, lrows), R: _rel(sr, rrows)}
        return {L: sl, R: sr}, contracts, ref, gen
    k, g, h, s, q, st, v = nm(), nm(), nm(), nm(), nm(), nm(), nm()
    D = distractors(r, nm, 2)
    sch = [(k, I), (g, S), (h, S), (s, I), (q, I), (st, S), (v, I)] + D
    r.shuffle(sch)
    rels = [nm(), nm()] if (composed or mech == "N4") else [nm()]
    src = _upsert(rels[0], rels[1], k) if len(rels) == 2 else ("rel", rels[0])
    o1, o2 = nm(), nm()
    if mech == "N1":
        ref = ("map", ("fold", src, (g,), ((o2, "sum", col(q)),)), ((o1, col(g)), (o2, col(o2))))
    elif mech == "N7":
        ref = ("map", ("fold", src, (g,), ((o2, "sum", col(v)),)), ((o1, col(g)), (o2, col(o2))))
    elif mech == "N4":
        base = ("filter", src, ("cmp", "eq", col(st), ("const", "ok", S))) if composed else src
        ref = ("map", base, ((o1, col(k)), (o2, col(v))))
    else:                                                          # N6: latest row per key (rank by s)
        ref = ("map", ("rank", src, (k,), ((col(s), True),), 1), ((o1, col(k)), (o2, col(v))))
    contracts = {rn: dict(unique=[] if mech == "N6" else [k], not_null=[k, g, h, s, q, st, v]) for rn in rels}
    hmap = {"p": "x1", "q": "x2", "r": "x3"}

    def gen(rr, n, edge):
        def row(kk, sv):
            gv = rr.choice(["p", "q", "r"])
            hv = hmap[gv] if not (edge and mech == "N7" and rr.random() < 0.4) else rr.choice(["x1", "x2", "x3"])
            d = {k: kk, g: gv, h: hv, s: sv, q: 1 if (mech == "N1" and not edge) else rr.randint(1, 5), st: "ok" if (not edge or mech != "N4" or not composed or rr.random() < 0.7) else "hold",
                 v: rr.randint(0, 99)}
            d.update({x: dval(rr, t) for x, t in D})
            return tuple(d[c] for c, _ in sch)
        keys = rr.sample(range(1, 400), n)
        seqs = iter(rr.sample(range(1, 2000), 4 * n))
        base_rows = [row(kk, next(seqs)) for kk in keys]
        if mech == "N6" and edge:
            base_rows += [row(kk, next(seqs)) for kk in rr.sample(keys, max(1, n // 3))]
        if mech == "N1" and edge and all(x[[c for c, _ in sch].index(q)] == 1 for x in base_rows):
            i0 = [c for c, _ in sch].index(q)
            base_rows[0] = base_rows[0][:i0] + (3,) + base_rows[0][i0 + 1:]
        env = {rels[0]: _rel(sch, base_rows)}
        if len(rels) == 2:
            if edge or mech != "N4":
                newk = rr.sample(keys, max(2, n // 3)) + rr.sample(range(400, 500), 2)
            else:
                newk = rr.sample(range(400, 500), max(3, n // 3))      # N4 visible: no overlap with old keys
            if mech == "N4" and not edge:
                newk = rr.sample(range(400, 500), max(3, n // 3))
            env[rels[1]] = _rel(sch, [row(kk, next(seqs)) for kk in newk])
        return env
    return {rn: sch for rn in rels}, contracts, ref, gen


def build(mech, inst, seed, pool="heldout"):
    r = rng10c(seed, 0, 1)
    nm = Namer(r, pool)
    composed = inst >= 2
    schemas, contracts, ref, gen = family(mech, composed, r, nm)
    envs = {}
    for i, (b, n) in enumerate(SIZES):
        rr = rng10c(seed, 1 + i, 2)
        edge = b.startswith("hid") or (b.startswith("ev") and rr.random() < 0.5)
        envs[b] = gen(rr, n, edge)
    exp = {b: C.evaluate(ref, envs[b]) for b in envs}
    if any(v is C.ERR for v in exp.values()):
        raise RuntimeError("reference evaluation error")
    out_schema = C.rel_schema(ref, {k: v.schema() for k, v in envs["vis_a"].items()})
    learner = dict(id=f"Z{seed}", inputs={b: envs[b] for b in ("vis_a", "vis_b")}, expected={b: exp[b] for b in ("vis_a", "vis_b")}, out_schema=out_schema,
                   contracts=contracts)
    admin = dict(static=[(envs["ev1"], exp["ev1"]), (envs["ev2"], exp["ev2"])], oracle=lambda env, ref=ref: C.evaluate(ref, env))
    hidden = dict(kind=f"{mech}{'c' if composed else ''}", mech=mech, composed=composed, seed=seed, ref=ref, hid=[(envs[b], exp[b]) for b in ("hid1", "hid2")])
    return learner, admin, hidden
