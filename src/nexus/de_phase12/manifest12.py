"""Phase 12 seed namespaces and the FROZEN evaluation manifest (NOT LOCKED; frozen in commit 1, BEFORE any development tuning of the
disambiguation searcher).
  agi12/dev     120000-120999   development fixtures: ONLY Phase 11 families (already-seen mechanisms: threshold labels, latest per key,
                                conditional sums, coalescing, filters, pre-aggregated joins, W3 / W7 compositions) - never a Suite 1 mechanism
  agi12/suite1  121000-121099   ONE-USE: Fresh_Ambiguous_Compositions_24 = tasks12 mechanisms M1-M6 x instances 0-3 (2-3 composed)
Suite 2 (Phase11_Regression_Audit_24) re-evaluates the Phase 11 Suite 1 targets (agi11/suite1 113000-113023, already consumed) as an
owner-requested DIAGNOSTIC regression; it is not a new one-use evaluation and never replaces a Phase 11 row.
Phase 11 history (recorded): the Phase 11 composition families W1-W8 were run on agi11/dev seeds during Phase 11 Stage 1 timing; the
Suite 1 targets were W1-W8 instances on fresh seeds."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase11 import manifest11 as M11               # noqa: F401  (registers Phase 1-11 ranges first)
from nexus.de_phase12 import tasks12 as T

RANGES = {("agi12", "dev"): range(120000, 121000), ("agi12", "suite1"): range(121000, 121100)}
ONE_USE = {("agi12", "suite1")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
DEV_KINDS = ("flag", "dedup", "condsum", "coalesce", "filtmap", "preagg", "W3", "W7")


def suite1():
    b = RANGES[("agi12", "suite1")].start
    return [dict(suite="suite1", mech=m, inst=i, seed=b + 6 * i + j) for i in range(4) for j, m in enumerate(T.MECHS)]


def suite2():
    return [dict(suite="suite2", kind=t["kind"], seed=t["seed"], pool=t["pool"]) for t in M11.suite1()]


def dev(n_each=1):
    b = RANGES[("agi12", "dev")].start
    return [dict(suite="dev", kind=k, seed=b + 10 * i + j, pool="base") for i, k in enumerate(DEV_KINDS) for j in range(n_each)]
