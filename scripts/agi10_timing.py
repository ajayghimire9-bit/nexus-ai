"""Phase 10 dev timing check (NOT LOCKED): the slow rehearsal wake (P5 duckdb, dev seed 81008) re-run with the trained
dev guide after the roles memo; output-identity of the memo is checked against the unmemoised roles on the same domain."""
import json, time
from pathlib import Path
from nexus.de_phase6 import pipeline6 as P6, skills6 as SK
from nexus.de_phase10 import guide10 as G, lineage10 as LN, manifest10 as MF, procedure10 as PR10
ck = json.loads(Path("artifacts/agi10_dev/train/main.N6.json").read_text())
p = LN.build(MF.train_spec(8, 81008), 81008, Path("var/agi10_ws/dev/timing"), require=False)
inv = P6.Inv6(p)
d = inv.dom(0, inv.legacy)
same = all(G._ORIG_ROLES(d, c) == SK.roles(d, c) for c in d.header)
t = time.time()
st = PR10.investigate(p, PR10.Live(LN.W_SRC, LN.WALL), ck["memory"], PR10.F0)
print("memo output-identical", same, "decision", st.decision["kind"], "wall", round(time.time() - t, 2))
