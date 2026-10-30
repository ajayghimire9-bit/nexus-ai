"""Phase 12B seed namespaces and the FROZEN Fresh_Phase12B_24 manifest (NOT LOCKED; frozen in commit 1, BEFORE any Stage 2 diagnostic).
  agi12b/fresh  124000-124099  ONE-USE: Fresh_Phase12B_24 = tasks12b mechanisms N1 N2 N4 N6 N7 N8 x instances 0-3 (2-3 composed)
Stage 2 DIAGNOSTICS (already opened suites; owner-requested; never new one-use evaluations): Phase12_Diagnostic_24 = the Phase 12 Suite 1
tasks (121000-121023) and Phase11_Diagnostic_24 = the Phase 11 Suite 1 tasks (113000-113023)."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase12 import manifest12 as M12               # noqa: F401  (registers Phase 1-12 ranges first)
from nexus.de_phase12b import tasks12b as T

RANGES = {("agi12b", "fresh"): range(124000, 124100)}
ONE_USE = {("agi12b", "fresh")}
R.REGISTRY.update(RANGES)
R.ONE_USE |= ONE_USE
R._check_disjoint()


def fresh():
    b = RANGES[("agi12b", "fresh")].start
    return [dict(suite="fresh", mech=m, inst=i, seed=b + 6 * i + j) for i in range(4) for j, m in enumerate(T.MECHS)]


def p12():
    return [dict(t, suite="p12") for t in M12.suite1()]


def p11():
    return [dict(t, suite="p11") for t in M12.suite2()]
