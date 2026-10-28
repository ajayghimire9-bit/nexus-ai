"""Dev-only reproduction (NOT LOCKED): is a late supplier unit shift (s5 unit_shift at tick 13, after traffic_spike at 11)
detected? de5 dev worlds; NEXUS_Synth (oop) and the R2 template operator, each on its own build.
  python scripts/oop_dev_unitshift.py OUT.json seeds"""
import json, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import oop_run as RR
from nexus import oop_env as E
from nexus.wave31_evaluator import ledger_append

FORCED = [("traffic_spike", 11), ("unit_shift", 13)]


def main(outp, seeds):
    t0 = time.perf_counter()
    orig = E.ops_world
    E.ops_world = lambda w, split, seed, forced=None: orig(w, split, seed, forced=FORCED)
    res = {}
    try:
        for s in seeds:
            w = E.make_world(s, "dev")
            out = RR.run_project(s, w, "dev", ["NEXUS_Synth", "NEXUS_Template"], ROOT / "runs/oop/unitshift_art", forced=False,
                                 secondary=False)
            res[w["spec"]["project"]] = {a: dict(e2e=v["e2e_correct"], silent=(v["ops"] or {}).get("eval", {}).get("silent"),
                                                 ledger=[x for x in (v["ops"] or {}).get("ledger", []) if x["kind"] in
                                                         ("false_alarm", "repaired", "escalated", "metadata_change_no_unit_change")])
                                         for a, v in out["arms"].items()}
            print(s, {a: (v["e2e"], v["silent"]) for a, v in res[w["spec"]["project"]].items()}, flush=True)
    finally:
        E.ops_world = orig
        Path(outp).write_text(json.dumps(res, indent=1, default=str))
        ledger_append(dict(run="oop-dev-unitshift", wall_s=time.perf_counter() - t0, status="COMPLETE"))


if __name__ == "__main__":
    main(sys.argv[1], [int(x) for x in sys.argv[2].split(",")])
