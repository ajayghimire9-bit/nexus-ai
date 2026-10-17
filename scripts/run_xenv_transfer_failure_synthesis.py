#!/usr/bin/env python3
import json
from pathlib import Path
from nexus.world.xenv_transfer_failure_synthesis import analyze
from nexus.world.terminal_value_execution import save

if __name__ == '__main__':
    report = analyze()
    save(Path('artifacts/xenv_transfer_failure_synthesis.json'), report)
    out = {k: report[k] for k in (
        'complete', 'authorized', 'new_environment_steps', 'new_imagined_transitions',
        'bottleneck', 'next_direction', 'claims_learning_to_learn', 'is_agi', 'note')}
    print(json.dumps(out, indent=2, default=float))
