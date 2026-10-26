"""Wave 26 Phase 5: stream schedule, drift retirement, empirical contracts never prune."""
from nexus.wave26_phase5 import LAGS, DriftingOpaque, EmpiricalContractStore, make_stream


def test_every_base_world_is_revisited_exactly_once_after_it():
    bases, order = make_stream(7)
    assert len(order) == 2 * len(bases)
    pos = {(w, v): i for i, (w, v) in enumerate(order)}
    lags = [pos[(b["wid"], 2)] - pos[(b["wid"], 1)] for b in bases]
    assert all(l >= 1 for l in lags) and all(b["lag"] in LAGS for b in bases)
    assert any(l >= 15 for l in lags) and any(l <= 7 for l in lags)     # all three lag buckets are exercised


def test_drift_retires_the_empirical_contract_at_the_first_counterexample():
    store = EmpiricalContractStore()
    ok, bad = DriftingOpaque(".", 2, False, store), DriftingOpaque(".", 2, True, store)
    ok([3, 1, 2])
    assert store.status[ok.name()] == "ACTIVE"
    bad([3, 1, 2])
    assert store.status[bad.name()] == "RETIRED_BY_DRIFT" and bad.name() in store.drift_used
