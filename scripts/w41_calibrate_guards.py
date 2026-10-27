"""Wave 41 guard calibration (NOT LOCKED; development data only): rescore stored PROSE-dev / Split-dev snapshots and the 4
BURNED Wave 40 cases under guard variants V0-V3. Rule (fixed before looking): choose the variant with the fewest guarded
silent failures summed over dev + burned; ties -> the most correct answers kept."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from nexus import w39_lang as L, w41_guards as G
import w41_common as C, w41_track3 as T
res = json.loads(Path(sys.argv[1]).read_text())
tasks = {t["name"]: t for t in T.load("dev")}
tot = {}
for var in ("V0", "V1", "V2", "V3"):
    G.VARIANT = var
    s = {"silent": 0, "kept": 0, "silent_raw": 0, "kept_raw": 0}
    for n, v in res["tasks"].items():
        for arm, x in v.items():
            if arm != sys.argv[2] or "snaps" not in x:
                continue
            for k, sc in C.score_k(x, tasks[n], 2).items():
                if k in (0, 2):
                    s["silent"] += sc["silent_guard"]; s["kept"] += sc["ans_guard"]
                    s["silent_raw"] += sc["silent_raw"]; s["kept_raw"] += sc["ans_raw"]
    o = json.loads((ROOT / "artifacts/w40_step6_heldout_audit.json").read_text())
    for c in o["cases"]:
        xs = [c["query"]] + [r["input"] for r in c["heldout"][1:]]
        uq = [True] + [r["labelled_unique"] for r in c["heldout"][1:]]
        ok = [r["ok"] for r in c["heldout"]]
        tiers = G.label_inputs(c["public"], c["certified_program"], xs, uq)
        s["silent"] += sum(t == "UNIQUE" and not k for t, k in zip(tiers, ok))
        s["kept"] += sum(t == "UNIQUE" and k for t, k in zip(tiers, ok))
    tot[var] = s
    print(var, s)
best = min(tot, key=lambda v: (tot[v]["silent"], -tot[v]["kept"]))
print("chosen", best)
