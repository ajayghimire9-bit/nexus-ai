"""Phase 4 Stage 3: full-trajectory improver versus improver (NOT LOCKED).  python scripts/agi4_meta.py REP IMP BUDGET_S
Each clone starts from the identical frozen Full_r<REP> endpoint (DE memory pi_de, skills, P, prefs; digest-checked against
artifacts/agi4_freeze_source.json) and runs a COMPLETE learning trajectory controlled entirely by its improver: its own
curriculum, search procedure, failure-archive priority, cross-engine mode, admission threshold, pruning and learning rates:
  Mstar = the Full_r<REP> endpoint's adopted M; M0 = lineage.M0; Mrand = lineage.m_random(random.Random(f"agi4-mrand-meta-{REP}"))
Paired environment randomness: identical learning / admission seed streams (seeds.meta_block(REP): agi4de/source_meta) and
RNG keys; no meta-edits. Output artifacts/agi4_meta/r<REP>_<IMP>.json (never rerun)."""
import json, random, sys, time
from pathlib import Path
from nexus.de_phase4 import lineage as LG, seeds as SD, world as W
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from agi4_eval import digest  # noqa: E402


def main(rep, imp, budget):
    rep, budget = int(rep), float(budget)
    out = ROOT / "artifacts/agi4_meta"
    if (out / f"r{rep}_{imp}.json").exists():
        raise SystemExit("meta clones are never rerun")
    e = json.loads((ROOT / "artifacts/agi4_freeze_source.json").read_text())["endpoints"][f"Full_r{rep}"]
    st = json.loads(json.dumps(e["state"]))
    assert digest(st) == e["digest"]
    if imp == "M0":
        st["M"] = json.loads(json.dumps(LG.M0))
    elif imp == "Mrand":
        st["M"] = LG.m_random(random.Random(f"agi4-mrand-meta-{rep}"))
    elif imp != "Mstar":
        raise SystemExit(imp)
    W.SparkCode.warm()
    blk = SD.meta_block(rep)
    lin = LG.Lineage(f"r{rep}_{imp}", st, budget, out, blk["learn"], blk["admit"], meta_edits=False, use_P=True, rng_key=f"meta4|{rep}")
    lin.run()
    s = lin.rows
    print(lin.name, "projects", len(s), "verified", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s),
          "skills", len(lin.st["DE"]["skills"]), "P", len(lin.st["DE"]["P"]), "stop", lin.stop_reason, "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
