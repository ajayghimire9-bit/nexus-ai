"""E3 (NOT LOCKED): DGM-inspired branching archive (Zhang et al. 2025, arXiv:2505.22954; documented ADAPTATION: the
'self-modifications' are restricted to learner-DSL v2.1 edits, not source code; no coding agent; no empirical
open-ended benchmark) vs incumbent-only hill climbing vs budget-matched random search.
Each method: 2 independent lineages x 12 program evaluations (the 3 trivial seeds are counted in the 12), zero human
intervention, the same fitness (wave34_meta.score on wave36 dev seed 824 training streams, normalised by
min(SEED_ON, SEED_OFF, FIXED_PAYOFF)). DGM parent selection: probability proportional to sigmoid-ranked performance
divided by (1 + number of children). Each lineage's best is then evaluated ONCE on held-out dev streams (F3 / F4 x 3,
seed 825) against B-online (SEED_PRIOR). Audit: learner programs are DSL expressions with no op specs; scanned for any."""
import json, math, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave34_meta as M4
FIT, HOLD, BUDGET = (824,), 825, 12


def run_lineage(ev, method, lineage, base):
    from nexus import wave34_learner as L
    rng = random.Random(f"w36-e3:{method}:{lineage}")
    seeds = [L.SEED_ON, L.SEED_OFF, L.SEED_PRIOR]
    arch = []
    for p in seeds:
        fit, _ = M4.score(ev, p, FIT, base)
        arch.append(dict(program=p, fit=fit, children=0))
    while len(arch) < BUDGET:
        if method == "random":
            q = rng.choice(seeds)
            for _ in range(rng.randint(2, 6)):
                q = L.mutate(q, rng)
        elif method == "incumbent":
            best = min(arch, key=lambda e: (e["fit"]["wrong"], e["fit"]["score"]))
            q = L.mutate(best["program"], rng); best["children"] += 1
        else:
            ranked = sorted(arch, key=lambda e: e["fit"]["score"])
            w = [1 / (1 + math.exp(10 * (i / max(1, len(ranked) - 1) - 0.5))) / (1 + e["children"]) for i, e in enumerate(ranked)]
            par = rng.choices(ranked, weights=w)[0]; par["children"] += 1
            q = L.mutate(par["program"], rng)
        fit, _ = M4.score(ev, q, FIT, base)
        arch.append(dict(program=q, fit=fit, children=0))
    best = min(arch, key=lambda e: (e["fit"]["wrong"], e["fit"]["score"]))
    return best, [e["fit"]["score"] for e in arch]


def main():
    from nexus import seed_registry as R
    from nexus import wave31_evaluator as E
    from nexus import wave34_learner as L
    from nexus import wave34_tasks as T4
    R.claim("wave36", "dev", list(R.REGISTRY[("wave36", "dev")]), run_id="w36-e3-dev", record=False)
    ev = E.Evaluator(depth=4, checker=3)
    t0 = time.perf_counter()
    M4.SEARCH["instr"] = 0
    base = M4.baseline(ev, FIT)
    out = {"lineages": []}
    hold = {"F3": T4.family_stream(T4.F3, f"e3h{HOLD}", 3, "F3"), "F4": T4.family_stream(T4.F4, f"e3h{HOLD}", 3, "F4")}
    bref = {}
    for fam, tasks in hold.items():
        rows, learn = M4.run_prog(ev, L.SEED_PRIOR, tasks, f"e3h:{fam}")
        bref[fam] = sum(r["ext"]["evaluator_work"] for r in rows) + learn
    for method in ("dgm_branching", "incumbent", "random"):
        for lineage in (0, 1):
            s0 = M4.SEARCH["instr"]
            best, curve = run_lineage(ev, method, lineage, base)
            ho = {}
            for fam, tasks in hold.items():
                rows, learn = M4.run_prog(ev, best["program"], tasks, f"e3h:{fam}")
                ho[fam] = dict(ratio_vs_B=(sum(r["ext"]["evaluator_work"] for r in rows) + learn) / bref[fam],
                               wrong=sum(r["wrong"] is not None for r in rows))
            leak = any(op in json.dumps(best["program"]) for op in ("enc_", "ir_", "proj", "Sort", "prefix_sum"))
            out["lineages"].append(dict(method=method, lineage=lineage, best_score=best["fit"]["score"], curve=curve,
                                        program=best["program"],
                                        is_seed=best["program"] in (L.SEED_ON, L.SEED_OFF, L.SEED_PRIOR), holdout=ho,
                                        search_instr=M4.SEARCH["instr"] - s0, embedded_solution_found=leak))
            l = out["lineages"][-1]
            print(method, lineage, "best %.4f seed? %s holdout F3 %.4f F4 %.4f search %.1fG leak %s" % (
                l["best_score"], l["is_seed"], ho["F3"]["ratio_vs_B"], ho["F4"]["ratio_vs_B"], l["search_instr"] / 1e9, leak), flush=True)
    (ROOT / "artifacts/wave36_e3_dev.json").write_text(json.dumps(out, sort_keys=True, default=repr))
    E.ledger_append(dict(run="w36-e3-dev", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main()
