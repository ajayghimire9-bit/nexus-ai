"""Trial 4 (NOT LOCKED).  python scripts/t7_trial4.py KIND  (KIND = rename | widen | unit | epoch | cross | decide)
A = W.Task(family, t7/tdev 0); its skill g_A = NEXUS's own hybrid solution (count costs, 4 s; skipped if A does not
generalise). B = the evolved instance (t7/theld 0 seed: fresh synonyms) with: rename (names only), widen (+2 numeric
distractor columns, ints -> floats), unit (first numeric field x100, reference divides), epoch (ts fields x1000), cross
(a different family / domain with the same skeleton). Arms (all CPU charged: alignment, probes, certification, fallback):
Fresh; Useful_Reuse (g_A unchanged if it certifies, else fresh); Name / Heuristic / HDC / Random / GW map -> transport ->
certify on B's 30 examples -> fresh fallback; GW+DeltaM: on a failed certification, g_A becomes a library function and the
hybrid search on B looks for fn_T(args) (2 s) before the fresh fallback. Metric: B held-out correct; total CPU.
KEEP iff GW or GW+DeltaM beats Fresh and Heuristic on correct, or ties both with lower total CPU (>= 10%)."""
import copy, json, sys, time
sys.path.insert(0, "scripts")
from u5_common import ROOT, K, W, load, learner_cfg
from nexus import t7_seeds, t7_world, t7_transport as TR, seed_registry as R  # noqa: F401
from nexus.oop_synthesizer import ev
ART = ROOT / "artifacts/t7_dev"
cfg = learner_cfg("count", load("p2_policy.json"))
NUMF = [f for f in W.FAMILIES if f[0] in "LCI" and W.FAMILIES[f]["out"] == "num"]
SA, SB = list(R.REGISTRY[("t7", "tdev")])[0], list(R.REGISTRY[("t7", "theld")])[0]
CROSS = [("I.power", "C.notional"), ("C.notional", "I.power"), ("I.kwh", "E.cost")]


def scale_node(n, f, k):
    tgt = ("u", "float", ("b", "get", ("var", "r"), ("const", f)))
    if n == tgt:
        return ("b", "/", tgt, ("const", k))
    if n[0] in ("var", "const"):
        return n
    return tuple(scale_node(c, f, k) if isinstance(c, tuple) else c for c in n)


def evolve(fam_a, kind):
    fam_b = fam_a if kind != "cross" else dict(CROSS)[fam_a]
    B = W.Task(f"{fam_b}#B", fam_b, SB)
    roles = W.FAMILIES[fam_b]["roles"]
    numr = [B.names[r] for r, k in roles.items() if k not in ("ccy", "member")]
    ref = B.reference

    def tx(e):
        e = copy.deepcopy(e)
        r = e["r"]
        if kind == "widen":
            for i, f in enumerate(numr[:2]):
                r[f"aux_{i}"] = float(r[f]) * 1.37 + 3 if isinstance(r[f], (int, float)) else r[f]
            for k2, v in list(r.items()):
                if isinstance(v, int) and not isinstance(v, bool):
                    r[k2] = float(v)
        if kind == "unit" and isinstance(r.get(numr[0]), (int, float)):
            r[numr[0]] = r[numr[0]] * 100
        if kind == "epoch":
            for f in numr:
                r[f] = r[f] * 1000
        return e
    if kind == "unit":
        ref = scale_node(ref, numr[0], 100)
    if kind == "epoch":
        for f in numr:
            ref = scale_node(ref, f, 1000)
    B.train, B.test, B.reference = [tx(e) for e in B.train], [tx(e) for e in B.test], ref
    B.y_train = [round(v, 9) if isinstance(v, float) else v for v in (ev(ref, e) for e in B.train)]
    return B


def certify(node, B):
    return node is not None and all(K._ok(K._safe_ev(node, e), y) for e, y in zip(B.train, B.y_train))


def fresh(B, budget=4.0):
    node, st, _ = K.solve_hybrid(B.train, B.y_train, cfg, [], budget)
    return node


def run_pair(fam, kind):
    A = W.Task(f"{fam}#A", fam, SA)
    gA, _, _ = K.solve_hybrid(A.train, A.y_train, cfg, [], 4.0)
    if gA is None or W.correct_on(A, gA) < 1.0:
        return None
    B = evolve(fam, kind)
    cA, cB = TR.columns(A.train), TR.columns(B.train)
    res = {}
    for arm in ("Fresh", "Useful_Reuse", "Name", "Heuristic", "HDC", "Random", "GW", "GW+DeltaM"):
        t0 = time.process_time()
        node, path = None, ""
        if arm == "Fresh":
            node, path = fresh(B), "fresh"
        elif arm == "Useful_Reuse":
            node, path = (gA, "reuse") if certify(gA, B) else (fresh(B), "fresh")
        else:
            mp = {"Name": TR.map_names, "Heuristic": TR.map_heuristic, "HDC": TR.map_hdc, "Random": TR.map_random,
                  "GW": TR.map_gw, "GW+DeltaM": TR.map_gw}[arm](cB, cA)
            g = TR.transport(gA, {a: b for b, a in mp.items()})
            if certify(g, B):
                node, path = g, "transported"
            elif arm == "GW+DeltaM" and TR.as_function(gA) is not None:
                fid, params, body = TR.as_function(gA)
                n2, st, _ = K.solve_hybrid(B.train, B.y_train, cfg, [(fid, params, body)], 2.0)
                node, path = (n2, "delta_m") if n2 is not None else (fresh(B), "fresh")
            if node is None:
                node, path = fresh(B), "fresh"
        res[arm] = dict(correct=node is not None and W.correct_on(B, node) == 1.0, cpu_s=round(time.process_time() - t0, 4), path=path)
    return res


kind = sys.argv[1]
if kind != "decide":
    fams = [a for a, _ in CROSS] if kind == "cross" else ["L.delay", "L.late"] if kind == "epoch" else NUMF
    out = {}
    for f in fams:
        r = run_pair(f, kind)
        if r:
            out[f] = r
            print(kind, f, {a: (v["correct"], v["path"], v["cpu_s"]) for a, v in r.items()}, flush=True)
    (ART / f"t4_{kind}.json").write_text(json.dumps(out, indent=1))
else:
    allr = {}
    for k in ("rename", "widen", "unit", "epoch", "cross"):
        p = ART / f"t4_{k}.json"
        if p.exists():
            for f, r in json.loads(p.read_text()).items():
                allr[f"{k}:{f}"] = r
    arms = ("Fresh", "Useful_Reuse", "Name", "Heuristic", "HDC", "Random", "GW", "GW+DeltaM")
    tab = {a: dict(correct=sum(r[a]["correct"] for r in allr.values()), cpu_s=round(sum(r[a]["cpu_s"] for r in allr.values()), 3),
                   transported=sum(r[a]["path"] in ("transported", "reuse", "delta_m") for r in allr.values())) for a in arms}
    def wins(g):
        return all(tab[g]["correct"] > tab[b]["correct"] or (tab[g]["correct"] == tab[b]["correct"] and tab[g]["cpu_s"] <= 0.9 * tab[b]["cpu_s"])
                   for b in ("Fresh", "Heuristic"))
    keep = wins("GW") or wins("GW+DeltaM")
    (ART / "t4.json").write_text(json.dumps(dict(n_pairs=len(allr), table=tab, verdict="KEPT" if keep else "REJECTED", pairs=allr), indent=1))
    print("pairs", len(allr)); [print(a, v) for a, v in tab.items()]; print("VERDICT", "KEPT" if keep else "REJECTED")
