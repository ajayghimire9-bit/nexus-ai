#!/usr/bin/env python3
import json
from nexus.world import h14_candidate_reuse as m
from nexus.world.terminal_value_execution import save
from pathlib import Path

if __name__ == '__main__':
    report = dict(complete=True, authorized=False, locked=False, trained=False,
        new_environment_steps=0, new_imagined_transitions=0,
        proposed_budget=m.budget(),
        primary_metric='fixed_minus_redraw_relative_multitask_advantage',
        labels=('h14_fixed_library_helps_multitask_relative',
                'h14_redraw_helps_multitask_relative',
                'h14_resampling_effect_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False,
        note='Feasibility only. No allocation. H12/H13 stay closed.')
    save(Path('artifacts/h14_candidate_reuse_feasibility.json'), report)
    print(json.dumps(report, indent=2, default=float))
