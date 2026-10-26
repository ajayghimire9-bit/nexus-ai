import random

from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, meter
from nexus.wave25_factored import run
from nexus.wave26_phase4 import EXTENDED, Library, make_fault_task, worlds
from nexus.wave29_core import certify_pm, certify_shell, index28, verify_candidates
from nexus.wave24_domains import vkey


def _shortcut_task():
    """Wave 28 seed 4019 (now Wave 29 dev data): ΔB task whose 2-step teacher is beaten by a 1-step shortcut."""
    wname, w = [x for x in worlds(4019) if x[0] == "records"][0]
    rng = random.Random(f"w26-p4-mixed:4019:{wname}")
    for _ in range(3):
        t = make_fault_task(w, rng, "dB")
    return t


def test_shell_exposes_minimal_size_shortcut():
    t = _shortcut_task()
    pub = list(t["public"])
    inputs = [x for x, _ in pub] + [t["query"]]
    tools = Library().tools(inputs, grammar=EXTENDED, with_schemas=True)
    keep, mac = index28(tools, pub, 2, meter(10**9), {})
    plain = certify_pm(pub, t["query"], (keep, 2, mac), meter(10**10))
    shell = certify_shell(pub, t["query"], (keep, 2, mac), meter(10**10))
    assert plain.status == UNIQUE and vkey(plain.answer) != vkey(t["answer"])          # the Wave 28 false certificate
    assert shell.status == AMBIGUOUS
    assert vkey(t["answer"]) in {vkey(h[1]) for h in shell.hypotheses}                # the teacher's answer is in the shell


def test_verify_candidates_are_new_and_built_from_observed_items():
    t = _shortcut_task()
    inputs = [x for x, _ in t["public"]] + [t["query"]]
    cands = verify_candidates(inputs, random.Random(0))
    seen = {vkey(x) for x in inputs}
    items = {vkey(it) for x in inputs for it in x}
    assert cands and all(vkey(c) not in seen for c in cands)
    assert all(vkey(it) in items for c in cands for it in c)
