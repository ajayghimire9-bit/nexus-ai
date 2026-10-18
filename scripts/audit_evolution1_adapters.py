"""Read-only source snapshot verification. Never import reviewed implementations.

This binds a manual adapter review to exact source bytes and AST definitions;
it does not prove semantic equivalence, dependency closure or isolation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'artifacts/evolution1_adapter_review.json'
BASE = '3ac0c5f49bc67e5202f6836a9b688ed5cf301095'
SOURCES = {
    'src/nexus/world/planning.py': (
        'InferenceCounter.step', 'RandomShootingMPC._score_batch',
        'RandomShootingMPC.act', 'mpc_for_model'),
    'src/nexus/world/bellman_backup_control.py': (
        '_score_open_loop', 'lookahead_first_action',
        'Meter.instrument_env', 'Meter.instrument_model'),
    'src/nexus/world/acrobot_lookahead.py': ('make_planner', 'lookahead_first_action'),
    'src/nexus/world/mountaincar_lookahead.py': ('make_planner', 'lookahead_first_action'),
    'src/nexus/world/mountaincar_continuous_lookahead.py': ('make_planner', 'lookahead_first_action'),
    'src/nexus/world/prediction_control_gap.py': ('candidate_sequences',),
    'src/nexus/world/rewards.py': (
        'pendulum_step_reward', 'acrobot_step_reward', 'mountaincar_step_reward'),
    'src/nexus/tasks/wrappers.py': (
        'DiscreteTorqueWrapper.action', 'AcrobotDenseRewardWrapper.step',
        'MountainCarDenseRewardWrapper.step'),
    'src/nexus/tasks/spec.py': ('make_task_env',),
    'src/nexus/world/dynamics.py': ('WorldModel.step',),
    'src/nexus/meta/schema.py': ('ExperimentAction',),
    'src/nexus/world/confirm_guard.py': ('assert_confirmation_allowed',),
    'src/nexus/evolution1/catalogue.py': ('plan_bound',),
    'src/nexus/evolution1/fixtures.py': ('FixtureBroker.submit',),
    'src/nexus/evolution1/promotion.py': ('FixturePromotionHarness.promote_for_test',),
}


class ReviewMismatch(ValueError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def definition(tree: ast.AST, qualified_name: str) -> ast.AST:
    """Require each explicitly named definition exactly once at its scope."""
    node = tree
    for name in qualified_name.split('.'):
        matches = [child for child in getattr(node, 'body', ())
                   if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   and child.name == name]
        if len(matches) != 1:
            raise ReviewMismatch(f'missing or duplicate definition: {qualified_name}')
        node = matches[0]
    return node


def source_snapshot(root: Path) -> dict:
    """Only read the fixed, reviewer-owned path/symbol inventory."""
    rows = []
    for relative, names in sorted(SOURCES.items()):
        path = root / relative
        try:
            raw = path.read_bytes()
            tree = ast.parse(raw, filename=relative)
        except (OSError, SyntaxError, ValueError) as exc:
            raise ReviewMismatch(f'unreadable reviewed source: {relative}') from exc
        symbols = {}
        for name in names:
            node = definition(tree, name)
            # Full-file hash also binds comments, locations and module globals.
            normalized = ast.dump(node, include_attributes=False)
            symbols[name] = hashlib.sha256(normalized.encode()).hexdigest()
        rows.append({'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(),
                     'symbols': symbols})
    return {
        'schema': 'evolution1_adapter_source_review_v1',
        'starting_revision': BASE,
        'status': 'blocked_runtime_gates',
        'execution_authorized': False,
        'source_inventory_complete_for_this_review': True,
        'transitive_dependency_closure_proven': False,
        'semantic_equivalence_proven': False,
        'process_isolation_proven': False,
        'scientific_execution_seconds': 0,
        'real_interactions': 0,
        'imagined_transitions': 0,
        'sources': rows,
    }


def verify_manifest(root: Path, payload: object) -> dict:
    expected = source_snapshot(root)
    try:
        matches = canonical(payload) == canonical(expected)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ReviewMismatch('invalid source-review manifest') from exc
    if not matches:
        raise ReviewMismatch('source review is missing, stale, altered or incomplete')
    return expected


def _unique(pairs: list) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReviewMismatch('duplicate manifest key')
        out[key] = value
    return out


def _nonfinite(value: str) -> None:
    raise ReviewMismatch(f'nonfinite manifest constant: {value}')


def load_manifest(path: Path) -> object:
    try:
        return json.loads(path.read_text(), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (OSError, ValueError, RecursionError) as exc:
        raise ReviewMismatch('unreadable source-review manifest') from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True,
                        help='verify source evidence only; no execution capability')
    parser.parse_args()
    try:
        result = verify_manifest(ROOT, load_manifest(MANIFEST))
    except ReviewMismatch as exc:
        parser.exit(1, f'REVIEW_MISMATCH: {exc}\n')
    print(f"SOURCE_REVIEW_MATCH: {len(result['sources'])} files; runtime remains blocked")


if __name__ == '__main__':
    main()
