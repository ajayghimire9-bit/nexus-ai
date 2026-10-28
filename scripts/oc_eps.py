"""Run one arm over a slice of micro-episodes (NOT LOCKED).  python scripts/oc_eps.py ARM SPLIT START N
ARM: p1_cov | p1_grey | p1_vs | p1_both | p2_meta | p2_random | p2_shuffled | explore (random policy, logging records)
Writes artifacts/oc_dev/eps_<ARM>_<SPLIT>_<START>.jsonl (one row per episode; task memory reset per episode)."""
import json, random, sys
sys.path.insert(0, "src")
from pathlib import Path
from nexus import oc_seeds, oc_ocean as OC, oc_learner as OL  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/oc_dev"
ART.mkdir(exist_ok=True)
arm, split, start, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
eps = OC.suite(split, n=n, start=start)
pol = OL.hand_policy
contract = vs = False
if arm in ("p1_grey", "p1_both"):
    contract = True
if arm in ("p1_vs", "p1_both"):
    vs = True
if arm in ("p2_random", "explore"):
    pol = OL.random_policy
if arm in ("p2_meta", "p2_shuffled"):
    recs = [json.loads(l) for l in (ART / "p2_records.jsonl").read_text().splitlines()]
    if arm == "p2_shuffled":
        sigs = [r["sig"] for r in recs]
        random.Random(13).shuffle(sigs)
        recs = [dict(r, sig=s) for r, s in zip(recs, sigs)]
    pol = OL.TablePolicy(recs)
import time as _time
out = ART / f"eps_{arm}_{split}_{start}.jsonl"
done = {json.loads(l)["seed"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
T0 = _time.perf_counter()
with open(out, "a") as fh:                                        # resumable: episodes already written are skipped
    for ep in eps:
        if ep.seed in done:
            continue
        if _time.perf_counter() - T0 > 800:                       # stay inside the 900 s call cap; resume next call
            break
        log = []
        r = OL.learn_episode(ep, pol, contract=contract, version_space=vs, cov_sample=0.25 if vs else 1.0, seed=ep.seed, log=log)
        r.update(seed=ep.seed, regime=ep.regime, needs=ep.needs, log=log)
        fh.write(json.dumps(r, default=str) + "\n")
        fh.flush()
print(arm, split, start, n, "done")
