#!/usr/bin/env python3
"""Source-only research registry. Does not train, collect, or select holdouts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONSULT = [
    "docs/NEXUS_CANONICAL_CURRENT_STATE.md",
    "docs/NEXUS_CODE_REUSE_MAP.md",
    "docs/NEXUS_FULL_RESEARCH_REGISTRY.md",
    "docs/NEXUS_FULL_RESEARCH_REUSE_AUDIT.md",
    "docs/NEXUS_HYPOTHESIS_REGISTER.md",
]

# Curated recoverable experiments. Missing commit/protocol fields stay incomplete.
EXPERIMENTS = [
    {
        "id": "V0.1",
        "title": "PPO actor-critic + factory + architecture evolution",
        "hypothesis": "A configurable PyTorch actor-critic with a spec factory and mutation loop can train on CartPole-scale tasks.",
        "implementation": ["src/nexus/rl", "src/nexus/nn", "src/nexus/evolution"],
        "commit": "incomplete",
        "protocol": None,
        "results": "README.md",
        "status": "historical_implemented",
        "artifacts": [],
        "reuse": "Not LEVEL 2 transfer. Do not treat architecture search as learning-to-learn.",
        "coverage": "partial",
    },
    {
        "id": "V0.4",
        "title": "Multi-seed PPO CartPole/Acrobot and architecture evolution",
        "hypothesis": "Matched PPO recipes solve CartPole and improve Acrobot versus random.",
        "implementation": ["src/nexus/rl/ppo.py", "src/nexus/evolution"],
        "commit": "incomplete",
        "protocol": None,
        "results": "README.md",
        "status": "historical_measured",
        "artifacts": [],
        "reuse": "Historical PPO evidence only. CartPole ceiling confounds evolution ranking.",
        "coverage": "partial",
    },
    {
        "id": "H-V05",
        "title": "LinUCB experiment selection versus random",
        "hypothesis": "A contextual bandit can select PPO experiments better than random on independent return.",
        "implementation": ["src/nexus/meta/controller.py", "src/nexus/meta/loop.py"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "synthetic_supported_real_not_established",
        "artifacts": [],
        "reuse": "Keep as a cheap scheduler. Not a path to learning-to-learn.",
        "coverage": "partial",
    },
    {
        "id": "H-V06",
        "title": "Sequential continual learning on CartPole variants",
        "hypothesis": "Naive/replay/EWC/multi-head beats specialists on CartPole variants.",
        "implementation": ["src/nexus/cl"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "not_established",
        "artifacts": [],
        "reuse": "Closed in V0.6.6. Do not retune the unsolved 8k PPO setup.",
        "coverage": "partial",
    },
    {
        "id": "H-V064",
        "title": "Encoder transfer versus scratch",
        "hypothesis": "A new head on a pretrained encoder beats scratch.",
        "implementation": ["src/nexus/cl"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "confounded_then_hurt_after_rms_control",
        "artifacts": [],
        "reuse": "Do not claim representation learning until RMS is controlled.",
        "coverage": "partial",
    },
    {
        "id": "H-V066",
        "title": "RMS-only reuse",
        "hypothesis": "Normalization reuse is the useful transfer mechanism.",
        "implementation": ["src/nexus/cl"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "supported_as_statistics_copy",
        "artifacts": [],
        "reuse": "Statistics copy, not an improving learner.",
        "coverage": "partial",
    },
    {
        "id": "H-V07",
        "title": "Residual world-model H=3 planning on CartPole",
        "hypothesis": "A residual world model supports planning better than greedy or random.",
        "implementation": ["src/nexus/world/dynamics.py", "src/nexus/world/planning.py"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "supported_on_cartpole",
        "artifacts": [],
        "reuse": "The only reliably positive WM planning result, and only on CartPole.",
        "coverage": "partial",
    },
    {
        "id": "H-V08",
        "title": "Fine-tune world model on shifted CartPole",
        "hypothesis": "Fine-tuning lowers error and raises return.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "mae_improved_control_not_established",
        "artifacts": [],
        "reuse": "Stop treating one-step MAE as the objective.",
        "coverage": "partial",
    },
    {
        "id": "H-V089",
        "title": "Past tasks reduce data needed on a new CartPole task D",
        "hypothesis": "ABC experience reduces data needed on D under MAE gating.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "falsified_under_frozen_protocol",
        "artifacts": [],
        "reuse": "Closed. Not learning-to-learn.",
        "coverage": "partial",
    },
    {
        "id": "H-V089g",
        "title": "Reptile versus matched multitask on Pendulum",
        "hypothesis": "First-order Reptile init adapts faster than matched-data multitask.",
        "implementation": ["scripts/run_meta_learning_pilot.py"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "reptile_worse_in_that_configuration",
        "artifacts": [],
        "reuse": "Not a general disproof of Reptile. Not learning-to-learn.",
        "coverage": "partial",
    },
    {
        "id": "H1",
        "title": "Planning-objective mismatch",
        "hypothesis": "Open-loop plan value is not first-action-plus-replan value.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md",
        "results": "docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md",
        "status": "supported_as_mechanism_class",
        "artifacts": [],
        "reuse": "Do not retune nested H=8 or score-correction from this class.",
        "coverage": "partial",
    },
    {
        "id": "H2",
        "title": "Q coverage or representation",
        "hypothesis": "Q coverage/representation explains closed 64-step Q/V failures.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md",
        "results": "docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md",
        "status": "explains_closed_qv_not_deployed_rule",
        "artifacts": [],
        "reuse": "Not the deployed H=16 receding rule.",
        "coverage": "partial",
    },
    {
        "id": "H3",
        "title": "H3 label collision — incomplete",
        "hypothesis": "Two later uses exist: occupancy-conditioned FiLM, and policy-induced distribution shift. A single H3 claim cannot be recovered without guessing.",
        "implementation": [],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_HYPOTHESIS_REGISTER.md",
        "status": "incomplete_label_collision",
        "artifacts": [],
        "reuse": "Cite the specific later ID, not a generic H3.",
        "coverage": "incomplete",
    },
    {
        "id": "H8",
        "title": "Source MCC RMS adaptation",
        "hypothesis": "Source MCC RMS improves 128-transition adaptation.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_MCC_NATIVE_RMS_RESULTS.md",
        "status": "not_established",
        "label": "mcc_native_rms_not_established",
        "artifacts": [],
        "reuse": "Closed unused MCC split. Do not reuse as a train label.",
        "coverage": "partial",
    },
    {
        "id": "H9",
        "title": "Source MCC residual scale",
        "hypothesis": "Source residual scale improves 128-transition adaptation.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_MCC_RESIDUAL_SCALE_RESULTS.md",
        "status": "harm_established",
        "label": "mcc_residual_scale_harm_established",
        "artifacts": [],
        "reuse": "Closed. Do not reuse the same MCC split.",
        "coverage": "partial",
    },
    {
        "id": "H10",
        "title": "MCC multitask at 128 transitions",
        "hypothesis": "Within-family MCC multitask improves 128-transition adaptation versus scratch.",
        "implementation": ["src/nexus/world/mcc_multitask_128.py"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_MCC_MULTITASK_128_RESULTS.md",
        "status": "supported_one_holdout",
        "label": "mcc_multitask_128_beats_scratch",
        "artifacts": [],
        "reuse": "One holdout. Not confirmation. Not learning-to-learn.",
        "coverage": "partial",
    },
    {
        "id": "H11",
        "title": "H10 confirmation on a new unused MCC holdout",
        "hypothesis": "The H10 recipe replicates on a new unused MCC holdout.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_MCC_MULTITASK_128_CONFIRM_RESULTS.md",
        "status": "not_established",
        "label": "mcc_multitask_128_confirm_not_established",
        "artifacts": [],
        "reuse": "Closed unused MCC confirmation. Do not retune.",
        "coverage": "partial",
    },
    {
        "id": "H12",
        "title": "H10 recipe ranks shared H=16 candidates",
        "hypothesis": "The H10 recipe ranks shared H=16 candidates better than scratch.",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_MCC_PLANNING_RANKING_RESULTS.md",
        "status": "supported",
        "label": "mcc_planning_ranking_multitask_better",
        "artifacts": [],
        "reuse": "LEVEL 1 ranking. Not 200-step control. Closed unused MCC.",
        "coverage": "partial",
    },
    {
        "id": "H13",
        "title": "H12 ranking confirmation",
        "hypothesis": "The frozen H12 ranking recipe confirms on unused MCC (0.0039, 0.002, 0.075).",
        "implementation": ["src/nexus/world"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_PROTOCOL.md",
        "results": "docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_RESULTS.md",
        "status": "supported",
        "label": "mcc_planning_ranking_confirm_multitask_better",
        "artifacts": [],
        "reuse": "Second ranking holdout. Recede is not the primary. Closed.",
        "coverage": "partial",
    },
    {
        "id": "H14",
        "title": "Fixed library versus redraw candidate reuse",
        "hypothesis": "A shared fixed candidate library helps multitask relative to redraw.",
        "implementation": ["src/nexus/world/h14_candidate_reuse.py"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md",
        "results": "docs/NEXUS_H14_CANDIDATE_REUSE_RESULTS.md",
        "status": "supported",
        "label": "h14_fixed_library_helps_multitask_relative",
        "did": 0.178,
        "artifacts": [],
        "reuse": "Closed unused MCC (0.0023, 0.0019, 0.065). Not 200-step control. Not L2L.",
        "coverage": "partial",
    },
    {
        "id": "H15",
        "title": "H14 confirmation",
        "hypothesis": "The H14 fixed-versus-redraw DiD replicates on unused MCC (0.004, 0.0021, 0.05).",
        "implementation": ["src/nexus/world/h15_candidate_reuse_confirm.py"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md",
        "results": "docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_RESULTS.md",
        "status": "supported",
        "label": "h15_fixed_library_helps_multitask_relative",
        "did": 0.230,
        "artifacts": [],
        "reuse": "Closed unused MCC confirmation. Do not retune.",
        "coverage": "partial",
    },
    {
        "id": "H16",
        "title": "Same-state library ranking",
        "hypothesis": "At later common states, L0 versus redraw changes selected-return DiD.",
        "implementation": ["src/nexus/world/h16_same_state_library.py"],
        "commit": "b646347c3f5a84bb8c4e492cca4fa50a6b9f7543",
        "protocol": "docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md",
        "results": "docs/NEXUS_H16_SAME_STATE_LIBRARY_RESULTS.md",
        "status": "not_established",
        "label": "h16_same_state_library_effect_not_established",
        "d_same": 0.023,
        "artifacts": ["artifacts/research_session_h16_same_state_library_usage.json"],
        "reuse": "Closed unused MCC (0.0015, 0.0014, 0.055). Interval includes 0. Do not retune.",
        "coverage": "partial",
    },
    {
        "id": "H17",
        "title": "Occupancy and library factorial",
        "hypothesis": "Occupancy/library factors explain remaining same-state ranking.",
        "implementation": ["configs/h17_occupancy_draft.json"],
        "commit": "incomplete",
        "protocol": None,
        "results": None,
        "status": "blocked",
        "label": "blocked_unlocked_unauthorized",
        "artifacts": [
            "docs/NEXUS_H17_SEED_DEPENDENCY_CLOSURE.md",
            "docs/NEXUS_H17_EXCLUSION_REGISTRY_AUDIT.md",
        ],
        "reuse": "Do not execute. Do not select a target. Exclusion list is a blocklist only.",
        "coverage": "reviews_only",
    },
    {
        "id": "H-lookahead-pendulum",
        "title": "Parameter-free lookahead versus frozen H=16 on Pendulum",
        "hypothesis": "One-step successor backup of frozen H=16 value beats receding H=16 on 200-step return.",
        "implementation": ["src/nexus/world/bellman_backup_control.py"],
        "commit": "incomplete",
        "protocol": None,
        "results": "docs/NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md",
        "status": "supported_development_algorithm_copy",
        "artifacts": [],
        "reuse": "Algorithm copy on family-native models. Not cross-family learning.",
        "coverage": "partial",
    },
    {
        "id": "H-lookahead-transfer",
        "title": "Lookahead transfer on new Pendulum physics",
        "hypothesis": "The frozen lookahead package transfers to a new unused Pendulum holdout.",
        "implementation": ["src/nexus/tasks/pendulum_family.py"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md",
        "results": "docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md",
        "status": "supported_one_holdout_not_l2l",
        "artifacts": [],
        "reuse": "Closed lookahead_transfer_holdout_v1 tuples. Not L2L.",
        "coverage": "partial",
    },
    {
        "id": "H-lookahead-acrobot",
        "title": "Lookahead versus H=16 on Acrobot",
        "hypothesis": "The same algorithm copy beats frozen H=16 on Acrobot development and confirmation.",
        "implementation": ["src/nexus/world/acrobot_lookahead.py"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_ACROBOT_LOOKAHEAD_PROTOCOL.md",
        "results": "docs/NEXUS_ACROBOT_LOOKAHEAD_RESULTS.md",
        "status": "development_passed_confirmation_passed_compute_matched_not_established",
        "artifacts": ["docs/NEXUS_ACROBOT_LOOKAHEAD_CONFIRM_RESULTS.md"],
        "reuse": "Closed Acrobot lookahead holdouts. Do not shop a new unnamed confirmation.",
        "coverage": "partial",
    },
    {
        "id": "E1-feasibility",
        "title": "Evolution-1 transferable proposal memory",
        "hypothesis": "Permitted memory of algorithm-improvement attempts helps discover planning configurations that transfer better than random, fixed, and equal-budget evolution.",
        "implementation": ["src/nexus/evolution1"],
        "commit": "cea4beab1316e698ddfcce5203ef0ecc8c2092c3",
        "protocol": "docs/NEXUS_EVOLUTION1_FEASIBILITY.md",
        "results": None,
        "status": "designed_not_scientifically_tested",
        "artifacts": ["docs/NEXUS_EVOLUTION1_SOURCE_CONTRACTS.md"],
        "reuse": "Feasibility and fixture contracts only. Not a scientific result.",
        "coverage": "source_verified",
    },
    {
        "id": "E1-toy-loop",
        "title": "Evolution-1 autonomous toy loop",
        "hypothesis": "Permitted training feedback changes proposal weights and later choices.",
        "implementation": ["src/nexus/evolution1/toy_loop.py"],
        "commit": "96c71ae297e6329517d4afb4d3bad50162832c21",
        "protocol": "docs/NEXUS_EVOLUTION1_AUTONOMOUS_LOOP_PROTOTYPE.md",
        "results": "docs/NEXUS_EVOLUTION1_AUTONOMOUS_LOOP_PROTOTYPE.md",
        "status": "synthetic_only",
        "artifacts": [],
        "reuse": "Functional intervention, not transferable algorithm improvement.",
        "coverage": "source_verified",
    },
    {
        "id": "E2-synthetic-screen",
        "title": "Evolution-2 persistent versus reset synthetic contract",
        "hypothesis": "Retained proposal-policy state changes discovery on later synthetic tasks versus reset.",
        "implementation": ["src/nexus/evolution2/methods.py"],
        "commit": "03c776c",
        "protocol": "docs/NEXUS_EVOLUTION2_CROSS_TASK_SCREEN.md",
        "results": None,
        "status": "synthetic_contract_only",
        "artifacts": ["docs/NEXUS_EVOLUTION2_INDEPENDENT_READINESS_AUDIT.md"],
        "reuse": "Authored hidden scores. Not LEVEL 2 evidence. Do not promote.",
        "coverage": "partial",
    },
    {
        "id": "E2-pendulum-acrobot-v1",
        "title": "Pendulum to Acrobot catalogue-proposer screen v1",
        "hypothesis": "Persisting AdaptiveProposer state after default Pendulum improves Acrobot discovery versus reset, random, evolution, retrieval, and one frozen index.",
        "implementation": ["src/nexus/evolution2/pendulum_acrobot_protocol.py"],
        "commit": "f9154f0",
        "protocol": "docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md",
        "results": None,
        "status": "design_locked_unauthorized_superseded_by_v2",
        "artifacts": [
            "configs/evolution2_pendulum_acrobot_protocol.yaml",
            "configs/evolution2_pendulum_acrobot_allocation.json",
            "docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_READINESS.md",
        ],
        "reuse": "Historical v1 lock. Do not collect. Holdout unnamed. See readiness review.",
        "coverage": "source_verified",
    },
    {
        "id": "E2-pendulum-acrobot-v2",
        "title": "Pendulum/Acrobot catalogue-proposer screen v2",
        "hypothesis": "Retained proposer state across the first training family improves discovery on the second versus random, evolution, reset, and both H=16 anchors.",
        "implementation": [
            "src/nexus/evolution2/pendulum_acrobot_protocol_v2.py",
            "src/nexus/evolution1/catalogue.py",
        ],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md",
        "results": None,
        "status": "design_only_unauthorized",
        "artifacts": ["docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_READINESS.md"],
        "reuse": "Superseding design. Do not collect. Do not name a holdout.",
        "coverage": "source_verified",
    },
    {
        "id": "E2.1-planner-adapter",
        "title": "Trusted catalogue-to-planner adapter",
        "hypothesis": "The 12-variant catalogue can be bound to existing family scoring rules without changing historical lookahead modules.",
        "implementation": ["src/nexus/evolution2/planner_adapter.py", "src/nexus/evolution2/methods.py"],
        "commit": "incomplete",
        "protocol": "docs/NEXUS_EVOLUTION2_TRUSTED_PLANNER_ADAPTER.md",
        "results": None,
        "status": "engineering_only_unauthorized",
        "artifacts": ["artifacts/evolution2_planner_compatibility.json"],
        "reuse": "Fake-model adapter. Not a scientific result. Do not collect.",
        "coverage": "source_verified",
    },
]


def scan_unindexed_docs(indexed_paths: set[str]) -> list[dict]:
    rows = []
    for path in sorted((ROOT / "docs").glob("NEXUS_*.md")):
        rel = f"docs/{path.name}"
        if rel in indexed_paths:
            continue
        name = path.name
        if not (
            name.endswith("_RESULTS.md")
            or name.endswith("_PROTOCOL.md")
            or name.endswith("_FEASIBILITY.md")
        ):
            continue
        rows.append(
            {
                "id": path.stem,
                "title": path.stem.replace("_", " "),
                "hypothesis": "incomplete",
                "implementation": [],
                "commit": "incomplete",
                "protocol": rel if name.endswith("_PROTOCOL.md") or name.endswith("_FEASIBILITY.md") else None,
                "results": rel if name.endswith("_RESULTS.md") else None,
                "status": "incomplete_unindexed_document",
                "artifacts": [],
                "reuse": "Consult the document before reuse. Do not invent a label.",
                "coverage": "incomplete",
            }
        )
    return rows


def build(head: str) -> dict:
    indexed = set()
    for row in EXPERIMENTS:
        for key in ("protocol", "results"):
            if row.get(key):
                indexed.add(row[key])
        for item in row.get("artifacts") or []:
            if item.startswith("docs/"):
                indexed.add(item)
    extra = scan_unindexed_docs(indexed)
    experiments = EXPERIMENTS + extra
    return {
        "mode": "documentation_registry",
        "scientific": False,
        "head": head,
        "ledger_s": [305.842, 3294.158],
        "h17": "blocked",
        "consult": CONSULT,
        "closed_primary_labels": [
            {"id": "H8", "label": "mcc_native_rms_not_established", "kind": "not_established"},
            {"id": "H9", "label": "mcc_residual_scale_harm_established", "kind": "harm"},
            {"id": "H10", "label": "mcc_multitask_128_beats_scratch", "kind": "supported_one_holdout"},
            {"id": "H11", "label": "mcc_multitask_128_confirm_not_established", "kind": "not_established"},
            {"id": "H12", "label": "mcc_planning_ranking_multitask_better", "kind": "supported"},
            {"id": "H13", "label": "mcc_planning_ranking_confirm_multitask_better", "kind": "supported"},
            {"id": "H14", "label": "h14_fixed_library_helps_multitask_relative", "kind": "supported", "did": 0.178},
            {"id": "H15", "label": "h15_fixed_library_helps_multitask_relative", "kind": "supported", "did": 0.230},
            {"id": "H16", "label": "h16_same_state_library_effect_not_established", "kind": "not_established", "d_same": 0.023},
        ],
        "synthetic_only": ["evolution1_toy_loop", "evolution2_cross_task_screen"],
        "do_not_reuse_as_train_labels": [
            "H8-H16 unused MCC physics",
            "H16 (0.0015, 0.0014, 0.055)",
            "29 H17 exclusions",
            "Evolution-2 FAMILY_SPEC hidden weights",
            "Acrobot lookahead development and confirmation tuples",
            "Pendulum lookahead transfer holdout (17.1, 1.5, 0.8) and siblings",
            "Default Pendulum (10, 1, 1) as a new holdout",
        ],
        "coverage": {
            "curated": len(EXPERIMENTS),
            "incomplete_unindexed_docs": len(extra),
            "total": len(experiments),
            "incomplete": sum(1 for row in experiments if row.get("coverage") in {"incomplete", "partial", "reviews_only"}),
            "source_verified": sum(1 for row in experiments if row.get("coverage") == "source_verified"),
        },
        "experiments": experiments,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# NEXUS full research registry",
        "",
        "Status: **documentation only**. Not a scientific result.",
        f"HEAD: `{payload['head']}`. Ledger **{payload['ledger_s'][0]} / {payload['ledger_s'][1]}**.",
        "H17 remains **blocked**.",
        "",
        "Missing commits, protocols, or implementations are marked **incomplete**",
        "instead of guessed. Curated rows are partial unless `coverage` is",
        "`source_verified`. Unindexed protocol/results documents are listed so",
        "they are not silently dropped.",
        "",
        "Consult this file, `docs/NEXUS_CANONICAL_CURRENT_STATE.md`, and",
        "`docs/NEXUS_CODE_REUSE_MAP.md` before implementing a new algorithm",
        "or component.",
        "",
        "## Coverage",
        "",
        f"- Curated rows: {payload['coverage']['curated']}",
        f"- Unindexed protocol/results docs: {payload['coverage']['incomplete_unindexed_docs']}",
        f"- Total rows: {payload['coverage']['total']}",
        f"- Incomplete or partial: {payload['coverage']['incomplete']}",
        f"- Source-verified: {payload['coverage']['source_verified']}",
        "",
        "## Closed primary labels that must not be retuned",
        "",
        "| ID | Label | Kind |",
        "|---|---|---|",
    ]
    for row in payload["closed_primary_labels"]:
        extra = ""
        if "did" in row:
            extra = f" DiD {row['did']}"
        if "d_same" in row:
            extra = f" D_same {row['d_same']}"
        lines.append(f"| {row['id']} | `{row['label']}`{extra} | {row['kind']} |")
    lines.extend(
        [
            "",
            "## Experiments",
            "",
            "| ID | Status | Protocol / results | Reuse | Coverage |",
            "|---|---|---|---|---|",
        ]
    )
    for row in payload["experiments"]:
        proto = row.get("protocol") or "—"
        results = row.get("results") or "—"
        lines.append(
            f"| `{row['id']}` | {row['status']} | {proto} / {results} | {row['reuse']} | {row['coverage']} |"
        )
    lines.extend(
        [
            "",
            "## Machine-readable copy",
            "",
            "`artifacts/nexus_research_registry.json`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    import subprocess

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    payload = build(head)
    json_path = ROOT / "artifacts" / "nexus_research_registry.json"
    md_path = ROOT / "docs" / "NEXUS_FULL_RESEARCH_REGISTRY.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    md_path.write_text(render_markdown(payload))
    print(f"REGISTRY {payload['coverage']['total']} rows -> {json_path}")
    print(json.dumps(payload["coverage"], indent=2))


if __name__ == "__main__":
    main()
