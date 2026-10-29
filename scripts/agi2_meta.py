"""Phase 2 Stage 3: full-trajectory improver versus improver (NOT LOCKED).
  python scripts/agi2_meta.py run REP IMP [--dev]     IMP in Mstar, M0, Mrand; one metered 45 s process
Each clone starts from the identical frozen Full_r<REP> (R, L, P, pi) (artifacts/agi2_freeze_source.json, digest-checked),
with an empty solved-solution buffer, and runs a COMPLETE multi-round learning trajectory controlled entirely by its
improver: its own curriculum (task choice), admission rule, pruning, archive policy and schedule.
  Mstar = the Full endpoint's M;  M0 = the original M0;  Mrand = improver.m_random(random.Random(f"agi2-mrand-meta-{REP}"))
Paired environment randomness: the three clones of a repetition draw from the identical source-meta seed stream
(agi2/source_meta 42600 + 300 * REP + k), the identical admission stream (agi2/admission 40600 + 300 * REP + 200 + k) and
the same RNG keys, but their actions are free. No meta-edits during Stage 3. Output artifacts/agi2_meta/r<REP>_<IMP>.json."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign2 import agent_loop as AL, improver as I, seeds as SD, state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
BUDGET = 43.5


def main(cmd, rep, imp, *flags):
    rep = int(rep)
    dev = "--dev" in flags
    if dev:
        st = ST.from_json(json.loads((ROOT / f"artifacts/agi2_dev/src/Full_r{rep}.json").read_text())["state"])
        out, base, abase = ROOT / "artifacts/agi2_dev/meta", SD.RANGES[("agi2", "dev")].start + 300, SD.RANGES[("agi2", "dev")].start + 950
    else:
        e = json.loads((ROOT / "artifacts/agi2_freeze_source.json").read_text())["endpoints"][f"Full_r{rep}"]
        st = ST.from_json(e["state"])
        assert ST.digest(st) == e["digest"]
        out = ROOT / "artifacts/agi2_meta"
        base = SD.RANGES[("agi2", "source_meta")].start + 300 * rep
        abase = SD.RANGES[("agi2", "admission")].start + 300 * rep + 200
        if (out / f"r{rep}_{imp}.json").exists():
            raise SystemExit("meta clones are never rerun")
    if imp == "M0":
        st["M"] = json.loads(json.dumps(I.M0))
    elif imp == "Mrand":
        st["M"] = I.m_random(random.Random(f"agi2-mrand-meta-{rep}"))
    elif imp != "Mstar":
        raise SystemExit(imp)
    lin = AL.Lineage(f"r{rep}_{imp}", st, 10.0 if dev else BUDGET, out, range(base, base + 300), range(abase, abase + 100),
                     rng_key=f"meta2|{rep}", meta_edits=False, use_P=True)
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = lin.rows
    print(lin.name, "tasks", len(s), "solved", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s), "rounds",
          len(lin.rounds), "L", len(lin.st["L"]), "R", len(lin.st["R"]), "P", len(lin.st["P"]), "stop", lin.stop_reason,
          "elapsed", round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
