"""Phase 7 dev debugging (NOT LOCKED): count imports during one declared-engine execution."""
import builtins, collections, json, time, traceback
from pathlib import Path
from nexus.de_phase6 import pipeline6 as P6
pid = "P6.P4.P4_duckdb.67003"
inv = P6.Inv6(dict(pid=pid, ws=f"var/agi7_ws/dev/diag/{pid}/workspace"))
inv.exec(inv.legacy, prescreen=False)
cnt, where = collections.Counter(), collections.Counter()
orig = builtins.__import__
def imp(name, *a, **k):
    cnt[name] += 1
    if cnt[name] == 3:
        where[name] = "".join(traceback.format_stack(limit=4)[:-1])
    return orig(name, *a, **k)
builtins.__import__ = imp
t = time.time(); inv.exec(inv.legacy, prescreen=False); t1 = time.time() - t
builtins.__import__ = orig
t = time.time(); inv.exec(inv.legacy, prescreen=True); t2 = time.time() - t
t = time.time(); v = P6.invariants(inv, inv.legacy); t3 = time.time() - t
print("duckdb exec", round(t1, 3), "sqlite exec", round(t2, 4), "invariants", round(t3, 3), v)
for n, c in cnt.most_common(5):
    print(c, n, where.get(n, "")[-600:])
