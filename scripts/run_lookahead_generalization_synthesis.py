#!/usr/bin/env python3
"""Write the source-only lookahead generalization audit. No environment collection."""
from nexus.world.lookahead_generalization_synthesis import audit

if __name__ == '__main__':
    payload = audit()
    print(payload['label'], 'steps', payload['new_environment_steps'], 'authorized', payload['authorized'])
