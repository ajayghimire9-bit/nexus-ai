"""Wave 40 (NOT LOCKED; development data only): one-off calibration of the payoff gate's exec-equivalent constants on PROSE-dev
scopes: OS instructions per learned-mixture cost-row entry and per program token refitted, divided by OS instructions per
search execution (process instruction counter, this process)."""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import w38_domains as D, w38_learn as K, w39_scope as S, w40_learn as W, w40_search as Q
from nexus.wave31_evaluator import instructions
import w39_prose as P

progs = [t["teacher"] for t in D.stream("w40-cal", D.DOMAINS, "source", 2)]
pri = K.fit(progs)
specs, _ = P.tasks_for("dev")
ex = ent = 0; ie = ir = 0
for n, spec in sorted(specs.items())[:12]:
    t, _ = P.convert(spec, True)
    if not t:
        continue
    sc = S.scope(t["public"], t["query"], 3)
    m = {}
    i0 = instructions(os.getpid()); Q.search(t["public"], t["query"], sc["tools"], 3, K.cost_matrix(None, sc["tools"]), budget=20000, meter=m)
    ie += instructions(os.getpid()) - i0; ex += m["execs"]
    cm = W.cost_matrix_fast(pri, sc["tools"])
    i0 = instructions(os.getpid())
    for r in range(60):
        cm["cost"][r]
    ir += instructions(os.getpid()) - i0; ent += 60 * len(sc["tools"])
i0 = instructions(os.getpid())
for _ in range(20):
    K.fit(progs)
fi = (instructions(os.getpid()) - i0) / (20 * sum(len(p) for p in progs))
pe = ie / ex
print(json.dumps(dict(instr_per_exec=pe, instr_per_row_entry=ir / ent, instr_per_fit_token=fi, C_ROW=ir / ent / pe, C_FIT=fi / pe)))
