"""Phase 3 Stage 3: full-trajectory improver versus improver (NOT LOCKED).  python scripts/agi3_meta.py run REP IMP [--dev]
Each clone starts from the identical frozen Full_r<REP> state (worlds R, L, P, pi + DE pi_de, L_de, P_de; digest-checked
from artifacts/agi3_freeze_source.json) and runs a COMPLETE multi-round learning trajectory (world tasks and DE projects)
controlled entirely by its improver (own curriculum, admission, pruning, archive, schedule, de_policy):
  Mstar = the Full endpoint's M; M0 = the Phase 3 M0; Mrand = agent_loop.m_random3(random.Random(f"agi3-mrand-meta-{REP}"))
Paired environment randomness: identical source-meta world-seed stream (agi3/source_meta 50000 + 300 * REP), DE project
stream (agi3de/source 51500 + 300 * REP + 100.. reserved block), admission streams and RNG keys; free actions; no
meta-edits. 45 s charged each. Output artifacts/agi3_meta/r<REP>_<IMP>.json."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign3 import agent_loop as AL, seeds as SD  # noqa: E402
from nexus.campaign2 import state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
BUDGET = 43.5


def main(cmd, rep, imp, *flags):
    rep = int(rep)
    dev = "--dev" in flags
    R = {k: SD.RANGES[k].start for k in SD.RANGES}
    if dev:
        st = ST.from_json(json.loads((ROOT / f"artifacts/agi3_dev/src/Full_r{rep}.json").read_text())["state"])
        out = ROOT / "artifacts/agi3_dev/meta"
        ts, as_, ds, das = range(R[("agi3", "dev")] + 300, R[("agi3", "dev")] + 400), range(R[("agi3", "dev")] + 900, R[("agi3", "dev")] + 950), \
            range(51000 + 300, 51000 + 340), range(51000 + 480, 51000 + 500)
    else:
        e = json.loads((ROOT / "artifacts/agi3_freeze_source.json").read_text())["endpoints"][f"Full_r{rep}"]
        st = ST.from_json(e["state"])
        assert ST.digest(st) == e["digest"]
        out = ROOT / "artifacts/agi3_meta"
        if (out / f"r{rep}_{imp}.json").exists():
            raise SystemExit("meta clones are never rerun")
        ts = range(R[("agi3", "source_meta")] + 300 * rep, R[("agi3", "source_meta")] + 300 * (rep + 1))
        as_ = range(R[("agi3", "admission")] + 300 * rep + 200, R[("agi3", "admission")] + 300 * (rep + 1))
        ds = range(R[("agi3de", "source")] + 900 + 150 * rep, R[("agi3de", "source")] + 900 + 150 * rep + 100)
        das = range(R[("agi3de", "source")] + 900 + 150 * rep + 100, R[("agi3de", "source")] + 900 + 150 * (rep + 1))
    if imp == "M0":
        st["M"] = json.loads(json.dumps(AL.M3))
    elif imp == "Mrand":
        st["M"] = AL.m_random3(random.Random(f"agi3-mrand-meta-{rep}"))
    elif imp != "Mstar":
        raise SystemExit(imp)
    lin = AL.Lineage3(f"r{rep}_{imp}", st, 10.0 if dev else BUDGET, out, ts, as_, rng_key=f"meta3|{rep}", meta_edits=False,
                      use_P=True, de_seeds=ds, de_adm_seeds=das, cap_s=AL.SRC_CAP_S)
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = lin.rows
    print(lin.name, "tasks", len(s), "solved", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s), "L", len(lin.st["L"]),
          "R", len(lin.st["R"]), "skills", len(lin.st["DE"]["skills"]), "stop", lin.stop_reason, "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
