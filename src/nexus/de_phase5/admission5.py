"""Phase 5 corrected admission rule (NOT LOCKED; replaces, for Phase 5 only, the Phase 4 rules in de_phase4.lineage
admission_round / meta_rollout, which admitted a cheaper FAILURE when both versions verified 0 projects).

admit(base, trial, min_saving) on paired per-project rows {pid: dict(correct, completed, wrong, cost)}:
  correct    verified completion, or a justified abstention where abstention is the right outcome
  completed  verified completion only (the set cost claims are made on)
  1 quality must be preserved: trial wrong <= base wrong and trial correct >= base correct
  2 a QUALITY benefit (more correct) is a benefit
  3 otherwise an efficiency claim needs the SAME NON-EMPTY set of correctly completed projects: cost is compared only on
    projects completed by both, and the trial must not lose any project the base completed (coverage changes are
    reported separately); never when both complete 0 projects
Costs are kept per resource (sqlite_runs, spark_runs, wall_s, questions); the decision uses cost-seconds = wall_s +
QUESTION_COST_S x questions (raw candidate counts are not interchangeable across engines)."""
from __future__ import annotations


def cost_s(row, q_cost):
    return row["cost"]["wall_s"] + q_cost * row["cost"].get("questions", 0)


def admit(base, trial, min_saving=0.1, q_cost=2.0):
    pids = sorted(set(base) & set(trial))
    cb, ct = sum(base[p]["correct"] for p in pids), sum(trial[p]["correct"] for p in pids)
    wb, wt = sum(base[p]["wrong"] for p in pids), sum(trial[p]["wrong"] for p in pids)
    done_b = {p for p in pids if base[p]["completed"]}
    done_t = {p for p in pids if trial[p]["completed"]}
    rec = dict(correct=[cb, ct], wrong=[wb, wt], completed=[len(done_b), len(done_t)], lost=sorted(done_b - done_t),
               gained=sorted(done_t - done_b))
    if wt > wb:
        return False, dict(rec, reason="more wrong submissions")
    if ct < cb:
        return False, dict(rec, reason="fewer correct outcomes")
    if ct > cb:
        return True, dict(rec, reason="more correct outcomes")
    common = sorted(done_b & done_t)
    if not common:
        return False, dict(rec, reason="no common correctly completed project: no efficiency claim (equal-zero loophole closed)")
    if done_b - done_t:
        return False, dict(rec, reason="loses a project the base completed")
    xb, xt = sum(cost_s(base[p], q_cost) for p in common), sum(cost_s(trial[p], q_cost) for p in common)
    rec.update(common=len(common), cost_common=[round(xb, 3), round(xt, 3)])
    if xt <= (1 - min_saving) * xb:
        return True, dict(rec, reason=f"cheaper by >= {min_saving:.0%} on the same correctly completed projects")
    return False, dict(rec, reason="no quality-preserving benefit")
