"""Part 2, full energy projects (NOT LOCKED).  python scripts/oc_energy_build.py ARM
The E.meter lifecycle of every energy project (seed % 4 == 3) in oc/edev 13001-13048 (12 projects; D1/D2 dev regimes) is
learned at BUILD time from ticks 1-8 with the arm's growth policy + the declared contract, then scored exact on ticks 9-16
(the class runs over the whole stream; only ticks 9-16 are scored). Task memory is reset per project.
ARM: hand | meta | random | shuffled | full (the f45da4e covered learner, all hypothesis space at once)"""
import json, random, sys
sys.path.insert(0, "scripts")
sys.path.insert(0, "src")
from pathlib import Path
from nexus import oc_seeds, t7_platform as T7, oc_learner as OL, u5_statesplit as SP, u5_stateful as SF, seed_registry as R  # noqa: F401
ART = Path(__file__).resolve().parents[1] / "artifacts/oc_dev"
EMETER_CONTRACT = {"OPEN": dict(reads_value=False), "READ": dict(reads_value=True), "ADJUST": dict(reads_value=True),
                   "CLOSE": dict(reads_value=False), "DISPUTE": dict(reads_value=False), "ESTIMATE": dict(reads_value=True)}


class ProjEp:
    def __init__(self, P):
        self.P, self.seed = P, P.seed
        self.train = [e for t in range(1, 9) for e in P.ticks[t]["B"]]
        self.all = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
        self.y_train = P.ref_B(self.train)
        self.n_queries = 0
        self.contract = dict(EMETER_CONTRACT)

    def query(self, evs):
        self.n_queries += 1
        return self.P.ref_B(evs)

    def score(self, run_fn):
        want = self.P.ref_B(self.all)
        got = run_fn(self.all)
        n8 = len(self.train)
        ok = [SF.rows_eq(list(map(tuple, g)), w) for g, w in zip(got[n8:], want[n8:])]
        return dict(exact=all(ok), key_acc=sum(ok) / max(1, len(ok)))


arm = sys.argv[1]
recs = [json.loads(l) for l in (ART / "p2_records.jsonl").read_text().splitlines()] if arm in ("meta", "shuffled") else []
if arm == "shuffled":
    sigs = [r["sig"] for r in recs]
    random.Random(13).shuffle(sigs)
    recs = [dict(r, sig=s) for r, s in zip(recs, sigs)]
pol = {"hand": OL.hand_policy, "random": OL.random_policy, "full": OL.hand_policy}.get(arm) or OL.TablePolicy(recs)
rows = []
for s in [x for x in R.REGISTRY[("oc", "edev")] if x % 4 == 3]:
    P = T7.Project(s, "dev")
    assert P.domain == "energy"
    ep = ProjEp(P)
    r = OL.learn_episode(ep, pol, OL.H_FULL if arm == "full" else None, contract=True, seed=s)
    rows.append(dict(seed=s, fault=P.fault, **{k: r[k] for k in ("certified", "exact", "silent", "queries", "cpu_s", "steps", "actions")}))
    print(s, P.fault, r["certified"], r["exact"], r["silent"], r["queries"], r["cpu_s"], r["actions"], flush=True)
(ART / f"p2_energy_{arm}.json").write_text(json.dumps(rows, indent=1, default=str))
print(arm, "exact", sum(r["exact"] for r in rows), "/", len(rows), "silent", sum(r["silent"] for r in rows), "queries", sum(r["queries"] for r in rows))
