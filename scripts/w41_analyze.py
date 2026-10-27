"""Wave 41 analysis (NOT LOCKED): raw rows -> reported tables. Pure post-processing.
  track1 FILES... | track2 FILE | track3 FILE"""
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
from nexus.w39_eval import at_cap
import w41_common as C
CAPS = (0.25, 0.5, 1.0, 2.0)
B = 2_000_000
G9 = 1e9


def track1(paths, arms=C.ARMS):
    P = {a: dict(correct=0, n=0, wrong=0, work=0, fit=0, learn=0, curve={c: [0, 0] for c in CAPS},
                 cat={k: [0, 0, 0] for k in ("familiar", "held_out", "novel_composition", "seen_composition")}) for a in arms}
    per, src, srcc, nf, inter, ni = {}, 0, 0, 0, {a: 0 for a in arms}, 0
    skills = {a: [] for a in arms}
    for pth in paths:
        folds = {h: f for h, f in json.load(open(pth)).items() if not h.startswith("_")}
        ps = {}
        for a in arms:
            rows = [x for f in folds.values() for x in f["arms"][a]]
            fit = sum(f["fit_instr"][a] for f in folds.values())
            learn = sum(f["learn_instr"][a] for f in folds.values())
            ps[a] = dict(correct=sum(x["correct"] for x in rows), work=sum(x["work"] for x in rows) + fit + learn)
            X = P[a]
            X["correct"] += ps[a]["correct"]; X["n"] += len(rows); X["wrong"] += sum(x["wrong"] for x in rows)
            X["work"] += sum(x["work"] for x in rows); X["fit"] += fit; X["learn"] += learn
            for c in CAPS:
                rs = [at_cap(x, c * B) for x in rows]
                X["curve"][c][0] += sum(1 for x, y in zip(rows, rs) if y["solved"] and x["correct"])
                X["curve"][c][1] += sum(y["work"] for y in rs)
            for x in rows:
                for key in (x["category"], "novel_composition" if x["novel_composition"] else "seen_composition"):
                    X["cat"][key][0] += x["correct"]; X["cat"][key][1] += 1; X["cat"][key][2] += x["work"]
            skills[a] += [f["skills"][a] for f in folds.values()]
        per[pth] = ps
        for f in folds.values():
            nf += 1; src += f["source"]["work"]
            seen = set()
            for w, m, c in zip(f["source"]["work_by_task"], f["source"]["mech_by_task"], f["source"]["cert_by_task"]):
                if tuple(m) not in seen:
                    srcc += w
                    if c:
                        seen.add(tuple(m))
            for j in range(len(f["arms"][arms[0]])):
                if all(f["arms"][a][j]["correct"] for a in arms):
                    ni += 1
                    for a in arms:
                        inter[a] += f["arms"][a][j]["work"]
    return dict(pooled=P, per_seed=per, source_work=src / max(1, nf), source_core=srcc / max(1, nf), n_folds=nf,
                inter=dict(n=ni, work=inter), skills=skills)


def show_track1(t):
    P = t["pooled"]
    tot = lambda a: P[a]["work"] + P[a]["fit"] + P[a]["learn"]
    print("arm | solved/n | wrong | target G | fit G | online-learn G | total G | vs Flat | solved@0.25/0.5/1/2x")
    for a, x in P.items():
        print(f"  {a:31s} {x['correct']:3d}/{x['n']:3d} {x['wrong']:2d} {x['work'] / G9:9.1f} {x['fit'] / G9:6.3f} {x['learn'] / G9:7.3f} "
              f"{tot(a) / G9:9.1f} {tot(a) / tot('Flat_NEXUS_v5'):6.3f}  " + "/".join(str(x["curve"][c][0]) for c in CAPS))
    print("by category: solved/n and work G (familiar | held_out | novel_composition | seen_composition)")
    for a, x in P.items():
        print(f"  {a:31s} " + " | ".join(f"{v[0]}/{v[1]} {v[2] / G9:.1f}G" for v in x["cat"].values()))
    I = t["inter"]
    print(f"intersection n={I['n']}: " + ", ".join(f"{a} {w / I['work']['Flat_NEXUS_v5']:.3f}" for a, w in I["work"].items()))
    for a in P:
        if a == "Flat_NEXUS_v5":
            continue
        wins = sum(1 for ps in t["per_seed"].values() if ps[a]["work"] < ps["Flat_NEXUS_v5"]["work"] and ps[a]["correct"] >= ps["Flat_NEXUS_v5"]["correct"])
        winp = sum(1 for ps in t["per_seed"].values() if ps[a]["work"] < ps["Size_Matched_Placebo_Hierarchy"]["work"]
                   and ps[a]["correct"] >= ps["Size_Matched_Placebo_Hierarchy"]["correct"]) if "Size_Matched_Placebo_Hierarchy" in P else 0
        print(f"  {a}: seeds cheaper than Flat at >= solves {wins}/{len(t['per_seed'])}; than Placebo {winp}/{len(t['per_seed'])}")
    for a in ("Learned_Hierarchy", "Learned_Hierarchy_PS_Growth"):
        if a in P:
            sv = (P["Flat_NEXUS_v5"]["work"] - P[a]["work"]) / max(1, P[a]["n"])
            ex = t["source_work"] + (P[a]["fit"] + P[a]["learn"]) / t["n_folds"]
            print(f"  accounting {a}: mandatory (fit + online learn) {(P[a]['fit'] + P[a]['learn']) / G9:.3f}G | extra curriculum "
                  f"{ex / G9:.0f}G per fold | saving per target vs Flat {sv / G9:.3f}G | break-even "
                  f"{(ex / sv) if sv > 0 else float('inf'):.0f} tasks")
    print("skills (start -> end per fold):", {a: [(s["start"], s["end"]) for s in v] for a, v in t["skills"].items() if any(s["start"] or s["end"] for s in v)})


def track2(path, arms=C.ARMS):
    r = json.load(open(path))
    out = {}
    for a in arms:
        if a not in r:
            continue
        rows = r[a]["rows"]
        q = []
        for i in range(0, len(rows), 100):
            seg = rows[i:i + 100]
            w = sum(x["work"] + x.get("learn_instr", 0) for x in seg)
            s = sum(x["correct"] for x in seg)
            q.append(dict(solved=s, n=len(seg), work=w, per_solved=w / max(1, s), wrong=sum(x["wrong"] for x in seg)))
        sk = [x.get("update", {}).get("skills") for x in rows if x.get("update")]
        out[a] = dict(quintiles=q, total=sum(x["work"] + x.get("learn_instr", 0) for x in rows), solved=sum(x["correct"] for x in rows),
                      n=len(rows), wrong=sum(x["wrong"] for x in rows), skills_end=sk[-1] if sk else 0,
                      learn=sum(x.get("learn_instr", 0) for x in rows))
    return out


def show_track2(t):
    print("arm | solved/n | wrong | total G (incl. learning) | learning G | G per solved task by quintile (1-100 ... 401-500) | skills")
    base = t.get("Flat_NEXUS_v5")
    for a, x in t.items():
        print(f"  {a:31s} {x['solved']:3d}/{x['n']:3d} {x['wrong']:2d} {x['total'] / G9:9.1f} {x['learn'] / G9:7.3f}  "
              + " / ".join(f"{q['per_solved'] / G9:.2f}" for q in x["quintiles"]) + f"  {x['skills_end']}"
              + (f"  (vs Flat {x['total'] / base['total']:.3f})" if base else ""))


def track3(path, arms=C.ARMS + ("Flat_noLemma",)):
    r = json.load(open(path))
    T = r["tasks"]
    out = {"n": len(T), "arms": {}, "source": {k: v for k, v in r["source"].items() if k not in ("programs", "sigs")}, "fit": r.get("fit")}
    for a in arms:
        rows = [v[a] for v in T.values() if "work" in v.get(a, {})]
        if not rows:
            continue
        nc = [x for x in rows if x["status"] == "no_candidate"]
        X = dict(evaluable=len(rows), search=sum(x["search_instr"] for x in rows), witness=sum(x["witness_instr"] for x in rows),
                 cert=sum(x["checker_instr"] for x in rows), oracle=sum(x["oracle"] for x in rows) * 5e7,
                 total=sum(x["work"] for x in rows), nocand=len(nc), nocand_search=sum(x["search_instr"] for x in nc),
                 rss=max(x["rss"] or 0 for x in rows), kernel_calls=sum(x["kernel_calls"] for x in rows),
                 skill_won=sum(bool(x.get("skill_won")) for x in rows), lemma_skips=sum(x["lemma_skips"] for x in rows),
                 fit=(r.get("fit", {}).get(a, {}) or {}).get("instr", 0), learn=(r.get("fit", {}).get(a, {}) or {}).get("online_learn_instr", 0))
        X["k"] = {k: {f: sum(x["k"][str(k)][f] for x in rows) for f in ("certified", "hov", "cbf", "silent_raw", "silent_guard",
                                                                        "ans_raw", "ans_guard", "n_in")} for k in range(3)}
        out["arms"][a] = X
    return out


def show_track3(t):
    print(f"tasks {t['n']}; source (internal, extra curriculum) {t['source']}")
    print("arm | eval | search G | no-cand (n, search G) | witness G | certification G | oracle G | total G | vs Flat | kernel calls | "
          "peak RSS MB | fit G | online learn G")
    base = t["arms"].get("Flat_NEXUS_v5")
    for a, x in t["arms"].items():
        print(f"  {a:31s} {x['evaluable']:3d} {x['search'] / G9:8.1f} ({x['nocand']:3d}, {x['nocand_search'] / G9:7.1f}) {x['witness'] / G9:7.1f} "
              f"{x['cert'] / G9:9.1f} {x['oracle'] / G9:5.1f} {x['total'] / G9:8.1f} {x['total'] / base['total']:6.3f} {x['kernel_calls']:4d} "
              f"{x['rss'] / 2**20:6.0f} {x['fit'] / G9:6.3f} {x['learn'] / G9:6.3f}")
    print("epistemic safety per k: certified | HOV | certified-but-held-out-fail | silent raw / guarded (of inputs on certified tasks) | "
          "correct unique answers raw / guarded")
    for a, x in t["arms"].items():
        for k, v in x["k"].items():
            print(f"  {a:31s} k={k}: {v['certified']:3d} {v['hov']:3d} {v['cbf']:3d}   {v['silent_raw']:3d} / {v['silent_guard']:3d} of {v['n_in']:4d}   "
                  f"{v['ans_raw']:4d} / {v['ans_guard']:4d}")


if __name__ == "__main__":
    k = sys.argv[1]
    if k == "track1":
        show_track1(track1(sys.argv[2:]))
    elif k == "track2":
        show_track2(track2(sys.argv[2]))
    else:
        show_track3(track3(sys.argv[2]))
