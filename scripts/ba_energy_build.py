"""Energy build tasks under an acceptance check (NOT LOCKED).  python scripts/ba_energy_build.py ARM ACCEPT TRACK:SPLIT
The E.meter lifecycle of every energy project (seed % 4 == 3) of the split is learned at BUILD time from ticks 1-8 with the arm's
growth rule + the declared contract, then scored exact on ticks 9-16. Task memory is reset per project.
ARM: hand | learned | shuffled | random.  Writes artifacts/ba_dev/energy_<ARM>_<ACCEPT>_<SPLIT>.json."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import oc_seeds, ba_seeds, t7_platform as T7, ba_learn as BL, ba_energy as BE, seed_registry as R  # noqa: F401
import ba_eps
ART = Path(__file__).resolve().parents[1] / "artifacts/ba_dev"
arm, accept, ts = sys.argv[1], sys.argv[2], sys.argv[3]
pol = ba_eps.policy(arm, accept)
rows = []
for s in [x for x in R.REGISTRY[tuple(ts.split(":"))] if x % 4 == 3]:
    P = T7.Project(s, "dev")
    assert P.domain == "energy"
    ep = BE.ProjEp(P)
    r = BL.learn_episode(ep, pol, accept=accept, contract=True, seed=s)
    rows.append(dict(seed=s, fault=P.fault, **{k: r[k] for k in ("accepted", "exact", "silent", "abstain", "unaccepted_exact", "queries",
                                                                 "cpu_s", "steps", "actions", "label", "scope")}))
    print(s, P.fault, r["accepted"], r["exact"], r["silent"], r["queries"], r["cpu_s"], r["actions"], flush=True)
(ART / f"energy_{arm}_{accept}_{ts.split(':')[1]}.json").write_text(json.dumps(rows, indent=1, default=str))
print(arm, accept, "correct", sum(r["exact"] for r in rows), "/", len(rows), "silent", sum(r["silent"] for r in rows),
      "abstain", sum(r["abstain"] for r in rows), "queries", sum(r["queries"] for r in rows))
