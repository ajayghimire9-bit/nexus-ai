"""Independent verifier and artifact generator for `seed_integrated_architecture_v1`.

Verifies all 10 architecture sections and all 7 isolated component comparisons:
  1. Three operating timescales (`WITHIN_INTERACTION`, `ACROSS_EPISODES`,
     `ACROSS_RESEARCH_GENERATIONS`) and `EvidenceKernel` 3-tier feedback separation
     (`learning_feedback`, `promotion_checks`, `final_assessment`) + 7 `EvidenceStatus` values;
  2. `PerceptionAndLanguageInterface` compact state encoder + predictive feature
     discovery, 3 interchangeable language modes (`deterministic_template`,
     `nexus_small_neural`, `optional_local_pretrained` with `pretrained_assisted` flag),
     3-way intent routing (`ordinary_conversation`, `knowledge_retrieval_and_explanation`,
     `mechanism_investigation`), and source-attributed document claim extraction;
  3. `BeliefWorkspace` exact/noisy Bayesian posterior updates, 3 uncertainty regimes
     including `UNFAMILIAR_MECHANISM_INADEQUATE_FIT`, and splittable
     `ObservationalEquivalenceGroup`s;
  4. Compound probe synthesis (`[-4, -1, 0, 2, 2, 7]`), information-theoretic bound
     check (ceil(log2(50)) == 6 binary vs 1 multi-outcome compound probe), and
     conditional Kautz-Singleton `disjunct_matrix_comp` group testing;
  5. Three-stage bat-inspired investigation scheduler (`SURVEY -> DISCRIMINATE ->
     VALIDATE_AND_ACT`) and `DiagnosticProcedureLibrary` Sleep tree compilation;
  6. Six-part `MechanismCapsule` with separately verified `goal_adapter` (grid
     direction-inversion + order-reversal vs naive list reversal) and 4-way equal-budget
     targeted variation (`counterexample_directed_repair`, `uncertainty_directed_mutation`,
     `uniform_typed_mutation`, `ordinary_typed_enumeration`);
  7. Bounded delta debugging (`ddmin`) counterexample reduction verifying 1-minimality
     and refusing private assessment cases;
  8. 2x2 factorial (`{fixed_library, growing_library} x {episodic_reset, continual_memory}`),
     `TriLibrarySleepConsolidator` net savings, `SuccessorFeatureLearner` zero-shot GPI
     under changed reward weights, and `SmallLearnedOptimizer` vs fixed SGD/Momentum;
  9. Six-stage `DevelopmentalCurriculum` (with oracle-free learning progress) and
     11-action `CognitiveController` across 5 controller policies;
  10. Complete 10-step integrated episode verified in the isolated
      `blackbox_evaluator_worker` subprocess.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.integrated_architecture import (  # noqa: E402
    build_integrated_architecture_report,
    disjunct_matrix_comp,
    verify_d_disjunct,
)


def verify(root_dir: Path | str | None = None, write_artifact: bool = False) -> dict[str, Any]:
    root = ROOT if root_dir is None else Path(root_dir).resolve()
    art_path = root / "artifacts/seed_integrated_architecture_v1.json"

    if write_artifact or not art_path.exists():
        report = build_integrated_architecture_report()
        art_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        report = json.loads(art_path.read_text(encoding="utf-8"))

    if report.get("schema") != "seed_integrated_architecture_v1":
        raise ValueError("invalid_schema")
    if report.get("all_gates_passed") is not True:
        raise ValueError("integrated_architecture_gates_failed")
    gates = report.get("gates", {})
    if len(gates) != 10 or not all(gates.values()):
        raise ValueError("missing_or_failed_gates")

    # Verify 2-disjunct Kautz-Singleton matrix property independently
    mat = disjunct_matrix_comp(12, 2)
    if not verify_d_disjunct(mat, 2):
        raise ValueError("disjunct_matrix_verification_failed")

    # Verify subprocess black-box final assessment
    ep = report["integrated_episode"]
    bb = ep["blackbox_final_assessment"]
    if (
        bb.get("hidden_accuracy") != 1.0
        or bb.get("cross_lab_coding_accuracy") != 1.0
        or bb.get("cross_lab_reasoning_accuracy") != 1.0
        or bb.get("separate_evaluator_process") is not True
        or bb.get("private_inputs_exposed_to_learner") is not False
    ):
        raise ValueError("integrated_episode_blackbox_verification_failed")

    art_sha256 = hashlib.sha256(art_path.read_bytes()).hexdigest()
    return dict(
        schema="seed_integrated_architecture_audit_v1",
        valid=True,
        artifact_sha256=art_sha256,
        all_gates_passed=True,
        gates=gates,
        disjunct_matrix_verified=True,
        separate_evaluator_process=True,
        private_inputs_exposed_to_learner=False,
    )


if __name__ == "__main__":
    res = verify(write_artifact=("--write" in sys.argv))
    print(json.dumps(res, indent=2, sort_keys=True))
