"""Print source-only H17 readiness; no execution or registration options."""
import json
from pathlib import Path

from nexus.h17_protocol_readiness import review


if __name__ == '__main__':
    print(json.dumps(review(Path(__file__).resolve().parents[1]), indent=2, allow_nan=False))
