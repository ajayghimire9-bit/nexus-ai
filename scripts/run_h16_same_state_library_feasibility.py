#!/usr/bin/env python3
"""Write the H16 feasibility artifact. No collection."""
import json
from nexus.world.h16_same_state_library_feasibility import save_feasibility

if __name__ == '__main__':
    report = save_feasibility()
    print(json.dumps({k: report[k] for k in (
        'authorized', 'locked', 'trained', 'new_environment_steps',
        'new_imagined_transitions', 'holdout_physics_selected',
        'protocol_ready_to_lock', 'budget')}, indent=2, default=float))
