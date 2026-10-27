"""Wave 41 (NOT LOCKED; development data only): HYPOTHETICAL certification saving if a future checker accepted the base lemma
summaries. Proxy: executions of a full run-to-completion sweep of the declared v5 scope (repaired search, uniform order)
with and without the lemmas, on PROSE-dev tasks. This is NOT a Checker v5 measurement: v5 is read-only and accepts no
summaries; the estimate only sizes what a summary-accepting checker version (an owner decision) could save."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import w39_prose as P
from nexus import w38_learn as K, w39_scope as S, w41_lemmas as M, w41_search as Q, w39_eval as WE
t0 = time.perf_counter()
specs, _ = P.tasks_for("dev")
off = on = 0; rows = []
for n, spec in sorted(specs.items()):
    t, _ = P.convert(spec, True)
    if not t:
        continue
    sc = S.scope(t["public"], t["query"], 3)
    cm = K.cost_matrix(None, sc["tools"])
    m0, m1 = {}, {}
    a = Q.reachable_fitting(t["public"], t["query"], sc["tools"], 3, cm, budget=6_000_000, meter=m0)
    b = Q.reachable_fitting(t["public"], t["query"], sc["tools"], 3, cm, budget=6_000_000, lem=M.TaskLemmas(t["public"], sc["tools"]), meter=m1)
    assert a == b, n
    off += m0["execs"]; on += m1["execs"]; rows.append((n, m0["execs"], m1["execs"], len(a)))
out = dict(tasks=len(rows), sweep_execs_without=off, sweep_execs_with=on, ratio=on / off, rows=rows)
(ROOT / "artifacts/w41_sweep_estimate_dev.json").write_text(json.dumps(out, indent=1))
print({k: v for k, v in out.items() if k != "rows"})
WE.ledger_append(dict(run="w41-sweep-estimate-dev", wall_s=time.perf_counter() - t0, status="COMPLETE"))
