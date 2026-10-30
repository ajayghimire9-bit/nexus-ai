"""Phase 10F investigation layer (NOT LOCKED): dag10e plus ONE acceptance rule that closes the Phase 10E training wrong submission
(rep1, P10D.T_cdc_key+dirty.sqlite.postgres.101524; scripts/agi10f_diag_wrong*.py, artifacts/agi10f_diag_wrong*.json). Shared by
every arm, by training, dreams and admission; operators, roles, the other rules and the dream teacher are unchanged.

  justified_dedup   a dedup must partition by a DOCUMENTED unique key (ckey: a schema.yml unique test) or by a key that has at
                    least one duplicate group with a NON-NULL key on some visible batch (after the pre filters). Otherwise the
                    dedup removes no visible duplicate entity and its effect is on data the investigator cannot see.
  The 101524 failure: the submitted path partitioned stg_orders by a random distractor int column (legacy_id / shipping_cents /
  margin_bp: unique on both visible batches, so the partition changed nothing visible and passed deterministic_dedup) because a
  partition makes the POST-dedup NOT NULL filter on the dirty total available (dag10d offers post filters only on relations with
  a dedup); Occam pruning could not drop the partition (without it the post filter cannot be replayed). On the hidden batches the
  distractor values collide, the partition silently drops orders, and 5 of the 12 accepted paths of that shape are wrong.
  NULL keys (Stage 1 amendment, before any training): the forced-fork dev rehearsal (agi10fde/dev, artifacts/agi10f_dev/train)
  submitted 2 hidden-wrong repairs of shape add_partition -> add_filter(post NOT NULL) -> set_dedup on stg_orders, consistent with
  a partition on the dirty total itself: every dirty total is NULL, the NULLs form the only duplicate group, the post filter drops
  it, and visible output is unchanged. The diagnostic enumeration (scripts/agi10f_diag_dev_wrong.py) hit its 40 s cap, so the
  mechanism is NOT confirmed; a group of NULL keys no longer counts as a duplicate group. Residual risk (disclosed): a partition
  on a distractor whose non-null values happen to collide visibly, where the dropped row does not reach a visible output.
  The truth never violates the rule (its two dedups are on documented unique keys); a check on the rule is uncharged (spec +
  visible rows), like the Phase 10E rules."""
from __future__ import annotations

from nexus.de_phase10d import ir10d as IR
from nexus.de_phase10e import dag10e as D


def dup_groups(t, rows):
    d = t.get("dedup")
    if not d:
        return 0
    seen, dup = set(), set()
    for r in rows:
        if not all(IR.ev(c, r) is True for c in t.get("pre", [])):
            continue
        k = IR.ev(d["key"], r)
        if k in (None, ""):
            continue                                           # NULL keys are not entities: a group of NULLs is not a duplicate
        (dup if k in seen else seen).add(k)
    return len(dup)


class Inv10f(D.Inv10e):
    def rules(self, specs):
        out = super().rules(specs)
        for rel, t in sorted(specs[0].items()):
            d = t.get("dedup")
            if not d:
                continue
            if any((rel, c) in self.ukeys for c in IR.cols_of(d["key"])):
                continue
            n = 0
            for bid in range(len(self.batches)):
                try:
                    n += dup_groups(t, self.proj(t, bid))
                except Exception:                                   # noqa: BLE001
                    pass
            if n == 0:
                out.append(f"justified_dedup:{rel}")
        return sorted(set(out))
