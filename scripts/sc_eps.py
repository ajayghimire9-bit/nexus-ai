"""Separate growth-rule comparison (fallback disabled) on fresh micro-episodes (NOT LOCKED).
  python scripts/sc_eps.py ARM START N        ARM: learned | hand | shuffled | random
Identical to the ba Step 4 protocol: ba_learn.learn_episode(accept="bounded") - the growth learner alone, NO full-space fallback,
the frozen policies of ba_eps.policy (records artifacts/ba_dev/records_bounded.jsonl, sha256 in artifacts/ba_freeze.json), task
memory reset per episode; seeds sc/ep_held3 23000-23299 (fresh). Writes artifacts/sc_dev/eps_<ARM>_ep_held3_<START>.jsonl
(one row per episode, appended atomically line by line; resumable; self-limits to 780 s per call)."""
import json, resource, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexus import sc_seeds, oc_ocean as OC, ba_learn as BL, seed_registry as R  # noqa: F401
import ba_eps
ART = Path(__file__).resolve().parents[1] / "artifacts/sc_dev"
arm, start, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
pol = ba_eps.policy(arm, "bounded")
seeds = list(R.REGISTRY[("sc", "ep_held3")])[start:start + n]
out = ART / f"eps_{arm}_ep_held3_{start}.jsonl"
done = {json.loads(l)["seed"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
T0 = time.perf_counter()
with open(out, "a") as fh:
    for s in seeds:
        if s in done:
            continue
        if time.perf_counter() - T0 > 780:
            break
        ep = OC.Episode(s)
        w0 = time.perf_counter()
        r = BL.learn_episode(ep, pol, accept="bounded", seed=s)
        r.update(seed=s, regime=ep.regime, needs=ep.needs, wall_s=round(time.perf_counter() - w0, 3),
                 maxrss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 1),
                 out_of_alphabet=ep.regime == "new_kind" and ep.machine["extra"] not in {e["kind"] for e in ep.train}
                 and ep.machine["extra"] in {e["kind"] for e in ep.test})
        fh.write(json.dumps(r, default=str) + "\n")
        fh.flush()
print(arm, start, n, "rows", sum(1 for _ in open(out)))
