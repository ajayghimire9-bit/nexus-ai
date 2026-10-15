#!/usr/bin/env python3
"""One locked rp2 policy-switch diagnostic; no automatic retry."""
import torch
from nexus.world.policy_switch import execute
if __name__=='__main__':
    torch.set_num_threads(1)
    if not execute()['complete']: raise SystemExit(1)
