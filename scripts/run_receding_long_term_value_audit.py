#!/usr/bin/env python3
import json
from nexus.world.receding_long_term_value_audit import run

if __name__=='__main__':
    print(json.dumps(run(),indent=2,default=float))
