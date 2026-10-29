"""Phase 10 post-hoc diagnosis of the one accepted wrong repair (NOT LOCKED; analysis of an already-scored target,
no outcome changed or rerun): C1@N60 on 84005 - every decision point, its resolution and evidence, and the hidden check."""
import copy, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi10_eval as EV  # noqa: E402
from nexus.de_phase10 import lineage10 as LN, manifest10 as MF, procedure10 as PR10  # noqa: E402
t = next(x for x in MF.eval_manifest() if x["seed"] == 84005)
p = LN.build(t, 84005, Path("var/agi10_ws/posthoc"), require=False)
a = EV.arms()["C1@N60"]
st = PR10.investigate(p, PR10.Live(LN.W_SRC, LN.WALL), copy.deepcopy(a["mem"]), a["prog"], {})
o = PR10.outcome(p, st)
print("decision", st.decision, "verified", o["verified"], "hidden", o.get("hidden"), "faults", p["faults"], "modes", p["dps"], "inclusive", p["inclusive"])
print("path", (st.cand or {}).get("path"), "via_skill", (st.cand or {}).get("via_skill"))
for d in st.dps:
    print(" dp", str(d["pos"])[:40], d.get("kind"), d["options"], "resolved", d["resolved"], "via", d["via"], "conflict", d["conflict"], "claims", [(c["effect_at_boundary"], c["status"], c["provenance"]["file"]) for c in d.get("claims") or []],
          "effects", d.get("effects"), "legacy", d.get("legacy_effect"))
for x in st.trace:
    if x["action"] in ("resolve", "ask", "check_coverage"):
        print("  trace", x["action"], json.dumps(x["obs"], default=str)[:220], x["decision"])
