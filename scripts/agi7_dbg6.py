"""Phase 7 post-hoc diagnosis (NOT LOCKED; analysis of an already scored target, no outcome is changed or rerun):
for the one wrong project, evaluate every option combination of the A0 candidate's decision points on the hidden batches."""
import copy, itertools, json
from nexus.de_phase7 import procedure7 as PR7, seeds7 as S, world7 as W7, lineage7 as L7
t = next(x for x in S.target_manifest() if x["seed"] == 71032)
p = W7.make_project7({k: v for k, v in t.items() if k not in ("seed", "tier")}, 71032, "var/agi7_ws/posthoc")
st = PR7.investigate(p, PR7.Live(3000, 6.0), L7.empty_memory(), PR7.FIXED_STRATEGY)
print("decision", st.decision, "faults", p["faults"], "inclusive", p["inclusive"])
print("path", st.cand["path"])
for d in st.dps:
    print(" dp", d["stage"], d["pos"], d["op"], d["options"], "resolved", d["resolved"], "via", d["via"], "effects", d["effects"], "claims", [(c["effect_at_boundary"], c["status"]) for c in d["claims"]])
for opts in itertools.product(*[d["options"] for d in st.dps]):
    s2 = copy.copy(st)
    s2.decision = dict(kind="submit", choices={f"{d['stage']}:{d['pos']}": o for d, o in zip(st.dps, opts)})
    print(" combo", opts, PR7.outcome(p, s2)["verified"])
