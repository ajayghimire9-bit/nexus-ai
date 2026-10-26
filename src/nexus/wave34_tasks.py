"""Wave 34 task streams (EVALUATOR SIDE ONLY). Training streams: the increment-3 family (2 rep, 3 rep, mixed 2->3->2) plus
F2 multi-mechanism streams (F2 was the Wave 33 test family; inspected, so now development data). TEST family F3: 2-op
cores and string-output mechanisms that appear in no earlier family (checked against S_CORES / TARGET / STRING_TARGET /
S3 / TARGET3 / F2)."""
from __future__ import annotations

import random

from nexus import wave31_tasks as T
from nexus import wave33_tasks as T33

C = dict(T33.C, dec={"op": "dec_chars"})
F3 = {"records": (("pb", "diff", "rot"), ("pa", "rmax", "diff")),
      "strings": (("chars", "cnt", "keys", "dec"), ("chars", "rot", "rot", "dec")),
      "grids": (("objs", "sizes", "rmax"), ("cells", "diff", "rot")),
      "graphs": (("reach", "diff", "psum"), ("reach", "psum", "diff"))}


def family_stream(fam, seed, rep, tag):
    rng = random.Random(f"w34-{tag}:{seed}:{rep}")
    out = []
    for d, progs in fam.items():
        for names in progs:
            for _ in range(rep):
                t = T._task(d, [dict(C[n]) for n in names], rng, 4, core=list(names), category=tag)
                if t:
                    out.append(t)
    random.Random(f"w34-{tag}-order:{seed}:{rep}").shuffle(out)
    return out


def _seg(seed, sub, doms, rep):
    ts = [t for d in doms for t in T.target_stream3(f"{seed}{sub}", d, rep)]
    random.Random(f"w34-order:{seed}:{sub}").shuffle(ts)
    return ts


def train_streams(seed):
    rng = random.Random(f"w34-train:{seed}")
    doms = rng.sample(("records", "strings", "grids", "graphs"), 2)
    return {"2rep": _seg(seed, "a", doms, 2), "3rep": _seg(seed, "b", doms, 3),
            "mixed232": _seg(seed, "c", doms, 2) + _seg(seed, "d", doms, 3) + _seg(seed, "e", doms, 2),
            "F2x3": T33.f2_stream(f"w34:{seed}", 3)}


def mixed_test_streams(seed):
    """The Wave 32 mixed design: Source (records + strings + graphs) and Target (grids), segments 2 -> 3 -> 2 reps."""
    out = {}
    for name, doms in (("Source", ("records", "strings", "graphs")), ("Target", ("grids",))):
        out[name] = _seg(seed, "a", doms, 2) + _seg(seed, "b", doms, 3) + _seg(seed, "c", doms, 2)
    return out


# F4 (unseen): COUNTER-VALUED outputs (every earlier family outputs sequences, strings or grids)
F4 = {"records": (("pa", "cnt", "topc"), ("pb", "cnt")),
      "strings": (("chars", "cnt", "topc"), ("chars", "rot", "cnt")),
      "grids": (("cells", "cnt"), ("objs", "sizes", "cnt")),
      "graphs": (("deg", "topc"), ("reach", "diff", "cnt"))}
