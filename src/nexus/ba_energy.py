"""Energy build tasks as episodes (NOT LOCKED): the E.meter lifecycle of a platform energy project, learned at BUILD time from
ticks 1-8 (labelled by the oracle) + counted membership queries, scored exact on ticks 9-16 (the class runs over the whole
stream; only ticks 9-16 are scored). Same construction as scripts/oc_energy_build.ProjEp (c84fc76), importable."""
from __future__ import annotations

from nexus import u5_stateful as SF

EMETER_CONTRACT = {"OPEN": dict(reads_value=False), "READ": dict(reads_value=True), "ADJUST": dict(reads_value=True),
                   "CLOSE": dict(reads_value=False), "DISPUTE": dict(reads_value=False), "ESTIMATE": dict(reads_value=True)}


class ProjEp:
    def __init__(self, P):
        self.P, self.seed = P, P.seed
        self.train = [e for t in range(1, 9) for e in P.ticks[t]["B"]]
        self.all = [e for t in range(1, 17) for e in P.ticks[t]["B"]]
        self.test = self.all
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
