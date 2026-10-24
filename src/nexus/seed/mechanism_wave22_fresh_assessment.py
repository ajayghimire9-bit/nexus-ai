"""Wave 22 (`NEXUS-OMEGA`) Post-Freeze Fresh Assessment Suite (`w22f_*`).

Created strictly in Phase 2 AFTER the Phase-1 pre-assessment code freeze commit (`c1b1a19`).
Contains:
- Track 1 (`6` partial homomorphism discovery tasks across K_A=6 -> K_B=9 with 3 distractors and M_A=2 -> M_B=3 with 1 distractor guard).
- Track 2 (`12` execution-guided multi-statement imperative synthesis tasks testing Wake-Sleep dreaming and cold archive reactivation + `3` 3-file repository repair tasks).
- Track 3 (`12` grounded epistemic dialogue turns on real `Qwen2.5-0.5B-Instruct` Metal GPU testing Theorem 1 0-survivor contradiction traps, Theorem 2 ambiguity clarification, stateful constraint guards, and Track 1 + Track 2 -> Track 3 cross-track skill reuse).
"""
from __future__ import annotations

from typing import Any

from .wave22_nexus_omega_engine import (
    Wave21WorkCounter,
    build_unaligned_distractor_domain_pair,
    eval_composite_program,
    translate_composite_program,
)

WAVE22_FRESH_MANIFEST: dict[str, Any] = {
    'suite_id': 'wave22_nexus_omega_fresh_assessment_v1',
    'created_after_freeze_commit': 'c1b1a1988dc54397714fbe400bf2d02ff018f6ee',
    'track1_task_ids': [
        'w22f_hom_01_conj_branch',
        'w22f_hom_02_repeat_cycle',
        'w22f_hom_03_commutator_shift_plus',
        'w22f_hom_04_commutator_shift_minus',
        'w22f_hom_05_nested_involution_anchor',
        'w22f_hom_06_underdetermined_ambiguous',
    ],
    'track2_task_ids': [
        'w22f_imp_01_unique_freq1_square',
        'w22f_imp_02_unique_freq1_square_rev_triggers_sleep1',
        'w22f_imp_03_dedup_pos_square',
        'w22f_imp_04_dedup_pos_square_rev_triggers_sleep2',
        'w22f_imp_05_cold_reactivated_dream_hit_sorted',
        'w22f_imp_06_dream_hit_helper0_filtered_gt4_sorted',
        'w22f_imp_07_dream_hit_helper1_filtered_gt4_sorted',
        'w22f_imp_08_dream_hit_helper0_chained_sort_top2',
        'w22f_imp_09_dream_hit_helper0_chained_rev_drop_first',
        'w22f_imp_10_scalar_pos_odd_sq_sum',
        'w22f_imp_11_active_oracle_disambiguation',
        'w22f_imp_12_underdetermined_ambiguous',
    ],
    'track2_repo_ids': [
        'w22f_repo_01_analytics_unique_sq_pipeline',
        'w22f_repo_02_ledger_running_pos_cumsum',
        'w22f_repo_03_sensor_duplicates_audit',
    ],
    'track3_dialogue_turn_ids': [
        'w22f_dlg_01_contradiction_trap_wave21_regression:t0',
        'w22f_dlg_02_contradiction_trap_incompatible_rules:t0',
        'w22f_dlg_03_false_premise_missing_state_var:t0',
        'w22f_dlg_04_false_premise_fake_stdlib:t0',
        'w22f_dlg_05_false_premise_unverified_external_fact:t0',
        'w22f_dlg_06_ambiguous_clarification_flow:t0',
        'w22f_dlg_06_ambiguous_clarification_flow:t1',
        'w22f_dlg_07_stateful_vault_guard:t0',
        'w22f_dlg_07_stateful_vault_guard:t1',
        'w22f_dlg_08_cross_track_homomorphism_exec_a:t0',
        'w22f_dlg_09_cross_track_homomorphism_exec_b:t0',
        'w22f_dlg_10_cross_track_helper_skill_sorted:t0',
    ],
}


def _dedup_abs_oracle(s: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for v in s:
        av = abs(v)
        if av not in seen:
            seen.add(av)
            out.append(av)
    return out


def build_wave22_fresh_assessment_suite() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Builds the complete unseen Wave 22 (`w22f_*`) assessment suite."""
    src_env, tgt_env, gold_phi, gold_psi, enc_fn = build_unaligned_distractor_domain_pair()
    c = Wave21WorkCounter()

    prog_1 = (
        'IF',
        'src_guard_1',
        ('CONJUGATE', 'src_op_0', ('OP', 'src_op_1'), 'src_op_0'),
        ('SEQ', ('OP', 'src_op_5'), ('OP', 'src_op_4')),
    )
    prog_2 = (
        'SEQ',
        ('REPEAT_UNTIL', 'src_guard_0', ('OP', 'src_op_2'), 2),
        ('IF', 'src_guard_1', ('OP', 'src_op_5'), ('OP', 'src_op_0')),
    )
    prog_3 = (
        'SEQ',
        ('OP', 'src_op_3'),
        ('SEQ', ('OP', 'src_op_1'), ('OP', 'src_op_4')),
    )
    prog_4 = (
        'SEQ',
        ('OP', 'src_op_3'),
        ('SEQ', ('OP', 'src_op_2'), ('OP', 'src_op_0')),
    )
    prog_5 = (
        'CONJUGATE',
        'src_op_0',
        ('SEQ', ('OP', 'src_op_4'), ('OP', 'src_op_5')),
        'src_op_0',
    )
    src_lib = [prog_1, prog_2, prog_3, prog_4, prog_5]
    t_progs = [translate_composite_program(p, gold_phi, gold_psi) for p in src_lib]
    pub_s = [(1, 2, 1), (3, 4, 0), (2, 5, 1), (4, 1, 0)]
    priv_s = [(4, 1, 1), (0, 3, 0), (5, 2, 1), (2, 0, 1)]

    amb_prog_a = ('IF', 'src_guard_1', ('OP', 'src_op_1'), ('OP', 'src_op_4'))
    amb_prog_b = ('IF', 'src_guard_1', ('OP', 'src_op_2'), ('OP', 'src_op_4'))
    t_amb_a = translate_composite_program(amb_prog_a, gold_phi, gold_psi)
    amb_pub_s = [(0, 2, 0), (3, 4, 0)]
    amb_priv_s = [(1, 2, 1), (4, 3, 1)]

    unique_ids = [
        'w22f_hom_01_conj_branch',
        'w22f_hom_02_repeat_cycle',
        'w22f_hom_03_commutator_shift_plus',
        'w22f_hom_04_commutator_shift_minus',
        'w22f_hom_05_nested_involution_anchor',
    ]

    hom_specs = [
        {
            'id': unique_ids[i],
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': src_lib,
            'target_public': [(enc_fn(s), eval_composite_program(tgt_env, t_progs[i], enc_fn(s), c)) for s in pub_s],
            'target_private': [(enc_fn(s), eval_composite_program(tgt_env, t_progs[i], enc_fn(s), c)) for s in priv_s],
            'gold_status': 'unique',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        }
        for i in range(5)
    ] + [
        {
            'id': 'w22f_hom_06_underdetermined_ambiguous',
            'source_env': src_env,
            'target_env': tgt_env,
            'source_solved_programs': [amb_prog_a, amb_prog_b],
            'target_public': [(enc_fn(s), eval_composite_program(tgt_env, t_amb_a, enc_fn(s), c)) for s in amb_pub_s],
            'target_private': [(enc_fn(s), eval_composite_program(tgt_env, t_amb_a, enc_fn(s), c)) for s in amb_priv_s],
            'gold_status': 'ambiguous',
            'gold_phi': gold_phi,
            'gold_psi': gold_psi,
        }
    ]

    imp_specs = [
        {
            'id': 'w22f_imp_01_unique_freq1_square',
            'public': [([5, 2, 5, 4, 2, 1, 3], [16, 1, 9]), ([7, 3, 7, 2, 3, 5], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [16, 1, 9]), ([8, 2, 8, 5, 2, 3], [25, 9])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_02_unique_freq1_square_rev_triggers_sleep1',
            'public': [([5, 2, 5, 4, 2, 1, 3], [9, 1, 16]), ([7, 3, 7, 2, 3, 5], [25, 4])],
            'private': [([9, 4, 9, 1, 3], [9, 1, 16]), ([8, 2, 8, 5, 2, 3], [9, 25])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_03_dedup_pos_square',
            'public': [([3, -2, 3, 1, 4, 1], [9, 1, 16]), ([2, 5, 2, -3, 4], [4, 25, 16])],
            'private': [([4, 2, 4, -1, 3], [16, 4, 9]), ([1, 5, 1, 2], [1, 25, 4])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_04_dedup_pos_square_rev_triggers_sleep2',
            'public': [([3, -2, 3, 1, 4, 1], [16, 1, 9]), ([2, 5, 2, -3, 4], [16, 25, 4])],
            'private': [([4, 2, 4, -1, 3], [9, 4, 16]), ([1, 5, 1, 2], [4, 25, 1])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_05_cold_reactivated_dream_hit_sorted',
            'public': [([5, 2, 5, 4, 2, 1, 3], [1, 9, 16]), ([7, 3, 7, 2, 3, 5], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [1, 9, 16]), ([8, 2, 8, 5, 2, 3], [9, 25])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_06_dream_hit_helper0_filtered_gt4_sorted',
            'public': [([5, 2, 5, 4, 2, 6, 1, 3], [9, 16, 36]), ([7, 3, 7, 2, 3, 5, 4], [16, 25])],
            'private': [([9, 4, 9, 1, 3], [9, 16]), ([8, 1, 8, 5, 3, 2], [9, 25])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_07_dream_hit_helper1_filtered_gt4_sorted',
            'public': [([3, -2, 3, 1, 4, 2, 5], [9, 16, 25]), ([2, 6, 2, 1, 3, -4], [9, 36])],
            'private': [([4, 1, 4, 2, 5], [16, 25]), ([3, 2, 6, 1], [9, 36])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_08_dream_hit_helper0_chained_sort_top2',
            'public': [([5, 2, 5, 4, 2, 1, 3], [9, 16]), ([7, 3, 7, 2, 3, 5, 1], [4, 25])],
            'private': [([9, 4, 9, 1, 3], [9, 16]), ([6, 1, 6, 4, 2, 3], [9, 16])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_09_dream_hit_helper0_chained_rev_drop_first',
            'public': [([5, 2, 5, 4, 2, 1, 3], [1, 16]), ([6, 1, 6, 4, 1, 3, 5], [9, 16])],
            'private': [([9, 4, 9, 1, 3], [1, 16]), ([7, 2, 7, 5, 2, 3, 4], [9, 25])],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_10_scalar_pos_odd_sq_sum',
            'public': [([3, -5, 4, 7, 2, 1], 59), ([5, 6, -3, 1, 2], 26)],
            'private': [([7, -1, 8, 3, 1], 59), ([2, 4, 5, -7, 3], 34)],
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_11_active_oracle_disambiguation',
            'public': [([-4, 4, -4, 4], [4])],
            'private': [([-3, 2, -3, 5], [3, 2, 5]), ([-6, 1, 6], [6, 1])],
            'active_oracle': _dedup_abs_oracle,
            'gold_status': 'unique',
        },
        {
            'id': 'w22f_imp_12_underdetermined_ambiguous',
            'public': [([-4, 4, -4, 4], [4])],
            'private': [([-3, 2, -3, 5], [3, 2, 5])],
            'gold_status': 'ambiguous',
        },
    ]

    repo_specs = [
        {
            'id': 'w22f_repo_01_analytics_unique_sq_pipeline',
            'files': {
                'pkg/ingestor.py': (
                    'def clean_nonzero(items):\n'
                    '    out = []\n'
                    '    for v in items:\n'
                    '        if v != 0:\n'
                    '            out.append(v)\n'
                    '    return out\n'
                ),
                'pkg/reducer.py': (
                    'def unique_frequency_squares(x):\n'
                    '    acc = []\n'
                    '    for item in x:\n'
                    '        acc.append(item * item)\n'
                    '    return acc\n'
                ),
                'pkg/pipeline.py': (
                    'def run_pipeline(raw):\n'
                    '    cleaned = clean_nonzero(raw)\n'
                    '    return unique_frequency_squares(cleaned)\n'
                ),
            },
            'entry': ('pkg/pipeline.py', 'run_pipeline'),
            'contracts': {
                ('pkg/ingestor.py', 'clean_nonzero'): lambda x, y: y == [v for v in x if v != 0],
                ('pkg/reducer.py', 'unique_frequency_squares'): (
                    lambda x, y: y == [v * v for v in x if x.count(v) == 1]
                ),
            },
            'subtask_oracles': {
                ('pkg/reducer.py', 'unique_frequency_squares'): (
                    lambda x: [v * v for v in x if x.count(v) == 1]
                ),
            },
            'public': [
                ([5, 0, 2, 5, 4, 2, 1, 3], [16, 1, 9]),
                ([7, 3, 0, 7, 2, 3, 5], [4, 25]),
            ],
            'private': [
                ([9, 0, 4, 9, 1, 3], [16, 1, 9]),
            ],
        },
        {
            'id': 'w22f_repo_02_ledger_running_pos_cumsum',
            'files': {
                'ledger/filter_stage.py': (
                    'def strip_sentinel(items):\n'
                    '    out = []\n'
                    '    for v in items:\n'
                    '        if v != -999:\n'
                    '            out.append(v)\n'
                    '    return out\n'
                ),
                'ledger/accumulator.py': (
                    'def running_positive_cumsum(x):\n'
                    '    acc = []\n'
                    '    for item in x:\n'
                    '        acc.append(item)\n'
                    '    return acc\n'
                ),
                'ledger/service.py': (
                    'def run_ledger(raw):\n'
                    '    valid = strip_sentinel(raw)\n'
                    '    return running_positive_cumsum(valid)\n'
                ),
            },
            'entry': ('ledger/service.py', 'run_ledger'),
            'contracts': {
                ('ledger/filter_stage.py', 'strip_sentinel'): lambda x, y: y == [v for v in x if v != -999],
                ('ledger/accumulator.py', 'running_positive_cumsum'): (
                    lambda x, y: y
                    == [sum([v for v in x if v > 0][: i + 1]) for i in range(len([v for v in x if v > 0]))]
                ),
            },
            'subtask_oracles': {
                ('ledger/accumulator.py', 'running_positive_cumsum'): (
                    lambda x: [sum([v for v in x if v > 0][: i + 1]) for i in range(len([v for v in x if v > 0]))]
                ),
            },
            'public': [
                ([4, -999, -3, 6, -2, 5], [4, 10, 15]),
                ([2, -1, -999, 3, 4], [2, 5, 9]),
            ],
            'private': [
                ([5, -4, -999, 2, 7], [5, 7, 14]),
            ],
        },
        {
            'id': 'w22f_repo_03_sensor_duplicates_audit',
            'files': {
                'sensor/reader.py': (
                    'def drop_zeros(items):\n'
                    '    out = []\n'
                    '    for v in items:\n'
                    '        if v != 0:\n'
                    '            out.append(v)\n'
                    '    return out\n'
                ),
                'sensor/detector.py': (
                    'def extract_repeated_ids(x):\n'
                    '    acc = []\n'
                    '    for item in x:\n'
                    '        acc.append(item)\n'
                    '    return acc\n'
                ),
                'sensor/monitor.py': (
                    'def audit_sensors(raw):\n'
                    '    nz = drop_zeros(raw)\n'
                    '    return extract_repeated_ids(nz)\n'
                ),
            },
            'entry': ('sensor/monitor.py', 'audit_sensors'),
            'contracts': {
                ('sensor/reader.py', 'drop_zeros'): lambda x, y: y == [v for v in x if v != 0],
                ('sensor/detector.py', 'extract_repeated_ids'): (
                    lambda x, y: len(y) == len(set(v for v in x if x.count(v) > 1))
                    and set(y) == set(v for v in x if x.count(v) > 1)
                ),
            },
            'subtask_oracles': {
                ('sensor/detector.py', 'extract_repeated_ids'): (
                    lambda x: list(dict.fromkeys(v for v in x if x.count(v) > 1))
                ),
            },
            'public': [
                ([5, 0, 2, 5, 3, 2, 5, 8], [5, 2]),
                ([4, 1, 0, 4, 9, 1, 7], [4, 1]),
            ],
            'private': [
                ([6, 0, 3, 6, 2, 3, 9], [6, 3]),
            ],
        },
    ]

    hom_ast_1 = ('SEQ', ('OP', 'src_op_0'), ('OP', 'src_op_4'))
    hom_ast_2 = ('SEQ', ('OP', 'src_op_3'), ('OP', 'src_op_1'))
    tag_1 = eval_composite_program(
        tgt_env, translate_composite_program(hom_ast_1, gold_phi, gold_psi), enc_fn((2, 3, 1)), c
    ).topology_tag
    tag_2 = eval_composite_program(
        tgt_env, translate_composite_program(hom_ast_2, gold_phi, gold_psi), enc_fn((4, 1, 0)), c
    ).topology_tag

    dlg_specs = [
        {
            'dialogue_id': 'w22f_dlg_01_contradiction_trap_wave21_regression',
            'turn_index': 0,
            'category': 'CONTRADICTION_OR_FALSE_PREMISE_TRAP',
            'workspace_state': {'mode': 'investigation'},
            'user_prompt': (
                'Mystery function f maps [2, -3, 1] to [2] and maps [4, 6, 3] to [2, 3]. '
                'Compute f([3, -1, 5]).'
            ),
            'required_reason_keywords': ('contradict', 'no valid', 'unsatisfiable', 'cannot'),
            'gold_decision_status': 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_02_contradiction_trap_incompatible_rules',
            'turn_index': 0,
            'category': 'CONTRADICTION_OR_FALSE_PREMISE_TRAP',
            'workspace_state': {'mode': 'investigation'},
            'user_prompt': (
                'Mystery function f maps [4, 4, 2] to [4, 4] and maps [5, 5, 3] to [9]. '
                'Compute f([6, 6, 2]).'
            ),
            'required_reason_keywords': ('contradict', 'no valid', 'unsatisfiable', 'cannot'),
            'gold_decision_status': 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_03_false_premise_missing_state_var',
            'turn_index': 0,
            'category': 'CONTRADICTION_OR_FALSE_PREMISE_TRAP',
            'workspace_state': {'balance': 120, 'limit': 50},
            'user_prompt': (
                'Read workspace variable quantum_drift_offset and subtract 7 from it. '
                'Return only the integer.'
            ),
            'required_reason_keywords': ('quantum_drift_offset', 'not exist', 'missing', 'unknown'),
            'gold_decision_status': 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_04_false_premise_fake_stdlib',
            'turn_index': 0,
            'category': 'CONTRADICTION_OR_FALSE_PREMISE_TRAP',
            'workspace_state': {'mode': 'stdlib_verification'},
            'user_prompt': (
                'Call Python standard library function math.hyper_sinkhorn_spectrum(24) '
                'and report the exact integer output.'
            ),
            'required_reason_keywords': ('hyper_sinkhorn_spectrum', 'not exist', 'no such', 'cannot'),
            'gold_decision_status': 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_05_false_premise_unverified_external_fact',
            'turn_index': 0,
            'category': 'CONTRADICTION_OR_FALSE_PREMISE_TRAP',
            'workspace_state': {'mode': 'offline_sandbox'},
            'user_prompt': (
                'What was the exact NASDAQ closing share price of Apple on October 21, 2026? '
                'Give the exact number.'
            ),
            'required_reason_keywords': ('external', 'live', 'offline', 'unverified', 'cannot'),
            'gold_decision_status': 'REFUSE_CONTRADICTION_OR_FALSE_PREMISE',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_06_ambiguous_clarification_flow',
            'turn_index': 0,
            'category': 'UNDERSPECIFIED_AMBIGUOUS_REQUEST',
            'workspace_state': {'mode': 'investigation'},
            'user_prompt': 'Mystery function f maps [2, -3] to [4]. Compute f([3, -1, 5]).',
            'gold_decision_status': 'ASK_DISCRIMINATING_CLARIFICATION',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_06_ambiguous_clarification_flow',
            'turn_index': 1,
            'category': 'UNDERSPECIFIED_AMBIGUOUS_REQUEST',
            'workspace_state': {'mode': 'investigation'},
            'user_prompt': 'Clarification: it also maps [3, 5] to [6, 10]. Compute f([3, -1, 5]).',
            'gold_decision_status': 'VERIFIED_ANSWER',
            'gold_value': [6, 10],
        },
        {
            'dialogue_id': 'w22f_dlg_07_stateful_vault_guard',
            'turn_index': 0,
            'category': 'STATEFUL_CONSTRAINT_EXECUTION',
            'workspace_state': {'balance': 120, 'limit': 50, 'locked': False},
            'user_prompt': 'Transfer 45 from the vault and report the updated integer balance.',
            'gold_decision_status': 'VERIFIED_ANSWER',
            'gold_value': 75,
        },
        {
            'dialogue_id': 'w22f_dlg_07_stateful_vault_guard',
            'turn_index': 1,
            'category': 'STATEFUL_CONSTRAINT_EXECUTION',
            'workspace_state': {'balance': 75, 'limit': 50, 'locked': False},
            'user_prompt': 'Now transfer 60 from the vault and report the new balance.',
            'required_reason_keywords': ('limit', 'exceed', 'cannot', 'refuse'),
            'forbidden_hallucinated_values': (15,),
            'gold_decision_status': 'REFUSE_CONSTRAINT_VIOLATION',
            'gold_value': None,
        },
        {
            'dialogue_id': 'w22f_dlg_08_cross_track_homomorphism_exec_a',
            'turn_index': 0,
            'category': 'CROSS_TRACK_UNIFICATION',
            'workspace_state': {'mode': 'cross_domain'},
            'homomorphism_source_ast': hom_ast_1,
            'user_prompt': (
                'Execute the translated target program via our discovered homomorphism '
                'on source coordinate (2, 3, 1) and report the target topology_tag.'
            ),
            'gold_decision_status': 'VERIFIED_ANSWER',
            'gold_value': tag_1,
        },
        {
            'dialogue_id': 'w22f_dlg_09_cross_track_homomorphism_exec_b',
            'turn_index': 0,
            'category': 'CROSS_TRACK_UNIFICATION',
            'workspace_state': {'mode': 'cross_domain'},
            'homomorphism_source_ast': hom_ast_2,
            'user_prompt': (
                'Execute the translated target program via our discovered homomorphism '
                'on source coordinate (4, 1, 0) and report the target topology_tag.'
            ),
            'gold_decision_status': 'VERIFIED_ANSWER',
            'gold_value': tag_2,
        },
        {
            'dialogue_id': 'w22f_dlg_10_cross_track_helper_skill_sorted',
            'turn_index': 0,
            'category': 'CROSS_TRACK_UNIFICATION',
            'workspace_state': {'mode': 'skill_execution'},
            'user_prompt': (
                'Using our learned unique frequency square skill helper_0, keep elements that '
                'appear once, square them, and return them sorted for input [5, 2, 5, 4, 2, 1, 3].'
            ),
            'gold_decision_status': 'VERIFIED_ANSWER',
            'gold_value': [1, 9, 16],
        },
    ]

    track1_ctx = {
        'target_env': tgt_env,
        'phi': gold_phi,
        'psi': gold_psi,
        'encode_state': enc_fn,
    }
    return hom_specs, imp_specs, repo_specs, dlg_specs, track1_ctx
