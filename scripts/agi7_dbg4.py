"""Phase 7 dev check (NOT LOCKED): why de_accept_v3 flags 'corruption' for a hidden-verified dedup-on-id repair."""
import json
from nexus.de_phase4 import world as W
from nexus.de_phase6 import pipeline6 as P6, engines6 as E
from nexus.de_phase7 import ops7  # noqa: F401
pid = "P6.P4.P4_sqlite.67010"
inv = P6.Inv6(dict(pid=pid, ws=f"var/agi7_ws/dev/diag/{pid}/workspace"))
sp = [s for s, prm in E.candidates("dedup_first", inv.legacy[0], inv.dom(0, inv.legacy)) if prm == "id"][0]
d0 = inv.dom(0, inv.legacy)
fresh = P6._fresh(inv, inv.rows)
print("ukey", inv.ukey, "cols", inv.cols, "fresh", sorted(fresh), "dirty", sorted(d0.dirty_cols), "int_like", sorted(d0.int_like))
for name, specs in (("legacy", inv.legacy), ("dedup_id", [sp])):
    base = inv.exec(specs, prescreen=True)
    stress = []
    for j, c in enumerate(sorted(d0.dirty_cols)):
        for v in ("n/a", "12x", ""):
            r = P6._probe(inv, 100 + 3 * j + len(stress), fresh); r[c] = v; stress.append(r)
    for c in sorted(d0.int_like - d0.dirty_cols)[:3]:
        r = P6._probe(inv, 200 + len(stress), fresh); r[c] = "0"; stress.append(r)
    st = inv.exec(specs, inv.rows + stress, prescreen=True)
    uk = inv.ukey
    b = {r.get(uk): tuple(W.num(r.get(c)) for c in inv.cols) for r in base["clean"]}
    s_ = {r.get(uk): tuple(W.num(r.get(c)) for c in inv.cols) for r in st["clean"]}
    diff = [(k, v, s_.get(k)) for k, v in b.items() if s_.get(k) != v]
    print(name, "n stress", len(stress), "changed keys", len(diff), diff[:2], "stress ids", [r["id"] for r in stress[:3]])
