"""Trial 2 (NOT LOCKED): leave-one-class-out over W1, 7953, X1, X2, unit_shift (clock_skew and id_collision always train).
Training worlds t7/tsrc 0-9, fresh evaluation worlds t7/tdev 0-4; 5 mutants per (world, class); oracle-label budget 60 per
project run for every arm. Arms: (a) invented = critic-selected admissible concepts from the training kill matrix;
(b) generic = count_eq + unique + range(1.5) + spot(k) with k filling the same budget; (c) unguided = random concepts drawn
without the kill matrix until the budget is spent (mean of 20 draws); (d) none. Metric: held-out kill rate on fresh worlds
(a mutant counts as caught if any selected check fails on it), and false rejections on fresh clean runs.
KEEP iff (a) > (b) and (a) > (c) on the mean held-out kill rate with 0 false rejections."""
import json, random, sys, time
sys.path.insert(0, "src")
from nexus import t7_seeds, t7_world, t7_oracle as O, seed_registry as R  # noqa: F401
from pathlib import Path
ART = Path(__file__).resolve().parents[1] / "artifacts/t7_dev"
t0 = time.process_time()
LOCO = ("W1", "7953", "X1", "X2", "unit_shift")
BUDGET = 60.0
train = [O.World(s) for s in R.REGISTRY[("t7", "tsrc")]]
fresh = [O.World(s) for s in R.REGISTRY[("t7", "tdev")]]
CS = O.concepts()
Kt, cost, cf = O.kill_matrix(train, O.MUTANTS, CS, 5, seed=1)
Ke, cost_e, cf_e = O.kill_matrix(fresh, O.MUTANTS, CS, 5, seed=2)


def caught(sel, held):
    keys = {k for c in CS for k in Ke[c] if k[1] == held}
    hit = {k for c in sel for k, v in Ke[c].items() if v and k[1] == held}
    return len(hit) / max(1, len(keys))


def false_rej(sel):
    return sum(cf_e[c] for c in sel)


rows = {}
for held in LOCO:
    Ktr = {c: {k: v for k, v in Kt[c].items() if k[1] != held} for c in CS}
    inv, spent = O.critic_select(Ktr, cost, cf, BUDGET)
    k_eq = max(1, int(BUDGET - sum(cost[c] for c in O.GENERIC if c[0] != "spot")))
    gen = [c for c in O.GENERIC if c[0] != "spot"] + [("spot", k_eq, None)]
    if ("spot", k_eq, None) not in Ke:
        Ksp, csp, cfsp = O.kill_matrix(fresh, O.MUTANTS, [("spot", k_eq, None)], 5, seed=2)
        Ke.update(Ksp); cf_e.update(cfsp)
    rnd = random.Random(held)
    ung = []
    for d in range(20):
        sel, sp = [], 0.0
        for c in rnd.sample(CS, len(CS)):
            if sp + cost[c] <= BUDGET:
                sel.append(c); sp += cost[c]
        ung.append(caught(sel, held))
    rows[held] = dict(invented=[list(map(str, c)) for c in inv], invented_cost=round(spent, 1), invented_rate=round(caught(inv, held), 3),
                      invented_false_rej=false_rej(inv), generic_rate=round(caught(gen, held), 3), generic_false_rej=false_rej(gen),
                      unguided_rate=round(sum(ung) / len(ung), 3), none_rate=0.0,
                      row_identity_invented=any(c[0] == "q_identity" for c in inv))
    print(held, rows[held], flush=True)
m = {a: round(sum(r[f"{a}_rate"] for r in rows.values()) / len(rows), 3) for a in ("invented", "generic", "unguided", "none")}
fr = sum(r["invented_false_rej"] for r in rows.values())
keep = m["invented"] > m["generic"] and m["invented"] > m["unguided"] and fr == 0
out = dict(loco=rows, mean_heldout_kill=m, invented_false_rejections=fr, budget=BUDGET, verdict="KEPT" if keep else "REJECTED",
           train_clean_fail={str(c): cf[c] for c in CS}, mean_cost={str(c): round(cost[c], 2) for c in CS},
           cpu_s=round(time.process_time() - t0, 2))
(ART / "t2.json").write_text(json.dumps(out, indent=1))
print("MEAN", m, "false_rej", fr, "VERDICT", out["verdict"])
