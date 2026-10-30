"""Phase 10G investigation layer (NOT LOCKED): dag10f plus ONE acceptance rule that closes the Phase 10F training wrong submission
(rep1 task 29, P10F.S_dirty.duckdb.postgres.104529; scripts/agi10g_diag_104529.py, artifacts/agi10g_diag_104529.json). Shared by every
arm, by training, dreams' contract guard and admission; operators, roles and the other rules are unchanged.

  necessary_dedup   a dedup whose key is NOT a documented unique key (schema.yml) must be NECESSARY: the same spec without that
                    dedup, with its post-dedup filters moved before it (identical semantics once there is no dedup), must FAIL a
                    visible public check or node contract. Otherwise visible evidence does not require the dedup and the simpler
                    repair is preferred (Occam): the candidate is not accepted and the search continues.
  104529 (confirmed): the path partitioned stg_orders by a distractor (tax_amount) whose non-null values collide ONCE on visible
  batch A; the partition drops clean order 164, whose customer reaches no visible output, and makes the post NOT NULL filter on the
  dirty total available (dag10d offers post filters only on deduped relations). 20 of the 25 accepted paths of that shape are
  hidden-wrong (hidden batches collide more). dag10f.justified_dedup could not see it (a real non-null duplicate group exists).
  It also subsumes the Phase 10E 101524 shape (a duplicate-free partition is always unnecessary).
  The truth never violates it (its dedups are on documented unique keys). Like the other rules it is a spec + visible-data check and
  is NOT charged as an execution (disclosed; it re-interprets only candidates holding a non-documented dedup)."""
from __future__ import annotations

from nexus.de_phase10d import dag10d as D10, ir10d as IR
from nexus.de_phase10f import dag10f as DF


def without_dedup(specs, rel):
    t = specs[0][rel]
    alt = dict(t, dedup=None, pre=list(t.get("pre", [])) + list(t.get("post", [])), post=[])
    return [dict(specs[0], **{rel: alt})] + list(specs[1:])


class Inv10g(DF.Inv10f):
    def rules(self, specs):
        out = super().rules(specs)
        for rel, t in sorted(specs[0].items()):
            d = t.get("dedup")
            if not d or any((rel, c) in self.ukeys for c in IR.cols_of(d["key"])):
                continue
            saved = dict(self.runs)
            try:
                ev = D10.Inv10d.run(self, without_dedup(specs, rel), True)
            finally:
                self.runs = saved                                   # uncharged (a rule, not a candidate execution)
            if not ev.get("error") and ev["ok"]:
                out.append(f"necessary_dedup:{rel}")
        return sorted(set(out))
