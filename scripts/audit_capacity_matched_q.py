#!/usr/bin/env python3
import json
from nexus.world.capacity_matched_q import audit
if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
