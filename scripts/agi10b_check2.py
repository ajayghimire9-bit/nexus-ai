"""Phase 10B dev check: the ROUND-reachable P7 77303 under a FULL F0 investigation (barrier active), fresh memory."""
import json
from pathlib import Path
from nexus.de_phase7 import world7 as W7
from nexus.de_phase9 import blocks9 as B
from nexus.de_phase10 import lineage10 as LN, procedure10 as PR10
from nexus.de_phase10b import fixes10b, search10b  # noqa: F401
p = W7.make_project7(B.STRATA["legacy_disagreement"][0], 77303, Path("var/agi10b_ws/dev/check"))
st = PR10.investigate(p, PR10.Live(LN.W_SRC, LN.WALL), LN.empty_memory(), PR10.F0)
o = PR10.outcome(p, st)
r = dict(check="round_primitive_full_F0", pid=p["pid"], decision=st.decision["kind"], reason=st.decision.get("reason"), verified=o["verified"], wrong=o["wrong"],
         obligations=st.obligation_status, path=(st.cand or {}).get("path"))
open("artifacts/agi10b_dev/checks.jsonl", "a").write(json.dumps(r, default=str) + "\n")
print(r)
