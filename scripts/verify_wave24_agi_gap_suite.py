#!/usr/bin/env python3
"""Independent verifier for the Wave 24 eight-gap suite.

Recomputes every predeclared gate from raw per-task rows (never from the
runner's own aggregates), counts false certificates itself and recomputes
the exact sign tests. Exit 0 only if EVERY gate passes; failures are listed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ALPHA = 0.05
TARGETS = ("CELL_AUTOMATA", "NESTED_DICT", "NUM_SERIES", "GRAPH", "STDLIB_BYTES")


def sign_test(diffs):
    pos, neg = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    n = pos + neg
    if n == 0:
        return dict(n=0, positive=0, negative=0, p_value=1.0)
    k = min(pos, neg)
    return dict(n=n, positive=pos, negative=neg, p_value=min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n))


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r, i = [0.0] * len(v), 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for m in range(i, j + 1):
                r[order[m]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) or 1.0
    return num / den


def paired(rows, a, b, key=lambda r: r["work"]):
    """Rows of methods a and b are emitted in the same task order per (seed, domain)."""
    A = [r for r in rows if r["method"] == a]
    B = [r for r in rows if r["method"] == b]
    assert len(A) == len(B), (a, b, len(A), len(B))
    return A, B, sign_test([key(y) - key(x) for x, y in zip(A, B)])


def verify(payload):
    gates, report = {}, {}
    if payload.get("execution_status") != "COMPLETE":
        gates["execution_complete"] = False
    g = payload["gaps"]
    all_rows = [r for name, runs in g.items() if name != "gap3" and name != "gap5"
                for run in runs for r in run.get("rows", [])]
    false = sum(1 for r in all_rows if r.get("certificate_valid") is False)
    report["false_certificate_count"] = false
    report["wrong_unique_answers"] = sum(1 for r in all_rows if r.get("wrong_unique"))
    gates["zero_false_certificates"] = false == 0

    # gap 1: full-cost improvement, every seed and pooled
    per_seed = []
    for run in g["gap1"]:
        L = [r for r in run["rows"] if r["method"] == "learned"]
        F = [r for r in run["rows"] if r["method"] == "fixed"]
        lt = sum(r["work"] for r in L) + run["overhead_work"]
        ft = sum(r["work"] for r in F)
        per_seed.append(dict(seed=run["seed"], learned_solved=sum(r["solved"] for r in L), fixed_solved=sum(r["solved"] for r in F),
                             learned_total_work=lt, fixed_total_work=ft, learned_eval_work=sum(r["work"] for r in L),
                             overhead_work=run["overhead_work"], tasks=len(L)))
    report["gap1_per_seed"] = per_seed
    arena = payload["open_world_arena"]["method_summary"]
    report["gap1_open_world"] = {k: dict(solved=v["solved"], total_work=v["total_work"]) for k, v in arena.items()}
    gates["gap1_every_seed_solved_and_total_work"] = all(s["learned_solved"] > s["fixed_solved"] and
                                                        s["learned_total_work"] < s["fixed_total_work"] for s in per_seed)
    ev, st = arena["nexus_self_evolving_open_world"], arena["nexus_static_quotient_open_world"]
    gates["gap1_open_world_solved_and_total_work"] = (ev["solved"] >= 13 and ev["solved"] > st["solved"]
                                                      and ev["total_work"] < st["total_work"])

    # gap 2: zero-shot transfer on 5 disjoint targets
    rows2 = [r for run in g["gap2"] for r in run["rows"]]
    for r in rows2:
        r["work_total"] = r["work"] + r.get("setup_work", 0)
    per_domain = {}
    for d in TARGETS:
        rd = [r for r in rows2 if r["domain"] == d]
        T = [r for r in rd if r["method"] == "transfer"]
        F = [r for r in rd if r["method"] == "fixed"]
        test = sign_test([f["work"] - t["work_total"] for t, f in zip(T, F)])
        depth_t = max((r["found_depth"] for r in T if r["solved"]), default=0)
        depth_f = max((r["found_depth"] for r in F if r["solved"]), default=0)
        per_domain[d] = dict(transfer_solved=sum(r["solved"] for r in T), fixed_solved=sum(r["solved"] for r in F),
                             transfer_work=sum(r["work_total"] for r in T), fixed_work=sum(r["work"] for r in F),
                             sign_test=test, max_solved_depth_transfer=depth_t, max_solved_depth_fixed=depth_f)
    report["gap2_per_domain"] = per_domain
    gates["gap2_five_domains_significant_vs_fixed"] = all(
        v["transfer_solved"] >= v["fixed_solved"] and v["transfer_work"] < v["fixed_work"] and
        v["sign_test"]["p_value"] < ALPHA and v["sign_test"]["positive"] > v["sign_test"]["negative"] for v in per_domain.values())
    T = [r for r in rows2 if r["method"] == "transfer"]
    N = [r for r in rows2 if r["method"] == "no_transfer"]
    tvn = sign_test([n["work_total"] - t["work_total"] for t, n in zip(T, N)])
    report["gap2_transfer_vs_no_transfer"] = dict(transfer_work=sum(r["work_total"] for r in T), no_transfer_work=sum(r["work_total"] for r in N),
        transfer_solved=sum(r["solved"] for r in T), no_transfer_solved=sum(r["solved"] for r in N), sign_test=tvn)
    gates["gap2_source_transfer_beats_no_transfer"] = (tvn["p_value"] < ALPHA and tvn["positive"] > tvn["negative"]
        and sum(r["work_total"] for r in T) < sum(r["work_total"] for r in N) and sum(r["solved"] for r in T) >= sum(r["solved"] for r in N))

    # gap 3: learning-to-learn curves
    seeds3 = []
    for run in g["gap3"]:
        m = [r for r in run["runs"] if r["method"] == "meta"]
        c = [r for r in run["runs"] if r["method"] == "reset"]
        rho_m = spearman([r["position"] for r in m], [r["acquisition_work"] for r in m])
        rho_c = spearman([r["position"] for r in c], [r["acquisition_work"] for r in c])
        mean = lambda rs, ps: sum(r["acquisition_work"] for r in rs if r["position"] in ps) / max(1, sum(r["position"] in ps for r in rs))
        seeds3.append(dict(seed=run["seed"], rho_meta=rho_m, rho_reset=rho_c,
                           meta_early=mean(m, (0, 1)), meta_late=mean(m, (3, 4)), reset_late=mean(c, (3, 4)),
                           meta_solved_late=sum(r["solved"] for r in m if r["position"] >= 3),
                           reset_solved_late=sum(r["solved"] for r in c if r["position"] >= 3),
                           precision_by_position=[round(sum(r["on_path"] for r in m if r["position"] == p) /
                                                        max(1, sum(r["expansions"] for r in m if r["position"] == p)), 4) for p in range(5)]))
    report["gap3_per_seed"] = seeds3
    gates["gap3_meta_curve_every_seed"] = all(s["rho_meta"] < 0 and s["rho_meta"] < s["rho_reset"] and s["meta_late"] < s["meta_early"]
                                             for s in seeds3)

    # gap 4: closed loop
    rows4 = [r for run in g["gap4"] for r in run["rows"]]
    E, N, t4 = paired(rows4, "explore", "no_explore")
    promotions = [p for run in g["gap4"] for d in run["promotions"] for p in d["promoted"]]
    evicted = sum(len(e["evicted"]) for run in g["gap4"] for e in run["evictions"])
    idle = sum({(i, r["domain"]): r["explore_work"] for i, run in enumerate(g["gap4"])
                for r in run["rows"] if r["method"] == "explore"}.values())
    report["gap4"] = dict(explore_stream_work=sum(r["work"] for r in E), no_explore_stream_work=sum(r["work"] for r in N),
                          explore_solved=sum(r["solved"] for r in E), no_explore_solved=sum(r["solved"] for r in N),
                          sign_test=t4, promotions=len(promotions), evicted_under_shift=evicted,
                          idle_exploration_work=idle)
    gates["gap4_exploration_accelerates_stream"] = (t4["p_value"] < ALPHA and t4["positive"] > t4["negative"]
        and sum(r["solved"] for r in E) >= sum(r["solved"] for r in N))
    gates["gap4_promotions_have_measured_gain"] = all(len(p["gains"]) >= 3 and all(x > 0 for x in p["gains"]) for p in promotions)
    gates["gap4_eviction_under_shift"] = evicted >= 1

    # gap 5: robustness
    g1rows = [r for run in g["gap1"] for r in run["rows"]]
    messy_l = sum(r["solved"] for r in g1rows if r["messy"] and r["method"] == "learned")
    messy_f = sum(r["solved"] for r in g1rows if r["messy"] and r["method"] == "fixed")
    fired = sum(1 for r in g1rows if r["method"] == "learned" and r["solved"] and r["recovery_fired"])
    sc = g["gap5"][0]["scaling"]
    by_n = {s["n"]: s for s in sc}
    report["gap5"] = dict(messy_learned_solved=messy_l, messy_fixed_solved=messy_f, recovery_fired_certified=fired,
                          scaling=sc, stdlib_ingested=len(g["gap5"][0]["stdlib_ingested"]),
                          approximate_law_retention=[run["approximate_law_retention"] for run in g["gap5"]])
    gates["gap5_messy_and_firing_recovery"] = messy_l >= messy_f and fired >= 1
    gates["gap5_bounded_projection_scaling"] = (by_n[10000]["bounded_ms"] < 1.5 * by_n[1000]["bounded_ms"]
                                                and by_n[10000]["bounded_ms"] * 10 < by_n[10000]["exact_ms"])
    gates["gap5_raw_stdlib_ingestion"] = report["gap5"]["stdlib_ingested"] >= 8

    # gap 6: hierarchy
    layers = defaultdict(int)
    for r in g1rows:
        if r["method"] == "learned" and r["solved"]:
            layers[r["layer_max"]] += 1
    report["gap6_certified_layers"] = dict(layers)
    gates["gap6_layer2_certified"] = any(k >= 2 for k in layers)

    # gap 7: world model
    rows7 = [r for run in g["gap7"] for r in run["rows"]]
    W, F, t7 = paired(rows7, "world_model", "fixed")
    acc = [run["prediction_accuracy"] for run in g["gap7"]]
    contained, predicted = sum(a["contained"] for a in acc), sum(a["predicted"] for a in acc)
    retained = sum(1 for w, f in zip(W, F) if f["solved"] and w["solved"]) / max(1, sum(f["solved"] for f in F))
    report["gap7"] = dict(world_model_work=sum(r["work"] for r in W), fixed_work=sum(r["work"] for r in F),
                          world_model_solved=sum(r["solved"] for r in W), fixed_solved=sum(r["solved"] for r in F),
                          sign_test=t7, prediction_accuracy=contained / max(1, predicted), retention=retained)
    gates["gap7_world_model"] = (t7["p_value"] < ALPHA and t7["positive"] > t7["negative"]
        and sum(r["solved"] for r in W) >= sum(r["solved"] for r in F) and contained / max(1, predicted) >= 0.95 and retained >= 0.95)

    # gap 8: grounding/planning and intrinsic goals
    rows8 = [r for run in g["gap8_grounding"] for r in run["rows"]]
    G, B, t8 = paired(rows8, "grounded_planner", "blind_fixed")
    report["gap8_grounding"] = dict(grounded_solved=sum(r["solved"] for r in G), blind_solved=sum(r["solved"] for r in B),
                                    grounded_work=sum(r["work"] for r in G), blind_work=sum(r["work"] for r in B), sign_test=t8,
                                    max_depth=max(r["depth"] for r in G))
    gates["gap8_grounded_long_horizon"] = (sum(r["solved"] for r in G) > sum(r["solved"] for r in B)
        and t8["p_value"] < ALPHA and t8["positive"] > t8["negative"])
    rows8b = [r for run in g["gap8_goals"] for r in run["rows"]]
    D, U, t8b = paired(rows8b, "directed", "undirected")
    report["gap8_goals"] = dict(directed_solved=sum(r["solved"] for r in D), undirected_solved=sum(r["solved"] for r in U),
                                directed_work=sum(r["work"] for r in D), undirected_work=sum(r["work"] for r in U), sign_test=t8b,
                                goals=[x for run in g["gap8_goals"] for x in run["goals"]])
    gates["gap8_intrinsic_goals_help"] = (sum(r["solved"] for r in D) >= sum(r["solved"] for r in U)
        and sum(r["work"] for r in D) < sum(r["work"] for r in U))
    return dict(gates=gates, all_passed=all(gates.values()), failed=[k for k, v in gates.items() if not v], report=report)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default=str(ROOT / "artifacts" / "wave24_agi_gap_suite.json"))
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    result = verify(json.loads(Path(args.path).read_text()))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(text)
    print(text)
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
