"""Wave 37 (NOT LOCKED): interaction test of the frozen online learner (Wave 36 E3 program) and N1-style Bayesian online
change detection in ONE pipeline. Solver side (sandboxed child).

Change detector: BOCPD (Adams & MacKay 2007) over each task's observable surface signature (input type, output type of
the first public pair; solver-visible only), with a Dirichlet-categorical model (alpha 0.5, open vocabulary), constant
hazard 1/50, run lengths truncated at 200. A change is DECLARED when P(run length <= 2) > 0.5 and >= 5 tasks have passed
since the last declaration.
Modes (all on the same interpreter, all costs metered by the OS counter in the evaluator):
  base    : no learning, no detection (SEED_OFF)
  learner : the frozen learner only
  n1      : SEED_OFF + the detector (nothing to reset: pure detection overhead)
  both    : the frozen learner + detector; on a declared change the learner forgets every task before the estimated change
            point (MAP run length) and its prior is refit from the remaining tasks at its next refit (None until then)
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus import wave33_prior as P
from nexus import wave34_learner as L

ROOT = Path(__file__).resolve().parents[2]
H, RMAX, ALPHA = 1 / 50, 200, 0.5
ST = {}


def _frozen():
    return json.loads((ROOT / "artifacts/wave36_e3_shortlisted_program.json").read_text())["program"]


def reset(mode):
    L.reset()
    ST.clear()
    prog = L.SEED_OFF if mode in ("base", "n1") else _frozen()
    ST.update(mode=mode, prog=prog, runs=[(1.0, {})], vocab=set(), since_decl=99, declared=[], t=0)


def _sig(view):
    x, y = view["public"][0]
    return P.vtype(x) + "->" + P.vtype(y)


def _bocpd(sig):
    ST["vocab"].add(sig)
    K = len(ST["vocab"]) + 1
    grown, cp = [], 0.0
    for w, cnt in ST["runs"]:
        n = sum(cnt.values())
        pred = (cnt.get(sig, 0) + ALPHA) / (n + ALPHA * K)
        c2 = dict(cnt); c2[sig] = c2.get(sig, 0) + 1
        grown.append((w * pred * (1 - H), c2))
        cp += w * pred * H
    new = [(cp, {sig: 1})] + grown
    z = sum(w for w, _ in new)
    ST["runs"] = [(w / z, c) for w, c in new[:RMAX]]
    p_short = sum(w for w, _ in ST["runs"][:3])
    mapr = max(range(len(ST["runs"])), key=lambda i: ST["runs"][i][0])
    return p_short, mapr


def solve(chan, view, seed):
    return L.solve(chan, view, ST["prog"], seed)


def update(candidate, view, certified, rec):
    ST["t"] += 1
    out = L.update(ST["prog"], candidate, view, certified, rec)
    if ST["mode"] in ("n1", "both"):
        p_short, mapr = _bocpd(_sig(view))
        ST["since_decl"] += 1
        if p_short > 0.5 and ST["since_decl"] >= 5:
            ST["since_decl"] = 0
            ST["declared"].append(ST["t"])
            if ST["mode"] == "both":
                keep = max(1, mapr + 1)                       # tasks in the current run (approx.: certified tasks kept)
                for k in ("progs", "views", "pfeats"):
                    L.ST[k] = L.ST[k][-keep:]
                L.ST["prior"] = None
                L.ST["since_fit"] = 99                           # refit at the next certified task
            out["declared_change"] = True
    out["n_declared"] = len(ST["declared"])
    return out
