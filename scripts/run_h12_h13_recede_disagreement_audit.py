#!/usr/bin/env python3
import json
from nexus.world import h12_h13_recede_disagreement_audit as m

if __name__ == '__main__':
    result = m.run()
    out = {k: result.get(k) for k in (
        'new_environment_interactions', 'new_imagined_transitions', 'trained',
        'authorized', 'closed_loop_is_primary', 'strongest_supported_claim',
        'claims_learning_to_learn', 'is_agi')}
    out['h12_primary'] = result['h12']['primary']
    out['h13_primary'] = result['h13']['primary']
    out['h12_recede'] = result['h12']['recede']
    out['h13_recede'] = result['h13']['recede']
    print(json.dumps(out, indent=2, default=float))
