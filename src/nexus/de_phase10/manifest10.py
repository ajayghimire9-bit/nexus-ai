"""Phase 10 partitions, repository / family splits and the frozen 48-target manifest (NOT LOCKED).

REPOSITORIES. A generated project's repository identity is its schema-name pool (world6 names: 'base' vs 'heldout') plus
its seed lineage. Repos_Train = base-name repositories; Repos_Eval = held-out-name repositories. No external repository is
available offline (no out-of-sandbox ingestion is performed; recorded as a limitation).
FAMILIES. Seen families: P1-P7, X1, X2 with every fault mechanism EXCEPT the held-out mutation family 'require'
(P6 require-nonempty); training generation rejects any project whose faults include it. Held-out families: Tier 3 (P8
migration, P9 hybrids A / B / C) and the 'require' mutation family (P6 projects whose faults include it).
Ranges (disjoint at import): agi10de/dev 81000-81999, agi10de/train 82000-83999 (wake stream 0-199, dreams 200-599,
admission 600-899, pi* pool / confirmation 900-999, M* rollout stream 1000-1199, M* validation 1200-1299, C3 / C2 use the same
wake stream), ONE-USE agi10de/eval 84000-84099 (48 targets)."""
from __future__ import annotations

from nexus import seed_registry as R
from nexus.de_phase9 import blocks9 as B9                  # noqa: F401  (registers Phase 1-9 ranges first)

RANGES = {("agi10de", "dev"): range(81000, 82000), ("agi10de", "train"): range(82000, 84000), ("agi10de", "eval"): range(84000, 84100)}
ONE_USE = {("agi10de", "eval")}
R.REGISTRY.update(RANGES)
R.ONE_USE -= set(RANGES) - ONE_USE
R.ONE_USE |= ONE_USE
R._check_disjoint()
HELD_OUT_FAULTS = {"require"}
T = RANGES[("agi10de", "train")].start
TRAIN = dict(wake=range(T, T + 200), dream=range(T + 200, T + 600), admit=range(T + 600, T + 900), pool=range(T + 900, T + 1000),
             mroll=range(T + 1000, T + 1200), mval=range(T + 1200, T + 1300))
CHECKPOINTS = (25, 60, 120)
MC = [dict(paradigm="P5", engine=e, modes=m, fault_p=0.4) for e in ("sqlite", "duckdb")
      for m in (dict(watermark="conflict_approved", checkpoint="conflict_approved"), dict(watermark="conflict_approved", checkpoint="missing"),
                dict(watermark="missing", checkpoint="conflict_approved"))]


def train_spec(i, seed):
    """Balanced Repos_Train stream: cycles of P1-P7, X1, X2 (blocks9.balanced_stream), base names."""
    c, sp, _ = B9.balanced_stream([seed] * 9 * (i // 9 + 1), i // 9 + 1, "agi10-train")[i]
    return dict(sp, names="base")


def pool_specs():
    """pi* replay pool (8) and confirmation (6): multi-conflict LOPO validation tasks + legacy / benign / undecided."""
    lf = B9.LF
    pool = [MC[0], MC[1], MC[3], MC[4], dict(paradigm="P7", engine="duckdb", **lf), dict(paradigm="P1", engine="sqlite", **lf), dict(paradigm="P2", engine="duckdb"),
            dict(paradigm="P1", engine="duckdb", dp_mode="undecided")]
    conf = [MC[2], MC[5], MC[0], MC[4], dict(paradigm="P7", engine="sqlite", dp_mode="conflict_approved"), dict(paradigm="P3", engine="sqlite")]
    return [dict(s, names="base") for s in pool], [dict(s, names="base") for s in conf]


def eval_manifest():
    """48 one-use targets in Repos_Eval (held-out names). 24 SEEN families on unfamiliar repositories (8 multi-conflict P5,
    16 P1-P7 / X1 / X2 with mixed requirement conditions) + 24 HELD-OUT (8 P8, 4 P9.A multi-conflict modes, 4 P9.B, 4 P9.C,
    4 P6 with the held-out 'require' mutation family). >= 12 targets are built to have K >= 2 simultaneous conflicts."""
    lf = B9.LF
    seen = [dict(MC[i % 6], group="seen", mc=True) for i in range(8)]
    other = [dict(paradigm="P1", engine="sqlite", dp_mode="conflict_approved"), dict(paradigm="P1", engine="duckdb", **lf), dict(paradigm="P2", engine="duckdb"),
             dict(paradigm="P2", engine="sqlite"), dict(paradigm="P3", engine="duckdb"), dict(paradigm="P3", engine="sqlite"), dict(paradigm="P4", engine="duckdb"),
             dict(paradigm="P4", engine="sqlite"), dict(paradigm="P5", engine="duckdb", dp_mode="explicit"), dict(paradigm="P6", engine="sqlite"),
             dict(paradigm="P7", engine="duckdb", dp_mode="conflict_approved"), dict(paradigm="P7", engine="sqlite", **lf), dict(paradigm="X1"), dict(paradigm="X2"),
             dict(paradigm="P1", engine="duckdb", dp_mode="undecided"), dict(paradigm="P5", engine="sqlite", dp_mode="missing")]
    seen += [dict(s, group="seen", mc=False) for s in other]
    modes = ["explicit", "missing", "conflict_approved", "undecided", "explicit", "missing", "conflict_approved", "explicit"]
    held = [dict(paradigm="P8", dp_mode=modes[j], group="heldout", mc=False) for j in range(8)]
    held += [dict(paradigm="P9", hybrid="A", modes=dict(watermark="conflict_approved", checkpoint="conflict_approved", window_end="conflict_approved"),
                  group="heldout", mc=True) for _ in range(4)]
    held += [dict(paradigm="P9", hybrid="B", group="heldout", mc=False) for _ in range(4)]
    held += [dict(paradigm="P9", hybrid="C", dp_mode=("explicit", "missing")[j % 2], group="heldout", mc=False) for j in range(4)]
    held += [dict(paradigm="P6", engine=("sqlite", "duckdb")[j % 2], fault_p=1.0, require_fault=True, group="heldout_mutation", mc=False) for j in range(4)]
    out = []
    base = RANGES[("agi10de", "eval")].start
    for i, t in enumerate(seen + held):
        out.append(dict(t, names="heldout", seed=base + i, tier=3 if t["paradigm"] in ("P8", "P9") else 1 if t["paradigm"] in ("P1", "P2", "P3") else 2))
    return out
