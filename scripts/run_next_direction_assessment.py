#!/usr/bin/env python3
import json
from nexus.world.next_direction_assessment import run

if __name__=='__main__':
    print(json.dumps(run(),indent=2,default=float))
