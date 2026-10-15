#!/usr/bin/env python3
import torch
from nexus.world.planning_value import execute
if __name__ == '__main__':
    torch.set_num_threads(1)
    if not execute()['complete']: raise SystemExit(1)
