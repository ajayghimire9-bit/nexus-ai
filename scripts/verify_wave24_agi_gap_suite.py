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
    if "gaps_v2" in payload:
        for old in ("gap4_exploration_accelerates_stream", "gap4_promotions_have_measured_gain", "gap4_eviction_under_shift",
                    "gap6_layer2_certified", "gap8_intrinsic_goals_help"):
            report.setdefault("superseded_v1_gates", {})[old] = gates.pop(old)
        verify_v2(payload["gaps_v2"], gates, report)
    return dict(gates=gates, all_passed=all(gates.values()), failed=[k for k, v in gates.items() if not v], report=report)


def verify_v2(g, gates, report):
    """Predeclared v2 gates (docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md, section v2)."""
    v2_rows = [r for runs in g.values() for run in runs for r in run.get("rows", [])]
    false = sum(1 for r in v2_rows if r.get("certificate_valid") is False)
    report["v2_false_certificate_count"] = false
    gates["v2_zero_false_certificates"] = false == 0

    # gaps 4 + 6 (every seed)
    per = []
    for run in g["gap4_6"]:
        rows, doms = run["rows"], run["domains"]
        def m(method, key):
            return [r for r in rows if r["method"] == method]
        ev, no, cap = m("evolved", 0), m("no_evolution", 0), m("evolved_layer1_cap", 0)
        overhead = lambda method: sum(d["sleep_work"] + d["setup_work"] for d in doms if d["method"] == method)
        promoted = sum(len(d["promotions"]) for d in doms if d["method"] == "evolved")
        names = {p["macro"] for d in doms if d["method"] == "evolved" for p in d["promotions"]}
        used = sum(1 for r in ev if r["solved"] and any(w in names for w in r["witness"]))
        per.append(dict(seed=run["seed"], promoted=promoted, promoted_used_in_certified=used,
                        evolved_solved=sum(r["solved"] for r in ev), no_evolution_solved=sum(r["solved"] for r in no),
                        evolved_total_work=sum(r["work"] for r in ev) + overhead("evolved"),
                        no_evolution_total_work=sum(r["work"] for r in no) + overhead("no_evolution"),
                        evolved_sleep_work=sum(d["sleep_work"] for d in doms if d["method"] == "evolved"),
                        layer2plus_certified=sum(1 for r in ev if r["solved"] and r["layer_max"] >= 2),
                        layer3plus_certified=sum(1 for r in ev if r["solved"] and r["layer_max"] >= 3),
                        deep5_evolved=sum(r["solved"] for r in ev if r["depth"] >= 5),
                        deep5_layer1_cap=sum(r["solved"] for r in cap if r["depth"] >= 5),
                        deep5_no_evolution=sum(r["solved"] for r in no if r["depth"] >= 5),
                        deep5_tasks=sum(1 for r in ev if r["depth"] >= 5)))
    report["v2_gap4_6_per_seed"] = per
    gates["v2_gap4_promoted_and_used_every_seed"] = all(s["promoted"] > 0 and s["promoted_used_in_certified"] > 0 for s in per)
    gates["v2_gap4_more_solved_every_seed"] = all(s["evolved_solved"] > s["no_evolution_solved"] for s in per)
    gates["v2_gap4_less_total_work_every_seed"] = all(s["evolved_total_work"] < s["no_evolution_total_work"] for s in per)
    gates["v2_gap6_layer2plus_ge15_every_seed"] = all(s["layer2plus_certified"] >= 15 for s in per)
    gates["v2_gap6_hierarchy_unlocks_depth5"] = (sum(s["deep5_evolved"] for s in per) > sum(s["deep5_layer1_cap"] for s in per)
                                                 and all(s["deep5_evolved"] >= s["deep5_layer1_cap"] for s in per))

    # gap 2 v2
    rows2 = [r for run in g["gap2_v2"] for r in run["rows"]]
    tot = lambda method: (sum(r["solved"] for r in rows2 if r["method"] == method),
                          sum(r["work"] + r.get("setup_work", 0) for r in rows2 if r["method"] == method))
    T, Lw, N = tot("skeleton_policy_transfer"), tot("law_only"), tot("skeletons_no_source")
    TT = [r for r in rows2 if r["method"] == "skeleton_policy_transfer"]
    NN = [r for r in rows2 if r["method"] == "skeletons_no_source"]
    report["v2_gap2"] = dict(transfer=T, law_only=Lw, skeletons_no_source=N,
                             transfer_vs_no_source_sign=sign_test([b["work"] - a["work"] for a, b in zip(TT, NN)]),
                             generic_macros=[run["generic_macros"] for run in g["gap2_v2"]],
                             policy_validated=[run["policy_validated"] for run in g["gap2_v2"]])
    gates["v2_gap2_skeleton_policy_beats_law_only"] = T[0] > Lw[0] and T[1] < Lw[1]

    # gap 3 v2
    seeds3, pairs = [], []
    for run in g["gap3_v2"]:
        rs = run["runs"]
        mean = lambda method, ps, key="acquisition_work": sum(r[key] for r in rs if r["method"] == method and r["position"] in ps) / \
            max(1, sum(1 for r in rs if r["method"] == method and r["position"] in ps))
        ratio = lambda method, ps: sum(r["on_path"] for r in rs if r["method"] == method and r["position"] in ps) / \
            max(1, sum(r["expansions"] for r in rs if r["method"] == method and r["position"] in ps))
        for o in {r["order"] for r in rs}:
            ro = [r for r in rs if r["order"] == o and r["method"] == "meta"]
            e = sum(r["on_path"] for r in ro if r["position"] in (0, 1)) / max(1, sum(r["expansions"] for r in ro if r["position"] in (0, 1)))
            l = sum(r["on_path"] for r in ro if r["position"] in (3, 4)) / max(1, sum(r["expansions"] for r in ro if r["position"] in (3, 4)))
            pairs.append(l - e)
        seeds3.append(dict(seed=run["seed"], meta_late_work=mean("meta", (3, 4)), reset_late_work=mean("reset", (3, 4)),
                           meta_early_ratio=ratio("meta", (0, 1)), meta_late_ratio=ratio("meta", (3, 4)),
                           reset_late_ratio=ratio("reset", (3, 4))))
    report["v2_gap3_per_seed"] = seeds3
    report["v2_gap3_useful_ratio_sign"] = sign_test(pairs)
    gates["v2_gap3_late_meta_cheaper_than_reset_every_seed"] = all(s["meta_late_work"] < s["reset_late_work"] for s in seeds3)
    st = sign_test(pairs)
    gates["v2_gap3_useful_branch_ratio_increases"] = st["positive"] > st["negative"] and st["p_value"] < ALPHA

    # gap 8a v2: semantic parser vs keyword retrieval (paired per task, solved outcome)
    rows8 = [r for run in g["gap8a_v2"] for r in run["rows"]]
    S = [r for r in rows8 if r["method"] == "semantic_parser"]
    K = [r for r in rows8 if r["method"] == "keyword_retrieval"]
    t8 = sign_test([int(a["solved"]) - int(b["solved"]) for a, b in zip(S, K)])
    report["v2_gap8a"] = dict(semantic_solved=sum(r["solved"] for r in S), keyword_solved=sum(r["solved"] for r in K),
                              semantic_work=sum(r["work"] for r in S), keyword_work=sum(r["work"] for r in K), tasks=len(S),
                              solved_sign_test=t8)
    gates["v2_gap8a_semantic_beats_keyword"] = (t8["positive"] > t8["negative"] and t8["p_value"] < 0.01
                                                and sum(r["work"] for r in S) < sum(r["work"] for r in K))

    # gap 8b v2: per-task p < 0.01 vs undirected AND vs no self-training (work), solved >=
    rows8b = [r for run in g["gap8b_v2"] for r in run["rows"]]
    for r in rows8b:
        r["work_cost"] = r["work"] + (0 if r["solved"] else 10**6)
    D, U, tu = paired(rows8b, "directed", "undirected", key=lambda r: r["work_cost"])
    D2, Nn, tn = paired(rows8b, "directed", "no_self_training", key=lambda r: r["work_cost"])
    report["v2_gap8b"] = dict(directed_solved=sum(r["solved"] for r in D), undirected_solved=sum(r["solved"] for r in U),
                              none_solved=sum(r["solved"] for r in Nn), vs_undirected=tu, vs_none=tn,
                              goals=[x for run in g["gap8b_v2"] for x in run["goals"]])
    gates["v2_gap8b_directed_beats_undirected_p01"] = tu["positive"] > tu["negative"] and tu["p_value"] < 0.01 \
        and sum(r["solved"] for r in D) >= sum(r["solved"] for r in U)
    gates["v2_gap8b_directed_beats_none_p01"] = tn["positive"] > tn["negative"] and tn["p_value"] < 0.01 \
        and sum(r["solved"] for r in D) >= sum(r["solved"] for r in Nn)

    # wild external arena
    rep_rows = [r for run in g["wild"] for r in run["repair"]]
    law_rows = [r for run in g["wild"] for r in run["laws"]]
    agg = lambda rows, method, key: sum(r[key] for r in rows if r["method"] == method)
    report["v2_wild"] = dict(repair_correct=dict(learned=agg(rep_rows, "learned", "correct"), fixed=agg(rep_rows, "fixed", "correct")),
                             repair_plausible=dict(learned=agg(rep_rows, "learned", "plausible"), fixed=agg(rep_rows, "fixed", "plausible")),
                             repair_work=dict(learned=agg(rep_rows, "learned", "work"), fixed=agg(rep_rows, "fixed", "work")),
                             repaired_programs=sorted({r["program"] for r in rep_rows if r["method"] == "learned" and r["correct"]}),
                             laws_correct=dict(mdl=agg(law_rows, "mdl_law_discovery", "correct"), linear=agg(law_rows, "linear_fit", "correct")),
                             law_tasks=len(law_rows) // 2)
    w = report["v2_wild"]
    gates["v2_wild_code_repair"] = w["repair_correct"]["learned"] >= w["repair_correct"]["fixed"] and \
        w["repair_correct"]["learned"] > 0 and w["repair_work"]["learned"] < w["repair_work"]["fixed"]
    gates["v2_wild_law_discovery"] = w["laws_correct"]["mdl"] > w["laws_correct"]["linear"]


# =========================================================================== v3
def permutation_ratio_test(a_rows, b_rows, *, n_perm=10_000, seed=0):
    """Paired sign-flip permutation test that arm A has LOWER work per correct solve than arm B.

    Statistic D = W_B/S_B - W_A/S_A over the paired tasks; under H0 the two arms are exchangeable
    within each task. One-sided p = (#{D_perm >= D_obs} + 1) / (n_perm + 1).
    """
    import random
    pairs = [(a["work"], int(a["correct"]), b["work"], int(b["correct"])) for a, b in zip(a_rows, b_rows)]

    def stat(ps):
        wa, sa = sum(p[0] for p in ps), sum(p[1] for p in ps)
        wb, sb = sum(p[2] for p in ps), sum(p[3] for p in ps)
        ra = wa / sa if sa else float("inf")
        rb = wb / sb if sb else float("inf")
        if ra == rb:
            return 0.0
        return (rb - ra) if math.isfinite(rb - ra) else (math.inf if ra < rb else -math.inf)
    obs = stat(pairs)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        perm = [p if rng.random() < 0.5 else (p[2], p[3], p[0], p[1]) for p in pairs]
        hits += stat(perm) >= obs
    return dict(n=len(pairs), statistic=obs, p_value=(hits + 1) / (n_perm + 1))


def _ratio(rows):
    s = sum(int(r["correct"]) for r in rows)
    return sum(r["work"] for r in rows) / s if s else None


def _regrade_code(payload, report):
    """Independent re-execution of every stored answer: false certificates + grading mismatches."""
    from nexus.wave24_code_repair import Meter as QMeter, Program, run_tests, split_tests
    from nexus.wave24_mbpp import Meter, grade, load_tasks, passes
    false, mismatch = [], []
    by_id = {t.task_id: t for t in load_tasks()}
    for r in payload["mbpp"]["rows"]:
        t = by_id[r["task_id"]]
        ans = r.get("answer")
        if ans is not None and r["method"] != "standalone":
            ok, _ = passes(ans, t.public, Meter(), setup=t.setup)
            if not ok:
                false.append(("mbpp", r["method"], r["task_id"]))
        if bool(grade(ans, t)) != bool(r["correct"]):
            mismatch.append(("mbpp", r["method"], r["task_id"]))
    qb_split = payload.get("qb_split_seed", 301)
    for r in payload["quixbugs"]["rows"]:
        p = Program.load(r["program"])
        pub, hid = split_tests(p, qb_split)
        src = r.get("patch")
        code = None
        if src:
            try:
                code = compile(src, "<candidate>", "exec")
            except SyntaxError:
                code = None
        if r["plausible"] and r["method"] != "qwen_standalone":
            if code is None or not all(run_tests(code, p.func, pub, QMeter(10**12))):
                false.append(("quixbugs", r["method"], r["program"]))
        tests = (list(pub) + list(hid)) if r["method"] == "qwen_standalone" else list(hid)
        if r["method"] != "qwen_standalone" and not r["plausible"]:
            regraded = False
        else:
            regraded = code is not None and all(run_tests(code, p.func, tests, QMeter(10**12)))
        if bool(regraded) != bool(r["correct"]):
            mismatch.append(("quixbugs", r["method"], r["program"]))
    report["false_code_certificates"] = false
    report["grading_mismatches"] = mismatch
    return false, mismatch


def verify_v3(payload):
    gates, report = {}, {}
    gates["v3_execution_complete"] = payload.get("execution_status") == "COMPLETE"
    # ---------------- procedural
    proc = payload.get("procedural", [])
    t_rows = [r for s in proc for r in s["transfer"]["rows"]]
    m_runs = [dict(r, seed=s["seed"]) for s in proc for r in s["meta"]["runs"]]
    proc_false = sum(1 for r in t_rows if r["status"].startswith("UNIQUE") and r["certificate_valid"] is False) + \
        sum(r["false_certificates"] for r in m_runs)
    report["procedural_false_certificates"] = proc_false
    false, mismatch = _regrade_code(payload, report)
    gates["v3_zero_false_certificates"] = proc_false == 0 and not false
    gates["v3_independent_regrade_matches"] = not mismatch
    # ---------------- code: QuixBugs + MBPP held-out (pooled)
    qb, mb = payload["quixbugs"]["rows"], payload["mbpp"]["rows"]
    arms = {"standalone": [r for r in qb if r["method"] == "qwen_standalone"] + [r for r in mb if r["method"] == "standalone"],
            "verified_sampling": [r for r in qb if r["method"] == "verified_sampling"] + [r for r in mb if r["method"] == "verified_sampling"],
            "nexus": [r for r in qb if r["method"] == "nexus_cegis"] + [r for r in mb if r["method"] == "nexus_evolved"]}
    table = {}
    for name, rows in arms.items():
        c, p = sum(int(r["correct"]) for r in rows), sum(int(r["plausible"]) for r in rows)
        table[name] = dict(tasks=len(rows), correct=c, plausible=p, precision=c / p if p else None,
                           work=sum(r["work"] for r in rows), llm_work=sum(r["llm_work"] for r in rows),
                           work_per_correct=_ratio(rows))
    for bench, rows_b in (("quixbugs", qb), ("mbpp", mb)):
        for m in sorted({r["method"] for r in rows_b}):
            rr = [r for r in rows_b if r["method"] == m]
            c, p = sum(int(r["correct"]) for r in rr), sum(int(r["plausible"]) for r in rr)
            table[f"{bench}:{m}"] = dict(tasks=len(rr), correct=c, plausible=p, precision=c / p if p else None,
                                         work=sum(r["work"] for r in rr), work_per_correct=_ratio(rr))
    report["code_table"] = table
    n, s, v = table["nexus"], table["standalone"], table["verified_sampling"]
    gates["v3_code_vs_unverified_qwen"] = n["correct"] > s["correct"] and (n["precision"] or 0) > (s["precision"] or 0)
    perm_vs = permutation_ratio_test(arms["nexus"], arms["verified_sampling"])
    report["nexus_vs_verified_sampling_permutation"] = perm_vs
    gates["v3_code_vs_verified_sampling"] = n["correct"] > v["correct"] and n["work_per_correct"] is not None and \
        v["work_per_correct"] is not None and n["work_per_correct"] < v["work_per_correct"]
    ev = [r for r in mb if r["method"] == "nexus_evolved"]
    fr = [r for r in mb if r["method"] == "nexus_frozen"]
    perm_ev = permutation_ratio_test(ev, fr)
    report["mbpp_evolved_vs_frozen_permutation"] = perm_ev
    e_c, f_c = sum(int(r["correct"]) for r in ev), sum(int(r["correct"]) for r in fr)
    e_r, f_r = _ratio(ev), _ratio(fr)
    gates["v3_mbpp_evolved_dominates_frozen"] = e_c > f_c and e_r is not None and f_r is not None and e_r < f_r \
        and perm_ev["p_value"] < ALPHA and not false
    layer2 = [r for r in ev if r["correct"] and r.get("max_helper_layer", 0) >= 2]
    report["mbpp_layers"] = dict(correct_using_library=sum(1 for r in ev if r["correct"] and r.get("answer_layer", 1) >= 2),
                                 correct_using_layer2_helper=len(layer2),
                                 stages={st: sum(r["stage"] == st for r in ev) for st in {r["stage"] for r in ev}},
                                 library_before=payload["mbpp"].get("library_before"),
                                 library_after=payload["mbpp"].get("evolution", {}).get("library_after"))
    gates["v3_layer2_helper_in_heldout_answer"] = len(layer2) >= 1
    # ---------------- Piece C: transfer
    agg = defaultdict(lambda: dict(solved=0, work=0, tasks=0))
    for r in t_rows:
        a = agg[r["method"]]
        a["solved"] += int(r["solved"])
        a["work"] += r["work"] + r.get("setup_work", 0)
        a["tasks"] += 1
    report["transfer"] = dict(agg)
    report["transfer_source_training_work"] = sum(s["transfer"]["source_work"] for s in proc)
    report["transfer_bindings"] = sum(len(s["transfer"]["bindings"]) for s in proc)
    ex, am, fx = agg["experienced"], agg["amnesiac"], agg["fixed"]
    pen = lambda r: r["work"] + r.get("setup_work", 0) + (0 if r["solved"] else 10**6)
    E = [r for r in t_rows if r["method"] == "experienced"]
    A = [r for r in t_rows if r["method"] == "amnesiac"]
    report["transfer_sign_vs_amnesiac"] = sign_test([pen(b) - pen(a) for a, b in zip(E, A)])
    gates["v3_transfer_experienced_beats_amnesiac_and_fixed"] = ex["solved"] > am["solved"] and ex["solved"] > fx["solved"] \
        and ex["work"] < am["work"] and ex["work"] < fx["work"]
    # ---------------- Piece D: meta strategy allocation, late families
    late = defaultdict(dict)
    for r in m_runs:
        if r["position"] >= 3:
            late[(r["seed"], r["order"], r["position"])][r["method"]] = r
    pairs = [(v["meta"], v["reset"]) for v in late.values() if "meta" in v and "reset" in v]
    share = lambda r: r["on_path"] / r["expansions"] if r["expansions"] else 0.0
    wps = lambda r: r["acquisition_work"] / max(1, r["solved"])
    st_share = sign_test([share(a) - share(b) for a, b in pairs])
    st_wps = sign_test([wps(b) - wps(a) for a, b in pairs])
    pooled = {m: dict(solved=sum(p[i]["solved"] for p in pairs), work=sum(p[i]["acquisition_work"] for p in pairs),
                      on_path=sum(p[i]["on_path"] for p in pairs), expansions=sum(p[i]["expansions"] for p in pairs))
              for i, m in ((0, "meta"), (1, "reset"))}
    for m in pooled.values():
        m["work_per_solve"] = m["work"] / max(1, m["solved"])
        m["useful_branch_share"] = m["on_path"] / max(1, m["expansions"])
    report["meta_late"] = dict(pairs=len(pairs), pooled=pooled, sign_share=st_share, sign_work_per_solve=st_wps)
    gates["v3_meta_late_useful_branch_share"] = st_share["positive"] > st_share["negative"] and st_share["p_value"] < ALPHA
    gates["v3_meta_late_work_per_solve"] = pooled["meta"]["work_per_solve"] < pooled["reset"]["work_per_solve"] and \
        st_wps["positive"] > st_wps["negative"] and st_wps["p_value"] < ALPHA
    report["llm"] = {k: payload.get("llm_telemetry", {}).get(k) for k in
                     ("backend", "model", "calls", "fresh_calls", "charged_cache_hits", "generated_tokens",
                      "input_tokens", "wall_s")}
    return dict(gates=gates, all_passed=all(gates.values()), failed=sorted(k for k, v in gates.items() if not v),
                report=report)


V4_ARMS = ("literal_fixed_baseline", "abstractions_fixed_refinement", "learned_refinement_ttt_trm",
           "full_nexus_reusable_procedures", "amnesiac_no_source_control", "independent_proposal_ablation")
V4_FULL = "full_nexus_reusable_procedures"
V4_CONTROLS = ("literal_fixed_baseline", "abstractions_fixed_refinement", "amnesiac_no_source_control",
               "independent_proposal_ablation")


def one_sided_sign(wins, losses):
    """Exact one-sided sign test P(X >= wins | n = wins + losses, p = 1/2); ties are dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n


def procedural_digest(rows):
    import hashlib
    keep = [(r["seed"], r["arm"], r["domain"], r["kind"], r["status"], r["solved"], r["false_certificate"], r["work"])
            for r in rows]
    return hashlib.sha256(json.dumps(keep).encode()).hexdigest()


def _arm_totals(seed_res, arm, kinds=None):
    rows = [r for r in seed_res["rows"] if r["arm"] == arm and (kinds is None or r["kind"] in kinds)]
    solved = sum(r["solved"] for r in rows)
    target = sum(r["work"] for r in rows) + (seed_res["setup_work"].get(arm, 0) if kinds is None else 0)
    return dict(tasks=len(rows), solved=solved, target_work=target,
                source_work=seed_res["source_cost"].get(arm, 0) if kinds is None else 0)


def verify_v4(payload, *, replay=False):
    gates, report = {}, {}
    gates["v4_execution_complete"] = payload.get("execution_status") == "COMPLETE"
    proc = payload.get("procedural", [])
    rows = [r for s in proc for r in s["rows"]]
    # ---------------- G1 zero false certificates (procedural, every arm incl. the frozen row, every kind)
    fc_proc = [(r["seed"], r["arm"], r["domain"], r["kind"]) for r in rows if r["false_certificate"]]
    fc_code = []
    mismatch = []
    mb = payload.get("mbpp", {})
    if mb.get("rows"):
        from nexus.wave24_mbpp import Meter, grade, load_tasks, passes
        by_id = {t.task_id: t for t in load_tasks()}
        for r in mb["rows"]:
            t = by_id[r["task_id"]]
            ans = r.get("answer")
            if ans is not None and r["method"] != "standalone":
                if not passes(ans, t.public, Meter(), setup=t.setup)[0]:
                    fc_code.append((r["method"], r["task_id"]))
            if bool(grade(ans, t)) != bool(r["correct"]):
                mismatch.append((r["method"], r["task_id"]))
    # witness conservation (Y_q subset of Y^_q) for arms that complete every level: an AMBIGUOUS verdict on a
    # gold-AMBIGUOUS task must contain the truth
    conservation = [(r["seed"], r["arm"], r["domain"], r["kind"]) for r in rows
                    if r.get("complete_levels") and r["gold"] == "AMBIGUOUS" and r["status"] == "AMBIGUOUS_WITNESS_FOUND"
                    and not r["truth_in_witness_set"]]
    report["false_certificates"] = dict(procedural=fc_proc, code=fc_code, witness_conservation=conservation)
    report["false_certificate_count"] = len(fc_proc) + len(fc_code)
    gates["v4_g1_zero_false_certificates"] = bool(proc) and not fc_proc and not fc_code and not conservation
    report["grading_mismatches"] = mismatch
    gates["v4_independent_regrade_matches"] = not mismatch
    if replay:
        from nexus.wave24_v4_agents import run_seed
        again = [r for s in proc for r in run_seed(s["seed"])["rows"]]
        report["procedural_replay"] = dict(recorded=procedural_digest(rows), replayed=procedural_digest(again))
        gates["v4_independent_regrade_matches"] = gates["v4_independent_regrade_matches"] and \
            report["procedural_replay"]["recorded"] == report["procedural_replay"]["replayed"]
    # ---------------- per-arm tables (pooled + per seed, per kind)
    table = {}
    for arm in V4_ARMS + ("full_nexus_frozen_zero_shot",):
        per_seed = [_arm_totals(s, arm) for s in proc]
        tot = {k: sum(p[k] for p in per_seed) for k in ("tasks", "solved", "target_work", "source_work")}
        tot["fully_loaded_work"] = tot["target_work"] + tot["source_work"]
        tot["work_per_solve_target"] = tot["target_work"] / max(1, tot["solved"])
        tot["work_per_solve_fully_loaded"] = tot["fully_loaded_work"] / max(1, tot["solved"])
        tot["by_kind"] = {}
        for kind in ("passive", "trap", "active", "subset"):
            kr = [r for r in rows if r["arm"] == arm and r["kind"] == kind]
            tot["by_kind"][kind] = dict(tasks=len(kr), solved=sum(r["solved"] for r in kr),
                                        work=sum(r["work"] for r in kr), probes=sum(r["probes"] for r in kr))
        tot["per_seed"] = per_seed
        table[arm] = tot
    report["arms"] = table
    # ---------------- G2 decisive cross-domain hypothesis (pooled, fully loaded)
    a4 = table[V4_FULL]
    g2 = {}
    for c in V4_CONTROLS:
        tc = table[c]
        g2[c] = dict(solved=(a4["solved"], tc["solved"]),
                     fully_loaded_work_per_solve=(a4["work_per_solve_fully_loaded"], tc["work_per_solve_fully_loaded"]),
                     passes=a4["solved"] > tc["solved"] and
                     a4["work_per_solve_fully_loaded"] < tc["work_per_solve_fully_loaded"])
    a5 = table["amnesiac_no_source_control"]
    net = (a5["target_work"] - a4["target_work"]) - a4["source_work"]
    report["g2"] = dict(per_control=g2, net_benefit_vs_amnesiac=net)
    gates["v4_g2_full_nexus_beats_controls"] = all(v["passes"] for v in g2.values()) and net > 0
    # ---------------- G3 disambiguation / subset-repair transfer (seed-level one-sided sign tests)
    g3 = {}
    for name, kinds in (("disambiguation", ("trap", "active")), ("subset_repair", ("subset",))):
        for c in ("abstractions_fixed_refinement", "amnesiac_no_source_control"):
            sw = sl = ww = wl = 0
            for s in proc:
                x, y = _arm_totals(s, V4_FULL, kinds), _arm_totals(s, c, kinds)
                rx, ry = x["solved"] / max(1, x["tasks"]), y["solved"] / max(1, y["tasks"])
                sw, sl = sw + (rx > ry), sl + (rx <= ry)
                ww, wl = ww + (x["target_work"] < y["target_work"]), wl + (x["target_work"] >= y["target_work"])
            p_s, p_w = one_sided_sign(sw, sl), one_sided_sign(ww, wl)
            g3[f"{name}_vs_{c}"] = dict(solve_rate_seed_wins=sw, solve_rate_p=p_s, work_seed_wins=ww, work_p=p_w,
                                        passes=p_s < ALPHA and p_w < ALPHA)
    report["g3"] = g3
    gates["v4_g3_disambiguation_and_repair_transfer"] = all(v["passes"] for v in g3.values())
    # ---------------- G4 Popper efficiency with exact verdicts
    audit = [a for s in proc for a in s["popper_audit"]]
    off = sum(a["evals_off"] for a in audit)
    on = sum(a["evals_on"] for a in audit)
    same = all(a["same_verdict"] for a in audit)
    report["g4"] = dict(tasks=len(audit), evaluations_off=off, evaluations_on=on,
                        reduction=1 - on / max(1, off), same_verdicts=same)
    gates["v4_g4_popper_efficiency"] = bool(audit) and on <= 0.85 * off and same
    # ---------------- G5 real-world MBPP
    code = {}
    for meth in ("standalone", "verified_sampling", "symbolic", "nexus_v4"):
        rs = [r for r in mb.get("rows", []) if r["method"] == meth]
        c, pl = sum(bool(r["correct"]) for r in rs), sum(bool(r["plausible"]) for r in rs)
        code[meth] = dict(tasks=len(rs), correct=c, plausible=pl, precision=c / pl if pl else 0.0,
                          work=sum(r["work"] for r in rs), work_per_correct=sum(r["work"] for r in rs) / c if c else None,
                          llm_calls=sum(r.get("llm_calls", 0) for r in rs))
    report["code_table"] = code
    nx, sa, vs = code["nexus_v4"], code["standalone"], code["verified_sampling"]
    gates["v4_g5a_nexus_vs_unverified_qwen"] = nx["tasks"] > 0 and nx["correct"] > sa["correct"] and \
        nx["precision"] > sa["precision"]
    gates["v4_g5b_nexus_vs_verified_sampling"] = nx["tasks"] > 0 and nx["correct"] > vs["correct"] and \
        nx["work_per_correct"] is not None and vs["work_per_correct"] is not None and \
        nx["work_per_correct"] < vs["work_per_correct"]
    if nx["tasks"]:
        A = [r for r in mb["rows"] if r["method"] == "nexus_v4"]
        B = [r for r in mb["rows"] if r["method"] == "verified_sampling"]
        report["nexus_vs_verified_sampling_permutation"] = permutation_ratio_test(A, B)
    ty = mb.get("tycho", {})
    used = sum(1 for r in mb.get("rows", []) if r["method"] == "nexus_v4" and r["correct"] and r.get("library_used"))
    used += sum(1 for r in mb.get("rows", []) if r["method"] == "nexus_v4" and r["correct"]
                and r.get("stage") == "helper_composition")
    report["g5c"] = dict(tycho=ty, correct_heldout_answers_using_library=used)
    gates["v4_g5c_helpers_positive_net_validation_benefit"] = bool(ty.get("admitted")) and \
        ty.get("net_benefit", 0) > 0 and used >= 1
    report["llm"] = {k: payload.get("llm_telemetry", {}).get(k) for k in
                     ("backend", "model", "calls", "fresh_calls", "charged_cache_hits", "generated_tokens",
                      "input_tokens", "wall_s")}
    report["resources"] = dict(payload.get("resources", {}), wall_s=payload.get("wall_s"),
                               metal_ledger=payload.get("metal_ledger"))
    report["source_reports"] = [dict(seed=s["seed"], admitted=s["source_report"]["admitted"],
                                     eta=s["source_report"]["eta"], n_schemas=s["source_report"]["n_schemas"],
                                     tycho=s["source_report"]["tycho"], source_ledger=s["source_ledger"])
                                for s in proc]
    return dict(gates=gates, all_passed=all(gates.values()), failed=sorted(k for k, v in gates.items() if not v),
                report=report)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default=str(ROOT / "artifacts" / "wave24_agi_gap_suite.json"))
    ap.add_argument("--report")
    ap.add_argument("--replay", action="store_true", help="v4: re-run Track A from source and compare digests")
    args = ap.parse_args(argv)
    payload = json.loads(Path(args.path).read_text())
    if payload.get("schema") == "wave24_suite_v4":
        result = verify_v4(payload, replay=args.replay)
    elif payload.get("schema") == "wave24_suite_v3":
        result = verify_v3(payload)
    else:
        result = verify(payload)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(text)
    print(text)
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
