"""NEXUS Phase 13 (NOT LOCKED): program-aware active investigation, a trainable task-conditioned Delta-State selector with
counterfactual regret demotion, and out-of-sandbox SQL sub-AST localize-and-lift repair.

Modules (imported lazily; nothing runs on package import):
  proposals13        program-aware input proposals synthesised from candidate ASTs (boundary constants, NULLs in read columns,
                     unmatched join keys, multi-row duplicate partition / group keys) plus Shadow-Edge Version Spaces: no permanent
                     passthrough or COUNT(*) lock; shadow alternatives (coalesce / count(col) / left-join variants) stay admissible
                     until an executed observation falsifies them.
  selector13         trainable task-conditioned Delta-State selector over proposal features; counterfactual regret auditing that
                     demotes the weights of shortcuts whose acceptance was later falsified (learned state, not hand edits).
  pipeline_lifter13  multi-stage SQL pipeline localisation: preserve stages that reproduce their observed outputs, lift the broken
                     sub-AST into the atomic synthesizer, and compile the verified repair back to native SQL.
  runner13           bounded experiment runner (--grant-seconds; <= 5000 full checks per row) comparing Fixed, Random, Untrained and
                     Trained controls under identical query budgets and strict work caps across seeded streams rep0 / rep1, with
                     source-learning / evaluation isolation.

Attribution: everything in this package is engineering machinery written by the engineering team. What NEXUS learns autonomously
is only the state these modules produce at run time (admitted functions, trained selector / guide weights, regret updates), which
the runner records separately from the code.
"""
from __future__ import annotations

PHASE = 13

# Pre-registered per-row inner-loop work caps shared by every arm (identical to synth12's strict caps).
WORK_CAPS = dict(full_checks=5000, rel_evals=4000, micro_evals=400000, constructed_asts=400000)

__all__ = ["PHASE", "WORK_CAPS", "proposals13", "selector13", "pipeline_lifter13", "runner13"]
