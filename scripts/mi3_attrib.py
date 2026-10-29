"""MI-3 attribution + discovery telemetry (NOT LOCKED; reads saved artifacts only, no evaluation).
  python scripts/mi3_attrib.py      -> artifacts/mi3_attribution.json
Per run: candidate counts by stage, duplicate / degenerate / distinct-space counts, mean candidate CPU, best-so-far curve.
Per winner: LPL source, full ancestry (ids, operators, edits), hypothesis-space size and the expressions it adds to / drops from
the seed procedure's space on the fixed probe contexts, and the mechanistic check of the claim-limit rule: which of its fresh
winner_eval solves (unfamiliar families) used a learned update that lies OUTSIDE the seed procedure's space."""
import json
from pathlib import Path
from nexus import mi3_search as MS, mi_lpl as LP, oop_synthesizer as S
ROOT = Path(__file__).resolve().parents[1]
RUNS = [f"{a}_L{l}" for a in ("E-F", "E-S", "R-F", "R-S") for l in (1, 2)]
CTX = MS.PROBE_CTX[2]


def space(prog):
    lst, _ = LP.hypothesis_space(prog, dict(CTX))
    return {LP._sig(g): S.src(g) for g in lst}


def ancestry(cands, i, depth=0):
    c = cands[i]
    node = dict(id=i, op=c["lineage"].get("op"), edits=c["lineage"].get("edits"), full_fitness=c.get("full_fitness"),
                screen_fitness=c.get("screen_fitness"), stage=c.get("stage"))
    if depth < 40:
        node["parents"] = [ancestry(cands, p, depth + 1) for p in c["lineage"].get("parents", [])]
    return node


def main():
    seed_sp = space(LP.SEED_BASELINE)
    seed_srcs = set(seed_sp.values())
    ev = {}
    for r in RUNS + ["A0"]:
        p = ROOT / f"artifacts/mi3_winner_eval/{r}.jsonl"
        ev[r] = [json.loads(l) for l in p.read_text().splitlines()]
    out = dict(runs={}, winners={})
    for r in RUNS:
        st = json.loads((ROOT / f"artifacts/mi3_disc/{r}.json").read_text())
        cs = st["cands"]
        stages = {}
        for c in cs:
            stages[c["stage"]] = stages.get(c["stage"], 0) + 1
        out["runs"][r] = dict(candidates=len(cs), stages=stages, duplicates=sum(c["duplicate"] for c in cs),
                              degenerate=sum(bool(c["invalid"]) for c in cs), distinct_spaces=len({c["signature"] for c in cs}),
                              fully_evaluated=sum(c.get("full_fitness") is not None for c in cs),
                              mean_candidate_cpu_s=round(sum(c["cpu_s"] for c in cs) / len(cs), 3),
                              screen_spent=round(st["screen_spent"], 2), audit_spent=round(st["audit_spent"], 2),
                              stopped_at=st.get("stopped_at"), curve=[(x["elapsed"], x["best_full_exact"]) for x in st["curve"]],
                              useful_distinct=len({c["signature"] for c in cs if (c.get("full_fitness") or [0])[0] > 0}),
                              selection=[(e["id"], e["sel_fitness"][:2]) for e in st.get("selection", [])])
        w = cs[st["winner_id"]]
        sp = space(w["prog"])
        added = sorted(v for k, v in sp.items() if k not in seed_sp)
        dropped = sorted(v for k, v in seed_sp.items() if k not in sp)
        solves = [x for x in ev[r] if x["exact"] and x["family"] != "K"]
        outside = []
        for x in solves:
            ups = [u for rg in (x["updates"] or []) for u in rg.values()]
            if any(u not in seed_srcs for u in ups):
                outside.append(dict(seed=x["seed"], family=x["family"], updates=ups))
        a0 = {(x["seed"], x["family"]) for x in ev["A0"] if x["exact"] and x["family"] != "K"}
        out["winners"][r] = dict(id=w["id"], rule=st["winner_rule"], source=LP.source(w["prog"]), ancestry=ancestry(cs, w["id"]),
                                 space_size=len(sp), seed_space_size=len(seed_sp), same_space_as_seed=w["signature"] == cs[0]["signature"],
                                 added_vs_seed=added[:60], n_added=len(added), dropped_vs_seed=dropped[:60], n_dropped=len(dropped),
                                 unfamiliar_solves=len(solves), solves_using_update_outside_seed_space=outside,
                                 solves_beyond_A0=sum((x["seed"], x["family"]) not in a0 for x in solves))
    p = ROOT / "artifacts/mi3_attribution.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    for r, v in out["winners"].items():
        print(r, "id", v["id"], "space", v["space_size"], "seed", v["seed_space_size"], "+", v["n_added"], "-", v["n_dropped"],
              "same_as_seed", v["same_space_as_seed"], "unf", v["unfamiliar_solves"], "outside_seed", len(v["solves_using_update_outside_seed_space"]),
              "beyond_A0", v["solves_beyond_A0"], "added", v["added_vs_seed"][:6])


if __name__ == "__main__":
    main()
