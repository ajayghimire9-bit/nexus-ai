"""Wave 40 analysis (NOT LOCKED): raw rows -> reported tables. Pure post-processing; no task is re-run.
  lodo   : internal folds (Wave 39 lodo_tables logic + the Fixed+Repr-v5 arm; curves at 0.25x-2x of 2M executions)
  stream : 6-phase stream, per learner pooled + per seed, vs every control at equal coverage
  prose  : Step 5 decomposition: search work at 500 / 2k / 8k / 36k execution caps, certification work, sound witness
           short-circuit accounting, HOV, online arms (ungated vs payoff-gated)."""
import json, sys
sys.path.insert(0, "src")
from nexus.w39_eval import at_cap
CAPS = (0.25, 0.5, 1.0, 2.0)
B = 2_000_000
ARMS = ("Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Fixed+Repr-v5", "Repr-core-v5")
FITTED = {"Placebo-v5", "Repr-v5", "Fixed+Repr-v5", "Repr-core-v5"}
SCAPS = (500, 2000, 8000, 36000)


def lodo(paths, arms=ARMS):
    pooled = {a: dict(correct=0, n=0, wrong=0, work=0, fit=0, curve={str(c): [0, 0] for c in CAPS}) for a in arms}
    per_seed, src, src_core, nf = {}, 0, 0, 0
    inter, n_inter = {a: 0 for a in arms}, 0
    for pth in paths:
        folds = {h: f for h, f in json.load(open(pth)).items() if not h.startswith("_")}
        ps = {}
        for a in arms:
            rows = [x for f in folds.values() for x in f["arms"][a]]
            fit = sum(f["fit_instr"].get(a, 0) for f in folds.values()) if a in FITTED else 0
            ps[a] = dict(correct=sum(x["correct"] for x in rows), n=len(rows), wrong=sum(x["wrong"] for x in rows),
                         work=sum(x["work"] for x in rows), fit=fit)
            for k in ("correct", "n", "wrong", "work", "fit"):
                pooled[a][k] += ps[a][k]
            for c in CAPS:
                rs = [at_cap(x, c * B) for x in rows]
                pooled[a]["curve"][str(c)][0] += sum(1 for x, y in zip(rows, rs) if y["solved"] and x["correct"])
                pooled[a]["curve"][str(c)][1] += sum(y["work"] for y in rs)
        per_seed[pth] = ps
        for f in folds.values():
            nf += 1
            src += f["source"]["work"]
            seen = set()
            for w, m, c in zip(f["source"]["work_by_task"], f["source"]["mech_by_task"], f["source"]["cert_by_task"]):
                if tuple(m) not in seen:
                    src_core += w
                    if c:
                        seen.add(tuple(m))
            for j in range(len(f["arms"][arms[0]])):
                if all(f["arms"][a][j]["correct"] for a in arms):
                    n_inter += 1
                    for a in arms:
                        inter[a] += f["arms"][a][j]["work"]
    return dict(pooled=pooled, per_seed=per_seed, source_work=src / max(1, nf), source_core_work=src_core / max(1, nf), n_folds=nf,
                intersection=dict(n=n_inter, work=inter))


def show_lodo(t):
    P, I = t["pooled"], t["intersection"]
    print("arm | solved/n | wrong | target work G | fit G | work incl fit G | solved@0.25x/0.5x/1x/2x | work G @caps")
    for a, x in P.items():
        print(f"  {a:14s} {x['correct']:3d}/{x['n']:3d} {x['wrong']:2d} {x['work'] / 1e9:9.1f} {x['fit'] / 1e9:6.3f} {(x['work'] + x['fit']) / 1e9:9.1f}  "
              + "/".join(str(x["curve"][k][0]) for k in x["curve"]) + "  " + "/".join(f"{x['curve'][k][1] / 1e9:.0f}" for k in x["curve"]))
    print(f"intersection (solved by all arms): n={I['n']}  " + "  ".join(f"{a} {w / 1e9:.1f}G" for a, w in I["work"].items()))
    tot = lambda d, a: d[a]["work"] + d[a]["fit"]
    for prim, ctrls in (("Repr-v5", ("Fresh-v5", "Placebo-v5", "Fixed-v5")), ("Fixed+Repr-v5", ("Fixed-v5", "Fresh-v5", "Placebo-v5"))):
        for c in ctrls:
            wins = sum(1 for ps in t["per_seed"].values() if tot(ps, prim) < tot(ps, c) and ps[prim]["correct"] >= ps[c]["correct"])
            print(f"  {prim} vs {c}: total ratio (fit charged) {tot(P, prim) / tot(P, c):.3f} | intersection ratio "
                  f"{I['work'][prim] / I['work'][c]:.3f} | solves {P[prim]['correct']} vs {P[c]['correct']} | seeds won (cheaper AND solves >=) "
                  f"{wins}/{len(t['per_seed'])}")
    for prim, core in (("Repr-v5", False), ("Fixed+Repr-v5", False), ("Repr-core-v5", True)):
        base = "Fixed-v5" if prim == "Fixed+Repr-v5" else "Fresh-v5"
        saving = (P[base]["work"] - P[prim]["work"]) / max(1, P[prim]["n"])
        extra = (t["source_core_work"] if core else t["source_work"]) + P[prim]["fit"] / t["n_folds"]
        print(f"  source accounting {prim} (vs {base}): mandatory-work (marginal fit) {P[prim]['fit'] / 1e9:.3f}G | extra-curriculum "
              f"{extra / 1e9:.0f}G per prior | saving per target task {saving / 1e9:.2f}G | break-even "
              f"{extra / saving if saving > 0 else float('inf'):.0f} target tasks per prior")


def stream(paths, learners=("Fresh", "no-gate", "regime-memory", "hier-s1")):
    P = {l: dict(work=0, correct=0, n=0, wrong=0, learn=0) for l in learners}
    per = {}
    for pth in paths:
        r = json.load(open(pth))
        per[pth] = {l: r[l] for l in learners}
        for l in learners:
            for k in P[l]:
                P[l][k] += r[l][k]
    return dict(pooled=P, per_seed=per)


def show_stream(t, prim="hier-s1"):
    P = t["pooled"]
    names = {"Fresh": "Fresh-v5", "no-gate": "Ungated Online", "regime-memory": "Hard-Gated", "hier-s1": "Hierarchical Stream Memory"}
    print("learner | solved/n | wrong | total work G (learning incl.) | learning G")
    for l, x in P.items():
        print(f"  {names[l]:27s} {x['correct']:3d}/{x['n']:3d} {x['wrong']:2d} {x['work'] / 1e9:9.1f} {x['learn'] / 1e9:7.3f}")
    for c in P:
        if c == prim:
            continue
        wins = sum(1 for ps in t["per_seed"].values() if ps[prim]["work"] < ps[c]["work"] and ps[prim]["correct"] >= ps[c]["correct"])
        lost = sum(1 for ps in t["per_seed"].values() for a, b in zip(ps[c]["solved"], ps[prim]["solved"]) if a and not b)
        print(f"  {names[prim]} vs {names[c]}: work ratio {P[prim]['work'] / P[c]['work']:.3f} | solves {P[prim]['correct']} vs "
              f"{P[c]['correct']} | tasks solved by {names[c]} but not {names[prim]}: {lost} | seeds won (cheaper AND solves >=) "
              f"{wins}/{len(t['per_seed'])}")


def prose(path, static=("Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Fixed+Repr-v5"),
          online=("Online-hier-v5", "Online-hier-payoff-v5")):
    r = json.load(open(path))
    T = r["tasks"]
    ev = lambda a: [T[n][a] for n in sorted(T) if "work" in T[n].get(a, {})]
    out = {"static": {}, "online": {}, "n_tasks": len(T)}
    for a in static:
        rs = ev(a)
        if not rs:
            continue
        s_ = sum(x["search_instr"] for x in rs); w_ = sum(x["witness_instr"] for x in rs); c_ = sum(x["checker_instr"] for x in rs)
        ch = sum(x["child_instr"] for x in rs)
        nosc = ch - w_ + c_
        sc = ch + sum(x["checker_instr"] for x in rs if not x["witness_found"])
        cand = [x for x in rs if x["iters"] and x["iters"][0][1]]
        caps = {}
        for cap in SCAPS:
            found = [x for x in cand if x["iters"][0][0] <= cap]
            instr = sum(x["search_instr"] if (x["iters"] and x["iters"][0][1] and x["iters"][0][0] <= cap)
                        else x["search_instr"] * min(1.0, cap / max(1, x["iters"][0][0] if x["iters"] else 1)) for x in rs)
            caps[cap] = dict(candidates=len(found), certified=sum(bool(x.get("certified")) for x in found),
                             hov=sum(bool(x.get("held_out_verified")) for x in found), search_G=instr / 1e9)
        uniq = [x for x in rs if x.get("first_label") == "SCOPE_UNIQUE"]
        amb = [x for x in rs if x.get("first_label") == "AMBIGUOUS"]
        out["static"][a] = dict(
            evaluable=len(rs), candidates=len(cand), certified=sum(bool(x.get("certified")) for x in rs),
            hov=sum(bool(x.get("held_out_verified")) for x in rs),
            cert_heldout_fail=sum(bool(x.get("certified")) and not x.get("held_out_verified") for x in rs),
            execs=sum(x["execs"] for x in rs), search_G=s_ / 1e9, witness_G=w_ / 1e9, cert_G=c_ / 1e9, nosc_G=nosc / 1e9, sc_G=sc / 1e9,
            search_share=s_ / max(1, s_ + c_), caps=caps, unique=len(uniq), ambiguous=len(amb),
            cert_G_unique=sum(x["checker_instr"] for x in uniq) / 1e9, cert_G_ambiguous=sum(x["checker_instr"] for x in amb) / 1e9,
            witness_found=sum(x["witness_found"] for x in rs), witness_unsound=sum(x["witness_unsound"] for x in rs),
            ambiguous_short_circuited=sum(x["witness_found"] for x in amb))
    names = [n for n in T if all(T[n].get(a, {}).get("held_out_verified") for a in static if a in out["static"])]
    out["intersection"] = dict(n=len(names), nosc_G={a: sum(T[n][a]["child_instr"] - T[n][a]["witness_instr"] + T[n][a]["checker_instr"]
                                                           for n in names) / 1e9 for a in out["static"]},
                               search_G={a: sum(T[n][a]["search_instr"] for n in names) / 1e9 for a in out["static"]})
    for a in online:
        rs = ev(a)
        if not rs:
            continue
        info = r.get("online", {}).get(a, {})
        out["online"][a] = dict(evaluable=len(rs), certified=sum(bool(x.get("certified")) for x in rs),
                                hov=sum(bool(x.get("held_out_verified")) for x in rs),
                                work_G=(sum(x["work"] for x in rs) + info.get("learn_instr", 0)) / 1e9,
                                child_G=sum(x["child_instr"] for x in rs) / 1e9, cert_G=sum(x["checker_instr"] for x in rs) / 1e9,
                                learn_G=info.get("learn_instr", 0) / 1e9, gate_log=info.get("gate_log"))
    return out


def show_prose(t):
    S = t["static"]
    print("arm | eval | cand | cert | HOV | cert-but-heldout-fail | search G | witness G | certification G | search share | "
          "total no-SC G | total SC G")
    for a, x in S.items():
        print(f"  {a:14s} {x['evaluable']:3d} {x['candidates']:3d} {x['certified']:3d} {x['hov']:3d} {x['cert_heldout_fail']:2d} "
              f"{x['search_G']:8.1f} {x['witness_G']:7.1f} {x['cert_G']:9.1f} {100 * x['search_share']:5.1f}% {x['nosc_G']:9.1f} {x['sc_G']:9.1f}")
    print("search work alone at execution caps (candidates found / search G):")
    for a, x in S.items():
        print(f"  {a:14s} " + "  ".join(f"{c}: {v['candidates']} / {v['search_G']:.1f}G" for c, v in x["caps"].items()))
    print("certification split (kernel label of the first evidence) and witness short-circuit:")
    for a, x in S.items():
        print(f"  {a:14s} unique {x['unique']} ({x['cert_G_unique']:.1f}G) | ambiguous {x['ambiguous']} ({x['cert_G_ambiguous']:.1f}G), "
              f"short-circuited {x['ambiguous_short_circuited']} | witness found {x['witness_found']} | unsound {x['witness_unsound']}")
    I = t["intersection"]
    print(f"intersection (HOV by every static arm) n={I['n']}: no-SC G " + ", ".join(f"{a} {v:.1f}" for a, v in I["nosc_G"].items()))
    print("  search G on the intersection: " + ", ".join(f"{a} {v:.2f}" for a, v in I["search_G"].items()))
    for a, x in t["online"].items():
        print(f"  {a:22s} eval {x['evaluable']} cert {x['certified']} HOV {x['hov']} work {x['work_G']:.1f}G (child {x['child_G']:.1f}, "
              f"certification {x['cert_G']:.1f}, learning {x['learn_G']:.3f}) gate {x['gate_log']}")


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "lodo":
        show_lodo(lodo(sys.argv[2:]))
    elif kind == "stream":
        show_stream(stream(sys.argv[2:]))
    else:
        show_prose(prose(sys.argv[2]))
