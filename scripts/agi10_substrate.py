"""Phase 10 Stage 2 substrate check (NOT LOCKED; development seeds). For each paradigm x engine (and P8 / P9), one project is
generated and its TRUTH pipeline is executed through every stage's declared engine by the independent evaluator; the
legacy languages encountered are recorded. Requested capabilities that the arena does not implement are listed, not
simulated: multi-table schemas / joins, Polars (not installed), Debezium-style nested CDC envelopes, MERGE / snapshot
reconciliation, QUALIFY, and ingestion of external repositories (none available offline; no network download)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agi7_diag as WIT  # noqa: E402
from nexus.de_phase4 import world as W  # noqa: E402
from nexus.de_phase7 import world7 as W7  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "artifacts/agi10_dev/substrate.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
W.SparkCode.warm()
s = 81950
specs = [dict(paradigm=p, engine=e) for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7") for e in ("sqlite", "duckdb", "spark")] + \
        [dict(paradigm="P8"), dict(paradigm="P8"), dict(paradigm="P9", hybrid="A"), dict(paradigm="P9", hybrid="B"), dict(paradigm="P9", hybrid="C"), dict(paradigm="X1"), dict(paradigm="X2")]
for sp in specs:
    t = time.time()
    try:
        p = W7.make_project7(sp, s, ROOT / "var/agi10_ws/dev/substrate")
        truths = json.loads((Path(p["hidden_dir"]) / "stakeholder.json").read_text())["truths"]
        row = dict(spec=sp, pid=p["pid"], stages=[(st["engine"], st["legacy_lang"], st["target_lang"]) for st in p["stages"]], truth_executes=WIT.ok_hidden(p, truths))
    except Exception as e:                                     # noqa: BLE001
        row = dict(spec=sp, error=str(e)[:120])
    row["wall"] = round(time.time() - t, 2)
    s += 1
    with open(out, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    print(row, flush=True)
