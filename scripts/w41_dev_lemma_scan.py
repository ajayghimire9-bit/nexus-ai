"""Wave 41 dev scan (NOT LOCKED; PROSE-dev + Split-dev only): search executions to first candidate / to exhaustion with and
without the base lemmas (uniform and Fixed+Repr orders)."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w39_prose as P
from nexus import w38_learn as K, w39_scope as S, w40_learn as W, w41_lemmas as M, w41_search as Q, w39_eval as WE
t0 = time.perf_counter()
specs, _ = P.tasks_for("dev")
pri = json.loads((ROOT / "artifacts/w39_prose_confirm.json").read_text())["source"]["priors"]["repr"]
tot = {"off": 0, "on": 0}; rows = []
for n, spec in sorted(specs.items()):
    t, _ = P.convert(spec, True)
    if not t:
        continue
    sc = S.scope(t["public"], t["query"], 3)
    cm = W.cost_matrix_fast({"kind": "fixed_repr", "repr": pri}, sc["tools"])
    r = {}
    for k, lem in (("off", None), ("on", M.TaskLemmas(t["public"], sc["tools"]))):
        m = {}
        c = Q.search(t["public"], t["query"], sc["tools"], 3, cm, budget=4_000_000, meter=m, lem=lem)
        r[k] = (m["execs"], c is not None, m.get("lemma_skips", 0))
        tot[k] += m["execs"]
    assert r["off"][1] == r["on"][1]
    rows.append((n, r))
for n, r in rows:
    print(f"{n:28s} found={r['off'][1]!s:5s} execs off {r['off'][0]:8d} on {r['on'][0]:8d} skips {r['on'][2]}")
print("total execs off", tot["off"], "on", tot["on"], "ratio %.3f" % (tot["on"] / tot["off"]))
WE.ledger_append(dict(run="w41-dev-lemma-scan", wall_s=time.perf_counter() - t0, status="COMPLETE"))
