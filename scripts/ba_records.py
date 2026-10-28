"""Meta-training records for the learned growth rule under an acceptance check (NOT LOCKED).  python scripts/ba_records.py ACCEPT
From artifacts/ba_dev/eps_explore_<ACCEPT>_ep_train_*.jsonl (random growth on oc/ep_train, dev): every growth step logged with
signature s and action a gets reward = 1 if the episode ended ACCEPTED within 2 further steps, minus 0.02 x steps remaining
(learner-visible signals only - exactness is never seen). Same rule as c84fc76 scripts/oc_p2_records.py; acceptance is now the
bounded check. Writes artifacts/ba_dev/records_<ACCEPT>.jsonl."""
import json, sys
from pathlib import Path
ART = Path(__file__).resolve().parents[1] / "artifacts/ba_dev"
acc = sys.argv[1]
recs, n = [], 0
for f in sorted(ART.glob(f"eps_explore_{acc}_ep_train_*.jsonl")):
    for l in f.read_text().splitlines():
        r = json.loads(l)
        n += 1
        k = len(r["log"])
        for st in r["log"]:
            left = k - st["step"]
            recs.append(dict(sig=st["sig"], action=st["action"], reward=(1.0 if r["accepted"] and left <= 2 else 0.0) - 0.02 * left))
(ART / f"records_{acc}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in recs))
print(len(recs), "records from", n, "episodes")
