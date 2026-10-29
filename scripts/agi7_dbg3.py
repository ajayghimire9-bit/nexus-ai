"""Phase 7 dev check (NOT LOCKED): apply a witness step on a dev project and report each acceptance stage."""
import json
from nexus.de_phase6 import pipeline6 as P6, engines6 as E
from nexus.de_phase7 import ops7, search7 as S7  # noqa: F401
for pid in ("P6.P4.P4_sqlite.67010", "P6.P1.P1_sqlite.67000"):
    inv = P6.Inv6(dict(pid=pid, ws=f"var/agi7_ws/dev/diag/{pid}/workspace"))
    sp = [s for s, prm in E.candidates("dedup_first", inv.legacy[0], inv.dom(0, inv.legacy)) if prm == "id"]
    print(pid, "id candidates", len(sp), "unique_cols has id", "id" in inv.dom(0, inv.legacy).unique_cols, "header", inv.dom(0, inv.legacy).header[:3])
    if sp:
        specs = [sp[0]] + inv.legacy[1:]
        ev = inv.run(specs)
        print(" ok", ev["ok"], "failed", ev["failed"], "held", ev["held_ok"], "score", round(ev["score"], 3), "legacy score", round(inv.run(inv.legacy)["score"], 3))
        print(" screen", P6.invariants(S7._Screen(inv), specs), "native", P6.invariants(inv, specs))
