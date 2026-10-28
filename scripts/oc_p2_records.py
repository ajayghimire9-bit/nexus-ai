"""Build Part 2 meta-training records from the exploration episodes (NOT LOCKED): for every growth step logged with
signature s and action a, reward = 1 if the episode ended certified AND exact... no - the learner never sees exactness:
reward = 1 if the episode ended CERTIFIED within 2 further steps, minus 0.02 x steps remaining (learner-visible signals only)."""
import json
from pathlib import Path
ART = Path(__file__).resolve().parents[1] / "artifacts/oc_dev"
recs = []
for f in sorted(ART.glob("eps_explore_ep_train_*.jsonl")):
    for l in f.read_text().splitlines():
        r = json.loads(l)
        n = len(r["log"])
        for st in r["log"]:
            left = n - st["step"]
            recs.append(dict(sig=st["sig"], action=st["action"], reward=(1.0 if r["certified"] and left <= 2 else 0.0) - 0.02 * left))
(ART / "p2_records.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
print(len(recs), "records from", sum(1 for f in ART.glob("eps_explore_ep_train_*.jsonl") for _ in f.read_text().splitlines()), "episodes")
