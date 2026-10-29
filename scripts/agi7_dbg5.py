"""Phase 7 dev check (NOT LOCKED): the real coverage barrier on development legacy_flip projects, end to end."""
import json
from nexus.de_phase6 import pipeline6 as P6
from nexus.de_phase7 import accept7 as AC7, procedure7 as PR7, world7 as W7
for spec, seed in ((dict(paradigm="P7", engine="duckdb", dp_mode="explicit", legacy_flip=True, fault_p=0.4), 68900),
                   (dict(paradigm="P1", engine="sqlite", dp_mode="explicit", legacy_flip=True, fault_p=0.4), 68901)):
    p = W7.make_project7(spec, seed, "var/agi7_ws/dev/cov")
    inv = P6.Inv6(p)
    c = {}
    cov = AC7.coverage(inv, inv.legacy, cost=c)
    print(p["pid"], "flip", p["legacy_flip"], "subjects", len(inv.claim_refs), "obligations", [(o["stage"], o["options"], o["effects"]) for o in cov["obligations"]],
          "equiv", len(cov["equivalences"]), "uncovered", len(cov["uncovered"]), c)
    for name, prog in (("SEED", PR7.SEED), ("FIXED", PR7.FIXED_STRATEGY)):
        st = PR7.investigate(p, PR7.Live(3000, 6.0), dict(de=dict(w={}, skills={}), M={}), prog)
        o = PR7.outcome(p, st)
        print("  ", name, st.decision["kind"], st.decision.get("reason"), "verified", o["verified"], "wrong", o["wrong"], "q", st.cost["questions"])
