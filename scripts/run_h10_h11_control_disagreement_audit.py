#!/usr/bin/env python3
import json
from nexus.world import h10_h11_control_disagreement_audit as m

if __name__ == '__main__':
    result = m.run()
    out = {k: result.get(k) for k in (
        'new_environment_interactions', 'trained', 'h11_negative_seeds',
        'h11_negative_still_better_mae', 'strongest_supported_claim',
        'not_a_harm_claim', 'is_agi')}
    out['h10_primary'] = result['h10']['primary']
    out['h11_primary'] = result['h11']['primary']
    print(json.dumps(out, indent=2, default=float))
