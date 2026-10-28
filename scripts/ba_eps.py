"""Run one growth arm over a slice of micro-episodes under an acceptance check (NOT LOCKED).
  python scripts/ba_eps.py ARM ACCEPT TRACK:SPLIT START N [SEEDS_FILE]
ARM: hand | learned | shuffled | random | explore (random growth, logging records for the learned rule)
ACCEPT: coverage | bounded.  TRACK:SPLIT e.g. oc:ep_train, oc:ep_val, ba:ep_held2.
Writes artifacts/ba_dev/eps_<ARM>_<ACCEPT>_<SPLIT>_<START>.jsonl (one row per episode; task memory reset per episode);
resumable (episodes already written are skipped; self-limits to 800 s per call)."""
import json, random, sys, time
from pathlib import Path
from nexus import oc_seeds, ba_seeds, oc_ocean as OC, oc_learner as OL, ba_learn as BL, seed_registry as R  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/ba_dev"
ART.mkdir(exist_ok=True)


def policy(arm, accept="bounded"):
    if arm in ("random", "explore"):
        return OL.random_policy
    if arm == "hand":
        return OL.hand_policy
    recs = [json.loads(l) for l in (ART / f"records_{accept}.jsonl").read_text().splitlines()]
    if arm == "shuffled":                                      # shuffled episode-to-extension pairs (signature permuted)
        sigs = [r["sig"] for r in recs]
        random.Random(13).shuffle(sigs)
        recs = [dict(r, sig=s) for r, s in zip(recs, sigs)]
    return OL.TablePolicy(recs)


if __name__ == "__main__":
    arm, accept, ts, start, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    track, split = ts.split(":")
    seeds = list(R.REGISTRY[(track, split)])[start:start + n]
    if len(sys.argv) > 6:
        seeds = [s for s in json.loads(Path(sys.argv[6]).read_text())][start:start + n]
    pol = policy(arm, accept)
    out = ART / f"eps_{arm}_{accept}_{split}_{start}.jsonl"
    done = {json.loads(l)["seed"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    T0 = time.perf_counter()
    with open(out, "a") as fh:
        for s in seeds:
            if s in done:
                continue
            if time.perf_counter() - T0 > 800:
                break
            ep = OC.Episode(s)
            log = []
            r = BL.learn_episode(ep, pol, accept=accept, seed=s, log=log)
            r.update(seed=s, regime=ep.regime, needs=ep.needs, log=log)
            fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
    print(arm, accept, ts, start, n, "rows", len(done) + sum(1 for _ in open(out)) - len(done))
