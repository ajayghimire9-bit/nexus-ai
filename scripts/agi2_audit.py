"""Phase 2 Stage 1: constructive expressivity & reachability audit of all 24 Phase 1 families (NOT LOCKED; agi2/dev).
  python scripts/agi2_audit.py [LAM_MAX_RAISED]     -> artifacts/agi2_audit.json
For every family and several dev instances (L1), a HAND-WRITTEN reference program (audit fixture only; never given to
any learner) is built from the task's mechanism descriptor and checked:
  expressible  type-checks and agrees with the independent Python reference on every train, hidden and exhaustive input
  metrics      nodes, depth, pi0 cost, largest lambda-body cost, primitives / constants used
  bounds       pi0 cost <= MAX_COST (18) and lambda-body cost <= lam_max (pi0 6; raised bound LAM_MAX_RAISED)
  reach_focus  the enumerator restricted to the reference's primitives (the prior a perfect pi / L would give) finds a
               consistent hypothesis that passes independent verification, within 5 s CPU
  reach_full   the full-grammar enumerator in 0.6 s CPU: Phase 1 substrate (lam_max 6) vs Phase 2 (lazy lagged lambdas)
Not-expressible families are listed with the reason. C5 / C6 / E5 / E6 are NOT audited (untouched)."""
import json, re, sys, time
from pathlib import Path
from nexus.campaign2 import substrate as S, state as ST, seeds as SD
from nexus.campaign2.worlds2 import make_task2
from nexus.campaign.worlds import verify
from nexus.campaign.worlds import world_f_programs as WF
ROOT = Path(__file__).resolve().parents[1]


def P(n, *a):
    return ("p", n) + a


X0, X1, A0, A1 = ("x", 0), ("x", 1), ("a", 0), ("a", 1)


def C(v):
    """A constant; values > 5 are built from available constants (the cheapest sum of 5s and a remainder)."""
    if v <= 5:
        return ("c", v)
    out = ("c", 5)
    v -= 5
    while v > 5:
        out, v = P("add", out, ("c", 5)), v - 5
    return P("add", out, ("c", v))


def L(ctx, b):
    return ("lam", ctx, b)


def num(d, key):
    m = re.search(key + r"=?(-?\d+)", d)
    return int(m.group(1)) if m else None


def nth(r, k):
    return P("nth", r, C(k))


def pred(s):
    op, k, c = re.match(r"(lt|ge|eq)\(f(\d+),(\d+)\)", s).groups()
    k, c = int(k), int(c)
    return {"lt": P("lt", nth(A0, k), C(c)), "ge": P("not", P("lt", nth(A0, k), C(c))), "eq": P("eq", nth(A0, k), C(c))}[op]


def build(t):
    d, w0 = t.descr, len(t.train_x[0][0][0]) if t.mech.sig[0] == "L" and t.train_x[0][0] else 0
    f = t.family
    if f == "A1":
        ps = re.findall(r"(?:lt|ge|eq)\(f\d+,\d+\)", d)
        body = pred(ps[0]) if len(ps) == 1 else P("and", pred(ps[0]), pred(ps[1]))
        return P("filterr", L("l", body), X0), None
    if f == "A2":
        k = num(d, "k=f")
        k2 = re.search(r"\*10\+f(\d+)", d)
        key = nth(A0, k) if not k2 else P("add", P("mul", nth(A0, k), C(10)), nth(A0, int(k2.group(1))))
        val = C(1) if "count" in d else nth(A0, num(d, "sum f"))
        return P("groupsum", L("l", key), L("l", val), X0), None
    if f == "A3":
        i, j = map(int, re.search(r"f(\d+) .*T2\.f(\d+)", d.replace("==", " ")).groups())
        if d.startswith("semijoin"):
            return P("filterr", L("l", P("mem", nth(A0, i), P("col", X1, C(j)))), X0), None
        return P("filterr", L("l", P("eq", nth(A0, i), nth(A0, w0 + j))), P("prod", X0, X1)), \
            "join: the prod primitive is invalid above 40 row pairs, the reference truncates"
    if f == "A4":
        if d.startswith("project"):
            a, b = map(int, re.findall(r"f(\d+)", d))
            return P("mapr", L("l", P("list2", nth(A0, a), nth(A0, b))), X0), None
        k, c, a, b = map(int, re.match(r"route\[f(\d+)<(\d+)\?\(f(\d+),f(\d+)\)", d).groups())
        return P("mapr", L("l", P("ite_l", P("lt", nth(A0, k), C(c)), P("list2", nth(A0, a), nth(A0, b)),
                                   P("list2", nth(A0, b), nth(A0, a)))), X0), None
    if f == "B1":
        v = re.search(r"\[(\w+)\]", d).group(1)
        if v in ("runsum", "runmax"):
            return P("scan", L("ii", P("add" if v == "runsum" else "max2", A0, A1)), C(0), X0), None
        return P("zipw", L("ii", P("sub" if v == "rundiff" else "add", A0, A1)), X0, P("cons", C(0), X0)), None
    if f == "B2":
        if d.startswith("latch"):
            c = num(d, "set>")
            return P("scan", L("ii", P("ite_i", P("lt", C(c), A1), C(1), A0)), C(0), X0), None
        hi, lo = num(d, "on>="), num(d, "off<=")
        return P("scan", L("ii", P("ite_i", P("lt", C(hi - 1), A1), C(1), P("ite_i", P("lt", A1, C(lo + 1)), C(0), A0))),
                 C(0), X0), None
    if f == "B3":
        if d.startswith("since"):
            c = num(d, "==")
            return P("scan", L("ii", P("ite_i", P("eq", A1, C(c)), C(0), P("add", A0, C(1)))), C(0), X0), None
        c, k = num(d, "trig=="), num(d, "k=")
        return P("scan", L("ii", P("ite_i", P("and", P("eq", A1, C(c)), P("eq", A0, C(0))), C(k),
                                    P("max2", P("sub", A0, C(1)), C(0)))), C(0), X0), None
    if f == "B4":
        k = num(d, "kind=")
        contrib = lambda inner: P("mapri", L("l", inner), X0)                             # noqa: E731
        add = P("ite_i", P("eq", P("head", A0), C(k)), P("last", A0), C(0))
        tot = P("scan", L("ii", P("add", A0, A1)), C(0), contrib(add))
        if "total" in d:
            return tot, None
        if "delayed" in d:
            return P("take", P("cons", C(0), tot), P("lenL", X0)), None
        rk = num(d, "reset=")
        enc = P("ite_i", P("eq", P("head", A0), C(rk)), P("sub", C(0), C(1)), add)
        return P("scan", L("ii", P("ite_i", P("lt", A1, C(0)), C(0), P("add", A0, A1))), C(0), contrib(enc)), None
    if f == "C1":
        v = re.search(r"\[(\w+)\]", d).group(1)
        pos = L("i", P("lt", C(0), A0))
        if v == "occupied_rows":
            return P("count", pos, P("mapri", L("l", P("maxl", A0)), X0)), None
        if v == "row_counts":
            return P("mapri", L("l", P("count", pos, A0)), X0), None
        return None, "connected components need 2-D flood fill: no adjacency / visited-set construction over grids"
    if f == "C2":
        v = re.search(r"\[(\w+)", d).group(1)
        if v == "recolour":
            a, b = map(int, re.search(r"(\d)->(\d)", d).groups())
            return P("mapr", L("l", P("map", L("i", P("ite_i", P("eq", A0, C(a)), C(b), A0)), A0)), X0), None
        return {"reflect_lr": P("mapr", L("l", P("rev", A0)), X0), "reflect_ud": P("revL", X0), "transpose": P("transpose", X0),
                "rot90": P("mapr", L("l", P("rev", A0)), P("transpose", X0)),
                "scale2": P("repeatL", P("mapr", L("l", P("repeat", A0, C(2))), X0), C(2))}[v], None
    if f == "C3":
        v = re.search(r"\[(\w+)\]", d).group(1)
        fill = L("ii", P("ite_i", P("lt", A0, C(0)), P("max2", A1, C(0)), A0))
        if v == "lr":
            return P("mapr", L("l", P("zipw", fill, A0, P("rev", A0))), X0), None
        if v == "ud":
            return P("transpose", P("mapr", L("l", P("zipw", fill, A0, P("rev", A0))), P("transpose", X0))), None
        return P("mapr", L("l", P("map", L("i", P("max2", A0, C(0))), A0)), X0), None
    if f == "C4":
        v = re.search(r"\[(\w+)\]", d).group(1)
        zeros, nz = L("i", P("lt", A0, C(1))), L("i", P("lt", C(0), A0))
        down = L("l", P("cat", P("filter", zeros, A0), P("filter", nz, A0)))
        right = L("l", P("take", P("cons", C(0), A0), P("len", A0)))
        return {"gravity_down": P("transpose", P("mapr", down, P("transpose", X0))),
                "gravity_left": P("mapr", L("l", P("cat", P("filter", nz, A0), P("filter", zeros, A0))), X0),
                "shift_right": P("mapr", right, X0),
                "shift_down": P("transpose", P("mapr", right, P("transpose", X0)))}[v], \
            ("transpose pads ragged / empty grids" if v == "shift_down" else None)
    if f == "D1":
        k = num(d, "k=")
        return P("iterate", L("l", P("uniq", P("cat", A0, P("gather", X0, A0)))), P("list1", X1), C(k)), None
    if f == "D2":
        new = P("filter", L("i", P("and", P("subset", P("row", X0, A0), X1), P("not", P("mem", A0, X1)))), P("range", P("lenL", X0)))
        return (new if "new" in d else P("uniq", P("cat", X1, new))), None
    if f == "D3":
        B = num(d, "B=")
        pre = P("scan", L("ii", P("add", A0, A1)), C(0), X0)
        ok = L("i", P("lt", A0, C(B + 1)))
        if "steps" in d:
            return P("count", ok, pre), None
        return P("sub", C(B), P("last", P("filter", ok, pre))), None
    if f == "D4":
        st = num(d, "stages=")
        pts = [P("nth", X0, C(i)) for i in range(1, st + 3)]

        def seg(a, b):
            return P("repeat", P("list1", P("ite_i", P("lt", a, b), C(1), C(2))), P("max2", P("sub", b, a), P("sub", a, b)))
        out = seg(pts[0], pts[1])
        for i in range(1, len(pts) - 1):
            out = P("cat", out, seg(pts[i], pts[i + 1]))
        return out, None
    if f == "E1":
        a = int(re.search(r"X=c(\d)", d).group(1))
        X = P("coalesce", P("nth", X0, C(0)), P("nth", X1, C(a)))
        src = X if "Y<-X" in d else P("nth", X1, C(int(re.search(r"Y<-c(\d)", d).group(1))))
        return P("coalesce", P("nth", X0, C(1)), src), None
    if f == "E2":
        v, j = re.search(r"Y=(\w+)\(X,c(\d)\)", d).groups()
        X = P("coalesce", P("nth", X0, C(0)), P("nth", X1, C(0)))
        c = P("nth", X1, C(int(j)))
        g = {"add": P("mod", P("add", X, c), C(4)), "mul": P("mod", P("mul", X, c), C(4)), "max": P("max2", X, c), "copy": X}[v]
        return P("coalesce", P("nth", X0, C(1)), g), None
    if f == "E3":
        lag = num(d, "=")
        Xs = P("zipw", L("ii", P("coalesce", A0, A1)), X0, X1)
        pad = P("scan", L("ii", P("add", A0, A1)), C(0), Xs) if "acc" in d else Xs
        for _ in range(lag):
            pad = P("cons", C(0), pad)
        return P("take", pad, P("len", X0)), None
    if f == "E4":
        m, j = int(re.search(r"\((\d)a", d).group(1)), int(re.search(r"\+c(\d)\)", d).group(1))
        diff = P("sub", P("nth", X0, C(3)), P("nth", X0, C(j)))
        if "+c2" in d:
            diff = P("sub", diff, P("nth", X0, C(2)))
        return P("mod", P("mul", diff, C(m)) if m != 1 else diff, C(4)), None
    if f in ("F1", "F2", "F3", "F4"):
        return None, "intended"
    raise KeyError(f)


def cost(n, costs):
    t = n[0]
    if t in ("x", "a"):
        return costs.get(t, 1)
    if t == "c":
        return costs.get(f"c:{n[1]}", 1 if n[1] <= 2 else 2)
    if t == "lam":
        return cost(n[2], costs)
    return costs.get(n[1], 2) + sum(cost(c, costs) for c in n[2:])


def lam_costs(n, costs):
    out = []
    for m in S.nodes(n):
        if m[0] == "lam":
            out.append(cost(m[2], costs))
    return out


def depth(n):
    if n[0] == "lam":
        return depth(n[2])
    if n[0] == "p":
        return 1 + max((depth(c) for c in n[2:]), default=0)
    return 1


def reach(t, ast, prims, cap, mod=S, lam_max=99, max_cost=30):
    """Run the enumerator exactly as the agent does: labelled training examples plus 8 unlabelled interface probes as
    contexts (observational-equivalence over both), consistency on the labels; report the first hypothesis that passes
    independent verification. mod = substrate module (campaign2 = Phase 2 lazy lambdas; campaign = Phase 1, lam_max 6)."""
    import random
    view = t.view()
    rng = random.Random(f"probe|{t.tid}")
    xs = [x for x, _ in view.train] + [view.sample(rng) for _ in range(8)]
    labels = [y for _, y in view.train]
    n = len(labels)
    consts = tuple(sorted({0, 1, 2, 3, 4, 5} | {m[1] for m in S.nodes(ast) if m[0] == "c"}))
    srch = mod.Search(xs, view.sig, view.out, ST.pi0()["costs"], lambda v: all(view.ok(x, y, z) for x, y, z in zip(xs[:n], labels, v[:n])),
                      consts=consts, deadline=time.process_time() + cap, lam_max=lam_max, prims=prims)
    c0, lvl, found = time.process_time(), 0, None
    try:
        for c in srch.levels(max_cost):
            lvl = c
            for _, h, _ in srch.hyps:
                g = mod.compile_ast(h)
                if verify(t, lambda x: g(tuple(x), (), ()))["ok"]:
                    found = (c, mod.to_src(h), round(time.process_time() - c0, 3))
                    break
            if found:
                break
    except mod.Deadline:
        pass
    return dict(found=found, level_completed=lvl, cpu=round(time.process_time() - c0, 3), n_cands=srch.n_cands)


def main(raised="10"):
    raised = int(raised)
    costs = ST.pi0()["costs"]
    rows = []
    k = 0
    for w, fams in (("A", "A1 A2 A3 A4"), ("B", "B1 B2 B3 B4"), ("C", "C1 C2 C3 C4"), ("D", "D1 D2 D3 D4"),
                    ("E", "E1 E2 E3 E4"), ("F", "F1 F2 F3 F4")):
        for f in fams.split():
            for j in range(3):
                s = SD.RANGES[("agi2", "dev")].start + 2 * k     # even seeds: World F keeps its draft protocol here
                k += 1
                role = SD.role_of(w, f)
                t = make_task2(w, f, 1, s, role, SD.partners_for(w, f, role))
                ast, note = build(t)
                if note == "intended":
                    import random
                    _, ast = WF.intended(f, random.Random(0))
                    # rebuild the intended program of THIS task: the generator draws the variant first from its rng
                    for att in range(40):
                        rng = random.Random(f"agi|{w}|{f}|L1|{s}|{att}")
                        _, ast, dd = WF.GEN[f](rng)
                        if dd == t.descr:
                            break
                    note = None
                row = dict(tid=t.tid, descr=t.descr, note=note)
                if ast is None:
                    row.update(expressible=False)
                    rows.append(row)
                    continue
                try:
                    S.check_types(ast, t.mech.sig)
                    g = S.compile_ast(ast)
                    v = verify(t, lambda x: g(tuple(x), (), ()))
                    tr = all(g(tuple(x), (), ()) == t.ref(x) for x in t.train_x) if t.mech.protocol == "io" else True
                    ok = v["ok"] and tr
                except TypeError as e:
                    ok, v = False, dict(error=str(e))
                prims = sorted({m[1] for m in S.nodes(ast) if m[0] == "p"})
                lc = lam_costs(ast, costs)
                row.update(expressible=ok, verify=v, src=S.to_src(ast), nodes=S.size(ast), depth=depth(ast),
                           cost_pi0=cost(ast, costs), max_lambda_cost=max(lc, default=0), prims=prims,
                           consts=sorted({m[1] for m in S.nodes(ast) if m[0] == "c"}),
                           within_cost_bound=cost(ast, costs) <= 18, within_lam_pi0=max(lc, default=0) <= 6,
                           within_lam_raised=max(lc, default=0) <= raised)
                if ok and j == 0:
                    from nexus.campaign import substrate as S1
                    row["reach_focus"] = reach(t, ast, prims, 5.0)
                    row["reach_full_lam6"] = reach(t, ast, None, 0.6, mod=S1, lam_max=6)      # Phase 1 bounds
                    row["reach_full_raised"] = reach(t, ast, None, 0.6)                      # Phase 2 lazy lambdas
                rows.append(row)
                print(t.tid, t.descr[:34], "expr", row.get("expressible"), "cost", row.get("cost_pi0"), "lam",
                      row.get("max_lambda_cost"), "focus", (row.get("reach_focus") or {}).get("found"),
                      "full6 lvl", (row.get("reach_full_lam6") or {}).get("level_completed"),
                      "full6", bool((row.get("reach_full_lam6") or {}).get("found")),
                      "fullR", bool((row.get("reach_full_raised") or {}).get("found")), row.get("note") or "", flush=True)
    fam = {}
    for r in rows:
        f = r["tid"].split(".")[1]
        e = fam.setdefault(f, dict(instances=0, expressible=0, lam_block_pi0=0, focus_reached=0, full6=0, fullR=0, notes=set()))
        e["instances"] += 1
        e["expressible"] += bool(r.get("expressible"))
        e["lam_block_pi0"] += r.get("expressible") is True and not r["within_lam_pi0"]
        if "reach_focus" in r:
            e["focus_reached"] += bool(r["reach_focus"]["found"])
            e["full6"] += bool(r["reach_full_lam6"]["found"])
            e["fullR"] += bool(r["reach_full_raised"]["found"])
        if r.get("note"):
            e["notes"].add(r["note"])
    for e in fam.values():
        e["notes"] = sorted(e["notes"])
    out = dict(raised_lam_max=raised, rows=rows, families=fam)
    (ROOT / "artifacts/agi2_audit.json").write_text(json.dumps(out, indent=1, default=list))
    for f, e in fam.items():
        print(f, e)


if __name__ == "__main__":
    main(*sys.argv[1:])
