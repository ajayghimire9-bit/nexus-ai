"""Phase 10B partitions (NOT LOCKED). Disjoint at import: agi10bde/dev 90000-90999, agi10bde/train 86000-89999 (repetition r
block 86000 + 2000 r: wake 0-199, dreams 200-599, admission 600-899, pool 900-999, M* rollout stream 1000-1199, M* validation
1200-1299; the two repetitions have independent exogenous streams), ONE-USE agi10bde/eval 85000-85099 (48 fresh targets with
the Phase 10 structure: 24 seen families on held-out-name repositories incl. 8 multi-conflict P5, 20 Tier 3 P8 / P9, 4 P6 with
the held-out 'require' mutation family). Every earlier project, incl. all Phase 10 targets, is development data."""
from nexus import seed_registry as R
from nexus.de_phase10 import manifest10 as MF               # noqa: F401  (registers Phase 1-10 ranges first)

RANGES = {("agi10bde", "dev"): range(90000, 91000), ("agi10bde", "train"): range(86000, 90000), ("agi10bde", "eval"): range(85000, 85100)}
ONE_USE = {("agi10bde", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()


def train(rep):
    b = RANGES[("agi10bde", "train")].start + 2000 * rep
    return dict(wake=range(b, b + 200), dream=range(b + 200, b + 600), admit=range(b + 600, b + 900), pool=range(b + 900, b + 1000),
                mroll=range(b + 1000, b + 1200), mval=range(b + 1200, b + 1300))


def eval_manifest():
    base = RANGES[("agi10bde", "eval")].start
    out = []
    for i, t in enumerate(MF.eval_manifest()):
        out.append(dict(t, seed=base + i))
    return out
