#!/usr/bin/env python3
"""Execute the locked diagnostic once; refuses to overwrite a run."""
import torch
from nexus.world.late_control_gap import run

if __name__ == '__main__':
    torch.set_num_threads(1)
    result=run()
    if not result['diagnostic_complete']:
        raise SystemExit(1)
