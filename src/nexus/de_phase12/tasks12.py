"""Phase 12 task generator for Suite 1 (Fresh_Ambiguous_Compositions_24; NOT LOCKED). GENERATOR INTERNALS: the reference program is
used to compute expected outputs and to answer the budgeted reference interface (`generator-supervised interaction`); it never reaches
the learner. Learner view: anonymous id, visible inputs / outputs (2 batches), output schema and DECLARED CONTRACTS (per relation: unique
columns, not-null columns) that define admissible inputs.

SIX AMBIGUITY MECHANISMS, none of them the Phase 11 threshold constant or min-vs-latest (all references are reachable by the synthesizer):
  M1 join_default    parents left-joined to a per-parent SUM of child quantities with a default of 0       (unmatched parents)
  M2 dupkey_semi     parents that have at least one child (semi join)                                       (several children per parent)
  M3 null_default    a value column with a default of 0 for NULL                                            (NULL values)
  M4 count_column    per-group COUNT of a nullable column                                                   (NULL values in the group)
  M5 window_twin     latest row per key by a sequence column that has a twin column agreeing on visible data (ties / disagreeing twins)
  M6 lookup_left     a left lookup join keeping parents without a match                                     (unmatched parents)
The VISIBLE batches never contain the deciding case, so several programs fit them; the HIDDEN batches always contain it; the two STATIC
evidence batches (the Fixed arm's predefined examples) are drawn from the natural data distribution and contain it with probability 1/2
each. Instances 0-1 of each mechanism are plain; instances 2-3 are held-out multi-operation compositions (M1 M2 M6: an upstream filter of
the parents on a status value; M3 M4 M5: the input is the pure next-state upsert of two sources)."""
from __future__ import annotations

from nexus.de_phase10c.rng10c import rng as rng10c
from nexus.de_phase11 import core11 as C
from nexus.de_phase11.tasks11 import NAMES, Namer, distractors, dval, coalesce

I, S = C.INT, C.STR
MECHS = ("M1", "M2", "M3", "M4", "M5", "M6")
SIZES = (("vis_a", 8), ("vis_b", 8), ("ev1", 8), ("ev2", 8), ("hid1", 16), ("hid2", 16))


def col(n):
    return ("col", n)


def _rel(schema, rows):
    return C.Rel([n for n, _ in schema], [t for _, t in schema], rows)


def _upsert(O, N, k):
    return ("union", ("join", "anti", ("rel", O), ("rel", N), (k,), (k,)), ("rel", N))


def family(mech, composed, r, nm):
    """-> (schemas, contracts, reference program, gen(rr, n, edge: bool) -> env)."""
    if mech in ("M1", "M2", "M6"):
        pid, pa, st, fk, q, attr = nm(), nm(), nm(), nm(), nm(), nm()
        D1, D2 = distractors(r, nm, 2), distractors(r, nm, 2)
        L, R = nm(), nm()
        sl = [(pid, I), (pa, S), (st, S)] + D1
        sr = [(fk, I), (q, I), (attr, S)] + D2
        r.shuffle(sl)
        r.shuffle(sr)
        base = ("filter", ("rel", L), ("cmp", "eq", col(st), ("const", "ok", S))) if composed else ("rel", L)
        o1, o2 = nm(), nm()
        if mech == "M1":
            ref = ("map", ("join", "left", base, ("fold", ("rel", R), (fk,), (("m", "sum", col(q)),)), (pid,), (fk,)),
                   ((o1, col(pid)), (o2, coalesce(col("m"), ("const", 0, I)))))
        elif mech == "M2":
            ref = ("map", ("join", "semi", base, ("rel", R), (pid,), (fk,)), ((o1, col(pid)), (o2, col(pa))))
        else:
            ref = ("map", ("join", "left", base, ("rel", R), (pid,), (fk,)), ((o1, col(pid)), (o2, col(attr))))
        contracts = {L: dict(unique=[pid], not_null=[pid, pa, st]), R: dict(unique=[fk] if mech == "M6" else [], not_null=[fk, q, attr])}

        def gen(rr, n, edge):
            ids = rr.sample(range(1, 300), max(4, n // 2))
            lrows = []
            for i in ids:
                row = {pid: i, pa: rr.choice(["u", "v", "w"]), st: "ok" if (not composed or rr.random() < 0.7) else "hold"}
                row.update({d: dval(rr, t) for d, t in D1})
                lrows.append(tuple(row[c] for c, _ in sl))
            ok_ids = [x[[c for c, _ in sl].index(pid)] for x in lrows]
            rrows = []
            if mech == "M6":                                       # at most one child per parent (fk unique); edge: some parents unmatched
                kids = ok_ids if not edge else ok_ids[: max(1, len(ok_ids) - 2)]
                for k in kids:
                    row = {fk: k, q: rr.randint(1, 20), attr: rr.choice(["a1", "b2", "c3"])}
                    row.update({d: dval(rr, t) for d, t in D2})
                    rrows.append(tuple(row[c] for c, _ in sr))
            else:
                if mech == "M1":
                    parents = list(ok_ids) if not edge else ok_ids[: max(1, len(ok_ids) - 2)]
                    per = [rr.choice([1, 2]) for _ in parents]
                else:                                              # M2: visible exactly one child each; edge: several for some
                    parents = list(ok_ids)
                    per = [1 for _ in parents] if not edge else [rr.choice([1, 2, 3]) for _ in parents]
                    if edge and max(per) == 1:
                        per[0] = 2
                for p_, k in zip(parents, per):
                    for _ in range(k):
                        row = {fk: p_, q: rr.randint(1, 20), attr: rr.choice(["a1", "b2", "c3"])}
                        row.update({d: dval(rr, t) for d, t in D2})
                        rrows.append(tuple(row[c] for c, _ in sr))
            return {L: _rel(sl, lrows), R: _rel(sr, rrows)}
        return {L: sl, R: sr}, contracts, ref, gen
    k, x, g, s, t, v = nm(), nm(), nm(), nm(), nm(), nm()
    D = distractors(r, nm, 2)
    sch = [(k, I), (x, I), (g, S), (s, I), (t, I), (v, I)] + D
    r.shuffle(sch)
    rels = [nm()] if not composed else [nm(), nm()]
    src = ("rel", rels[0]) if not composed else _upsert(rels[0], rels[1], k)
    o1, o2 = nm(), nm()
    if mech == "M3":
        ref = ("map", src, ((o1, col(k)), (o2, coalesce(col(x), ("const", 0, I)))))
        contracts = {rn: dict(unique=[k], not_null=[k, g, s, t, v]) for rn in rels}
    elif mech == "M4":
        ref = ("map", ("fold", src, (g,), ((o2, "count", col(x)),)), ((o1, col(g)), (o2, col(o2))))
        contracts = {rn: dict(unique=[k], not_null=[k, g, s, t, v]) for rn in rels}
    else:                                                          # M5: latest per key by s (twin t); composed: upsert source
        ref = ("map", ("rank", src, (g,), ((col(s), True),), 1), ((o1, col(g)), (o2, col(v))))
        contracts = {rn: dict(unique=[k], not_null=[k, g, s, t, v, x]) for rn in rels}

    def gen(rr, n, edge):
        def rows_for(keys, seq0):
            out = []
            for j, kk in enumerate(keys):
                sv = seq0 + 3 * j + rr.randint(0, 1)
                row = {k: kk, x: None if (edge and mech in ("M3", "M4") and rr.random() < 0.4) else rr.randint(0, 50), g: rr.choice(["p", "q", "r"]),
                       s: sv, t: 1000 + 2 * sv, v: rr.randint(0, 99)}
                if mech == "M5" and edge and rr.random() < 0.4:
                    row[t] = 3000 - 2 * sv                         # the twin disagrees on some rows
                row.update({d: dval(rr, tt) for d, tt in D})
                out.append(tuple(row[c] for c, _ in sch))
            if edge and mech in ("M3", "M4") and not any(r_[[c for c, _ in sch].index(x)] is None for r_ in out):
                i0 = [c for c, _ in sch].index(x)
                out[0] = out[0][:i0] + (None,) + out[0][i0 + 1:]
            return out
        keys = rr.sample(range(1, 400), n)
        env = {rels[0]: _rel(sch, rows_for(keys, 10))}
        if composed:
            newk = rr.sample(keys, max(2, n // 3)) + rr.sample(range(400, 500), 2)
            env[rels[1]] = _rel(sch, rows_for(newk, 200))
        return env
    return {rn: sch for rn in rels}, contracts, ref, gen


def build(mech, inst, seed, pool="heldout"):
    """-> (learner, admin, hidden). admin: static evidence batches ev1 / ev2 (Fixed arm) and the reference oracle; hidden: hid1 / hid2."""
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
    learner = dict(id=f"Q{seed}", inputs={b: envs[b] for b in ("vis_a", "vis_b")}, expected={b: exp[b] for b in ("vis_a", "vis_b")}, out_schema=out_schema,
                   contracts=contracts)
    admin = dict(static=[(envs["ev1"], exp["ev1"]), (envs["ev2"], exp["ev2"])], oracle=lambda env, ref=ref: C.evaluate(ref, env))
    hidden = dict(kind=f"{mech}{'c' if composed else ''}", mech=mech, composed=composed, seed=seed, ref=ref, hid=[(envs[b], exp[b]) for b in ("hid1", "hid2")])
    return learner, admin, hidden
