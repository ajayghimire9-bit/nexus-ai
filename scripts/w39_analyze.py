"""Wave 39 analysis (NOT LOCKED): turns raw rows into the reported tables. Pure post-processing; no task is re-run.
Cost-vs-coverage: caps 0.25x / 0.5x / 1x / 2x of 2M executions per search, read from the 2x run (w39_eval.at_cap: solved work
exact, unsolved-at-cap work a linear estimate). Matched quality: work on the intersection of tasks solved by every compared arm,
and each arm's work at the smallest cap where it reaches the strongest control's solve count."""
import json, sys
sys.path.insert(0, "src")
from nexus.w39_eval import at_cap
CAPS = (0.25, 0.5, 1.0, 2.0)
B = 2_000_000


def prose_tables(path, arms=("Fresh-v4", "Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Repr-core-v5", "Online-hier-v5")):
    r = json.load(open(path))
    T = r["tasks"]
    out = {"n_tasks": len(T), "by_split": {}}
    for sub in sorted({v["split"] for v in T.values()}) + ["all"]:
        names = [n for n, v in T.items() if sub == "all" or v["split"] == sub]
        rows = {}
        for arm in arms:
            rs = [T[n].get(arm, {}) for n in names]
            ev = [x for x in rs if x.get("label") not in ("NOT_EVALUABLE", "SKIPPED_FORMAT", None)]
            inputs = [i for x in ev for i in x.get("inputs", [])]
            rows[arm] = dict(
                evaluable=len(ev), certified=sum(bool(x.get("certified")) for x in ev),
                held_out_verified=sum(bool(x.get("held_out_verified")) for x in ev),
                certified_but_heldout_fail=sum(bool(x.get("certified")) and not x.get("held_out_verified") for x in ev),
                query_wrong_certified=sum(bool(x.get("wrong")) for x in ev),
                warned=sum("UNDER_SPECIFIED_WARNING" in (x.get("warnings") or []) for x in ev if x.get("certified")),
                answered_uncertified_heldout_pass=sum(x.get("heldout_pass") == 1.0 and not x.get("certified") for x in ev),
                inputs=len(inputs), wrong_inputs=sum(not i["ok"] for i in inputs),
                silent_failures=sum((not i["ok"]) and i["unique"] for i in inputs),
                silent_failures_v4_contract=sum(not i["ok"] for i in inputs),
                work_G=round(sum(x.get("work", 0) for x in rs) / 1e9, 2),
                curve={str(c): dict(held_out_verified=sum(at_cap(x, c * B)["solved"] and bool(x.get("held_out_verified")) for x in ev
                                                          if x.get("iters") is not None or x.get("label") == "ABSTAIN"),
                                    work_G=round(sum(at_cap(x, c * B)["work"] for x in ev if "work" in x) / 1e9, 2)) for c in CAPS})
        out["by_split"][sub] = rows
    v5 = [a for a in arms if a.endswith("v5") and a != "Online-hier-v5"]
    names = [n for n in T if all(T[n].get(a, {}).get("held_out_verified") for a in v5)]
    out["intersection"] = dict(n=len(names), work_G={a: round(sum(T[n][a]["work"] for n in names) / 1e9, 3) for a in v5})
    return out


def show_prose(t):
    for sub, rows in t["by_split"].items():
        print(f"\n[{sub}]  arm | evaluable | certified | HELD_OUT_VERIFIED | certified-but-held-out-fail | warned | uncertified-but-pass"
              " | silent fail (v5 contract / v4 contract) | work G | HOV@0.25x/0.5x/1x/2x")
        for arm, x in rows.items():
            c = x["curve"]
            print(f"  {arm:15s} {x['evaluable']:3d} {x['certified']:3d} {x['held_out_verified']:3d} {x['certified_but_heldout_fail']:3d} "
                  f"{x['warned']:3d} {x['answered_uncertified_heldout_pass']:3d}   {x['silent_failures']:3d}/{x['silent_failures_v4_contract']:3d} of {x['inputs']:4d}"
                  f"  {x['work_G']:8.1f}   " + "/".join(str(c[k]["held_out_verified"]) for k in c))
    print("\nintersection (HOV by all v5 arms):", t["intersection"])


if __name__ == "__main__":
    show_prose(prose_tables(sys.argv[1]))


# --------------------------------------------------------------------------- internal folds
def lodo_tables(paths, arms=("Fresh-v5", "Placebo-v5", "Fixed-v5", "Repr-v5", "Repr-core-v5")):
    seeds = {}
    for pth in paths:
        r = json.load(open(pth))
        seeds[pth] = {h: f for h, f in r.items() if not h.startswith("_")}
    fit_of = {"Placebo-v5": "Placebo-v5", "Repr-v5": "Repr-v5", "Repr-core-v5": "Repr-core-v5"}
    per_seed, pooled = {}, {a: dict(correct=0, n=0, wrong=0, work=0, fit=0, curve={str(c): [0, 0] for c in CAPS}) for a in arms}
    src_work = src_core_work = 0
    inter = {a: 0 for a in arms}; n_inter = 0
    for pth, folds in seeds.items():
        ps = {}
        for a in arms:
            rows = [x for f in folds.values() for x in f["arms"][a]]
            fit = sum(f["fit_instr"].get(fit_of.get(a, ""), 0) for f in folds.values())
            ps[a] = dict(correct=sum(x["correct"] for x in rows), n=len(rows), wrong=sum(x["wrong"] for x in rows),
                         work=sum(x["work"] for x in rows), fit=fit)
            P = pooled[a]
            for k in ("correct", "n", "wrong", "work", "fit"):
                P[k] += ps[a][k]
            for c in CAPS:
                rs = [at_cap(x, c * B) for x in rows]
                P["curve"][str(c)][0] += sum(1 for x, y in zip(rows, rs) if y["solved"] and x["correct"])
                P["curve"][str(c)][1] += sum(y["work"] for y in rs)
        per_seed[pth] = ps
        for f in folds.values():
            src_work += f["source"]["work"]
            if "mech_by_task" in f["source"]:
                seen = set()
                for w, m, c in zip(f["source"]["work_by_task"], f["source"]["mech_by_task"], f["source"]["cert_by_task"]):
                    if tuple(m) not in seen:
                        src_core_work += w
                        if c:
                            seen.add(tuple(m))
            else:
                src_core_work += f["source"]["work"] / 2           # dev artifacts before the field existed: estimate
            n = len(f["arms"][arms[0]])
            for j in range(n):
                if all(f["arms"][a][j]["correct"] for a in arms):
                    n_inter += 1
                    for a in arms:
                        inter[a] += f["arms"][a][j]["work"]
    return dict(per_seed=per_seed, pooled=pooled, source_work=src_work, source_core_work=src_core_work,
                intersection=dict(n=n_inter, work=inter))


def show_lodo(t, primary="Repr-v5", controls=("Fresh-v5", "Placebo-v5", "Fixed-v5")):
    P = t["pooled"]
    print("arm | solved/n | wrong | target work G | fit G | work incl fit G | solved@0.25x/0.5x/1x/2x | work G @caps")
    for a, x in P.items():
        print(f"  {a:13s} {x['correct']:3d}/{x['n']:3d} {x['wrong']:2d} {x['work'] / 1e9:9.1f} {x['fit'] / 1e9:6.3f} {(x['work'] + x['fit']) / 1e9:9.1f}  "
              + "/".join(str(x["curve"][k][0]) for k in x["curve"]) + "  " + "/".join(f"{x['curve'][k][1] / 1e9:.0f}" for k in x["curve"]))
    I = t["intersection"]
    print(f"intersection (solved by all arms): n={I['n']}  " + "  ".join(f"{a} {w / 1e9:.1f}G" for a, w in I["work"].items()))
    for c in controls:
        r_all = (P[primary]["work"] + P[primary]["fit"]) / P[c]["work"] if c == "Fresh-v5" or c == "Fixed-v5" else \
            (P[primary]["work"] + P[primary]["fit"]) / (P[c]["work"] + P[c]["fit"])
        r_int = I["work"][primary] / I["work"][c] if I["work"][c] else float("nan")
        wins = sum(1 for ps in t["per_seed"].values() if ps[primary]["work"] + ps[primary]["fit"] < ps[c]["work"] + ps[c]["fit"]
                   and ps[primary]["correct"] >= ps[c]["correct"])
        print(f"  {primary} vs {c}: total ratio (fit charged) {r_all:.3f} | intersection ratio {r_int:.3f} | solves {P[primary]['correct']} vs "
              f"{P[c]['correct']} | seeds won (cheaper AND solves >=) {wins}/{len(t['per_seed'])}")
    saving = (P["Fresh-v5"]["work"] - P[primary]["work"]) / max(1, P[primary]["n"])
    extra = t["source_work"] + P[primary]["fit"]
    print(f"source accounting: mandatory-work (marginal fit) {P[primary]['fit'] / 1e9:.3f}G | extra-curriculum {extra / 1e9:.0f}G | "
          f"saving per target task {saving / 1e9:.2f}G | break-even {extra / saving if saving > 0 else float('inf'):.0f} target tasks")
    if "Repr-core-v5" in P:
        sc = (P["Fresh-v5"]["work"] - P["Repr-core-v5"]["work"]) / max(1, P["Repr-core-v5"]["n"])
        ex = t["source_core_work"] + P["Repr-core-v5"]["fit"]
        print(f"core set: extra-curriculum {ex / 1e9:.0f}G | saving per task {sc / 1e9:.2f}G | break-even "
              f"{ex / sc if sc > 0 else float('inf'):.0f} target tasks")
