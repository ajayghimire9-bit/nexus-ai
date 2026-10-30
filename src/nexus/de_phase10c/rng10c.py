"""Phase 10C numeric random seeding (NOT LOCKED; owner Phase 10C rule 1).

Phase 10 / 10B seeded ranker training-pair sampling, the ranker's train / validation split and the M* edit choice from
strings that contained the learner / clone NAME (lineage10: f"{self.name}|{pid}", f"split|{self.name}|{cycles}",
f"M|{learner.name}"), so renaming a clone changed its data - the Phase 10B 9-vs-8 M* comparison was confounded by it.
Every Phase 10C random stream is derived ONLY from an explicit tuple of integers (repetition_id, step_id, task_id): no arm,
clone or learner name can reach a seed."""
from __future__ import annotations

import hashlib
import random


def seed_of(*ints):
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in ints):
        raise TypeError(f"Phase 10C seeds are numeric tuples only: {ints!r}")
    return int.from_bytes(hashlib.sha256(",".join(str(x) for x in ints).encode()).digest()[:8], "big")


def rng(*ints):
    return random.Random(seed_of(*ints))
