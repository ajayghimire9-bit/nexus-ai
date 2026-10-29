"""Multi-world campaign Stage 3: improver versus improver (NOT LOCKED).
  python scripts/agi_meta.py run REP IMP [--dev]     IMP in Mstar, M0, Mrand; one metered 60 s process
Each clone starts from the identical frozen Full_r<REP> (R, L, pi) (artifacts/agi_freeze_source.json, digest-checked),
with an empty improver buffer, and runs the agent loop's learning steps for 60 charged s under a FIXED improver:
  Mstar  the lineage's learned M* (the Full endpoint's M)     M0  the original M0
  Mrand  the matched random improver: improver.m_random(random.Random(f"agi-mrand-meta-{REP}"))
No meta edits during Stage 3. Identical task stream for the three clones of a repetition: a fixed schedule over the 8
learning families x 4 levels (order seeded "agi-meta-sched-<REP>") on fresh agi/source_meta seeds 35000 + 300 * REP + k,
and the same admission sequence agi/admission 34000 + 300 * REP + 150 + k. Output artifacts/agi_meta/r<REP>_<IMP>.json."""
import json, random, sys, time
T_START = time.time()
from pathlib import Path  # noqa: E402
from nexus.campaign import agent_loop as AL, improver as I, seeds as SD, state as ST  # noqa: E402
ROOT = Path(__file__).resolve().parents[1]
BUDGET = 58.0


def schedule(rep, base):
    cells = [(w, f, lv) for (w, f) in SD.LEARN for lv in (1, 2, 3, 4)]
    random.Random(f"agi-meta-sched-{rep}").shuffle(cells)
    return [cells[k % len(cells)] + (base + k,) for k in range(300)]


def main(cmd, rep, imp, *flags):
    rep = int(rep)
    dev = "--dev" in flags
    if dev:
        src = json.loads((ROOT / f"artifacts/agi_dev/src/Full_r{rep}.json").read_text())
        st, digest = ST.from_json(src["state"]), None
        out, base, abase = ROOT / "artifacts/agi_dev/meta", 30400, 30950
    else:
        fr = json.loads((ROOT / "artifacts/agi_freeze_source.json").read_text())
        e = fr["endpoints"][f"Full_r{rep}"]
        st = ST.from_json(e["state"])
        assert ST.digest(st) == e["digest"]
        out = ROOT / "artifacts/agi_meta"
        base = SD.RANGES[("agi", "source_meta")].start + 300 * rep
        abase = SD.RANGES[("agi", "admission")].start + 300 * rep + 150
        if (out / f"r{rep}_{imp}.json").exists():
            raise SystemExit("meta clones are never rerun")
    if imp == "M0":
        st["M"] = json.loads(json.dumps(I.M0))
    elif imp == "Mrand":
        st["M"] = I.m_random(random.Random(f"agi-mrand-meta-{rep}"))
    elif imp != "Mstar":
        raise SystemExit(imp)
    lin = AL.Lineage(f"r{rep}_{imp}", st, 12.0 if dev else BUDGET, out, iter(()), range(abase, abase + 150), rng_key=f"meta|{rep}|{imp}",
                     schedule=[tuple(x) for x in schedule(rep, base)], meta_edits=False)
    lin.T0, lin.C0 = T_START, 0.0
    lin.run()
    s = lin.rows
    print(lin.name, "tasks", len(s), "solved", sum(r["solved"] for r in s), "silent", sum(r["silent"] for r in s), "rounds",
          len(lin.rounds), "L", len(lin.st["L"]), "R", len(lin.st["R"]), "stop", lin.stop_reason, "elapsed",
          round(lin.elapsed(), 1), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
