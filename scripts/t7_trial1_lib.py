"""Trial 1, library arm (NOT LOCKED).  python scripts/t7_trial1_lib.py wake | items K/N | decide
wake:  NEXUS's promoted u5 learner (count costs, hybrid) solves t7 src (L, C, I families x tsrc 0-2; 63 tasks, 4 s) ->
       pooled with the u5 src solutions; candidates = u5_library.candidates with >= 1 use (min_uses lowered: the filter
       needs >= 20 candidates); one knockoff twin per candidate.
items: utility of each real item and each twin on EVAL = t7 tdev 0 (L, C, I; 21 tasks, 2 s): base run once; for an item,
       utility = (solves_with - solves_base) + 0.5 * (cpu_base - cpu_with) / cpu_base. Split in N parts (900 s cap).
decide: knockoff+ (q = 0.20) vs CURRENT admission (u5 greedy separate-task utility on the same pool and EVAL; its CPU =
       its work) vs MDL. Realised false admission: each admitted item is re-evaluated on HELD = t7 theld 0 (21 tasks);
       false = it does not improve held-out solves and does not cut held-out CPU by >= 5%."""
import json, sys, time
sys.path.insert(0, "scripts")
from u5_common import ROOT, K, W, save, load, node_dump, node_load, learner_cfg
from nexus import t7_seeds, t7_world  # noqa: F401
from nexus import u5_library as LB, t7_knockoff as KO
ART = ROOT / "artifacts/t7_dev"
ART.mkdir(exist_ok=True)
P = load("p2_policy.json")
cfg = learner_cfg("count", P)
LCI = [f for f in W.FAMILIES if f[0] in "LCI"]


def tasks(kind, idx):
    from nexus import seed_registry as R
    rng = list(R.REGISTRY[("t7", kind)])
    return [W.Task(f"{f}#{rng[i]}", f, rng[i]) for f in LCI for i in idx]


def sv(name, obj):
    (ART / name).write_text(json.dumps(obj, indent=1, default=str))


def ld(name):
    return json.loads((ART / name).read_text())


def evaluate(ts, lib, budget=2.0):
    ok, cpu = 0, 0.0
    for t in ts:
        node, st, _ = K.solve_hybrid(t.train, t.y_train, cfg, lib, budget)
        ok += node is not None and W.correct_on(t, node) == 1.0
        cpu += st["cpu_s"]
    return ok, cpu


cmd = sys.argv[1]
if cmd == "wake":
    c0 = time.process_time()
    sols = [node_load(s) for s in load("p2_policy.json")["solutions"]] + [node_load(s) for s in load("p3_wake.json")["solutions"]]
    for t in tasks("tsrc", range(3)):
        node, st, _ = K.solve_hybrid(t.train, t.y_train, cfg, [], 4.0)
        if node is not None:
            sols.append(node)
    seen = {}
    for pi, prog in enumerate(sols):
        for tr in LB._subtrees(prog):
            if 3 <= LB.size(tr) <= 9 and tr[0] in ("u", "b"):
                for keep in (True, False):
                    ps = []
                    body = LB._generalise(tr, ps, keep)
                    if ps and len(ps) <= 3:
                        seen.setdefault(LB.fid_of(body, ps), [ps, body, set()])[2].add(pi)
    cands = sorted(((f, p, b, len(u)) for f, (p, b, u) in seen.items()), key=lambda x: (-x[3], LB.size(x[2])))
    items = [dict(fid=f, params=p, body=node_dump(b), uses=u, twin=node_dump(KO.twin(p, b, seed=i))) for i, (f, p, b, u) in enumerate(cands)]
    base = evaluate(tasks("tdev", [0]), [])
    sv("t1_pool.json", dict(n_solutions=len(sols), items=items, base=base, wake_cpu_s=round(time.process_time() - c0, 3)))
    print("solutions", len(sols), "candidates", len(items), "base", base)
elif cmd == "items":
    k, n = map(int, sys.argv[2].split("/"))
    pool = ld("t1_pool.json")
    ev = tasks("tdev", [0])
    out = []
    for i, it in enumerate(pool["items"]):
        if i % n != k - 1:
            continue
        p = it["params"]
        r = evaluate(ev, [(it["fid"], p, node_load(it["body"]))])
        tw = evaluate(ev, [(it["fid"] + "_ko", p, node_load(it["twin"]))])
        out.append(dict(i=i, fid=it["fid"], real=r, twin=tw))
        print(i, it["fid"], r, tw, flush=True)
    sv(f"t1_items_{k}of{n}.json", out)
else:
    pool = ld("t1_pool.json")
    rows = sorted([r for f in sorted(ART.glob("t1_items_*of*.json")) for r in json.loads(f.read_text())], key=lambda r: r["i"])
    b_ok, b_cpu = pool["base"]
    u = lambda r: (r[0] - b_ok) + 0.5 * (b_cpu - r[1]) / b_cpu  # noqa: E731
    Wv = [u(r["real"]) - u(r["twin"]) for r in rows]
    T, adm = KO.knockoff_plus(Wv, 0.20)
    ko_work = sum(r["real"][1] + r["twin"][1] for r in rows) + b_cpu
    items = pool["items"]
    cands = {items[r["i"]]["fid"]: (items[r["i"]]["params"], node_load(items[r["i"]]["body"]), items[r["i"]]["uses"]) for r in rows}
    t0 = time.process_time()
    from nexus import seed_registry as R
    ev = tasks("tdev", [0])
    cur, log, cur_cpu = LB.admit_utility(cands, ev, cfg, 2.0, top_k=len(cands), max_fns=8, max_s=850.0)
    mdl = LB.admit_mdl([node_load(s) for s in load("p2_policy.json")["solutions"]], cands)
    held = tasks("theld", [0])
    hb = evaluate(held, [])
    def false_adm(lib_items):
        res = []
        for f, p, b in lib_items:
            ok, cpu = evaluate(held, [(f, p, b)])
            res.append(dict(fid=f, held=(ok, cpu), false=not (ok > hb[0] or (ok >= hb[0] and cpu <= 0.95 * hb[1]))))
        return res
    ko_items = [(rows[j]["fid"], items[rows[j]["i"]]["params"], node_load(items[rows[j]["i"]]["body"])) for j in adm]
    ko_check, cur_check = false_adm(ko_items), false_adm(cur)
    fdr = sum(x["false"] for x in ko_check) / max(1, len(ko_check))
    keep = (len(rows) >= 20 and fdr <= 0.20 and ko_work <= cur_cpu and len(ko_items) < max(1, len(mdl)) and len(ko_items) <= max(len(cur), 0)
            and len(ko_items) > 0)
    sv("t1_lib.json", dict(n_candidates=len(rows), W=Wv, threshold=T, admitted=[x[0] for x in ko_items], knockoff_work_cpu_s=round(ko_work, 3),
                           current_admitted=[x[0] for x in cur], current_work_cpu_s=round(cur_cpu, 3), current_log=log,
                           mdl_admitted=[x[0] for x in mdl], held_base=hb, knockoff_held=ko_check, current_held=cur_check,
                           realised_fdr=fdr, verdict="KEPT" if keep else "REJECTED"))
    print("candidates", len(rows), "T", T, "admitted", len(ko_items), "fdr", fdr, "ko_work", round(ko_work, 1), "cur", len(cur), round(cur_cpu, 1),
          "mdl", len(mdl), "VERDICT", "KEPT" if keep else "REJECTED")
