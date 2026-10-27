"""Corrected replay for the confirm_adapt run (NOT LOCKED). The original replay re-ran st["champion"] (the amendment-2
pick a4c2) and compared it with the digest of the frozen primary a0c2, so its False was a script bug. This re-executes
the frozen primary on the already-drawn 7218 Target/3-rep tasks in a fresh child with PYTHONHASHSEED=1 and compares
digests. No new seeds are drawn."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import wave32_evolve as W
import wave32_factorial as F
from nexus import wave31_evaluator as E

t0 = time.perf_counter()
p = ROOT / "artifacts/wave32_adaptive_confirm.json"
res = json.loads(p.read_text())
g = res["frozen_policies"]["Genk(adapt)"]
rows2, _, _ = F.run(E.Evaluator(depth=4, checker=3), g, (7218,), "Target", 3, "1")
ok = W.digest(rows2) == res["table"]["Target/3rep"]["Genk(adapt)"]["per_seed"]["7218"]["digest"]
res["replay_original_bug"] = "compared a4c2 replay against the a0c2 digest"
res["replay_7218_target3_adapt_corrected"] = ok
p.write_text(json.dumps(res, sort_keys=True, default=repr))
E.ledger_append(dict(run="wave32a-confirm-replay-corrected", wall_s=time.perf_counter() - t0, status="COMPLETE"))
print("corrected replay", ok)
