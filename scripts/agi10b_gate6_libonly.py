"""Phase 10B addendum diagnostic (NOT LOCKED; development seeds only - the gate-6 replication seeds 90700-90705): the
LIBRARY-ONLY version of control 6 that the addendum requires - macros removed while the learned ranker and bridge search stay
unchanged. Post hoc relative to the confirmation decision (which used the owner's earlier combined definition); reported as
attribution, it does not reopen or change any one-use outcome."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi9b_gate as G9  # noqa: E402
from nexus.de_phase6 import world6 as W6  # noqa: E402
from nexus.de_phase8 import lineage8 as L8  # noqa: E402
from nexus.de_phase10b import fixes10b, search10b  # noqa: E402,F401
ROOT = Path(__file__).resolve().parents[1]
ck = json.loads((ROOT / "artifacts/agi10_train/main.N120.json").read_text())
guide = dict(ck["memory"]["guide"], bridge=True, ratio=4 / 7)
arms = dict(full=dict(L8.empty_memory(), de=dict(w={}, skills=ck["memory"]["de"]["skills"]), guide=guide),
            no_macros=dict(L8.empty_memory(), guide=guide),
            macros_fixed_guide=dict(L8.empty_memory(), de=dict(w={}, skills=ck["memory"]["de"]["skills"]), guide=dict(kind="fixed")),
            plain=dict(L8.empty_memory(), guide=dict(kind="fixed")))
rows = [json.loads(l) for l in (ROOT / "artifacts/agi10b_dev/gate6.jsonl").read_text().splitlines()]
out = []
for r in [r for r in rows if r.get("phase") == "replicate"]:
    p = W6.make_project6(r["spec"], r["seed"], ROOT / "var/agi10b_ws/dev/gate6_libonly")
    row = dict(seed=r["seed"], spec=r["spec"], **{k: G9._search(p, m) for k, m in arms.items()})
    out.append(row)
    print(r["spec"]["paradigm"], r["seed"], {k: (v["verified"], v["work"], v["method"]) for k, v in row.items() if isinstance(v, dict) and "verified" in v}, flush=True)
(ROOT / "artifacts/agi10b_dev/gate6_libonly.json").write_text(json.dumps(out, indent=1, default=str))
