import hashlib
import random
from pathlib import Path

from nexus import checker_kernel as K
from nexus.wave24_v4_core import meter
from nexus.wave25_factored import ints_world, run
from nexus.wave26_phase1 import records_world_f
from nexus.wave30_arms import a1_tools, make_task, prove, spec_of

ROOT = Path(__file__).resolve().parents[1]


def test_kernel_file_is_pinned():
    pinned = (ROOT / "src" / "nexus" / "checker_kernel.sha256").read_text().split()[0]
    assert hashlib.sha256((ROOT / "src" / "nexus" / "checker_kernel.py").read_bytes()).hexdigest() == pinned


def test_kernel_interpreter_agrees_with_prover_on_every_mechanism():
    rng = random.Random(5)
    for w in (ints_world(11), records_world_f(11, 3)):
        xs = [w["sample"](rng) for _ in range(12)]
        for t in a1_tools(xs[:5]):
            spec = spec_of(t.fn)
            for x in xs:
                try:
                    a = ("ok", K.key(t.fn(x)))
                except Exception:
                    a = ("raise",)
                try:
                    b = ("ok", K.key(K.apply(spec, x)))
                except Exception:
                    b = ("raise",)
                assert a == b, (spec, x)


def _evidence():
    rng = random.Random(2)
    w = records_world_f(13, 3)
    t = None
    while t is None:
        t = make_task(rng, w, a1_only=True)
    inputs = [x for x, _ in t["public"]] + [t["query"]]
    tools = a1_tools(inputs)
    ev, _, _ = prove(t["public"], t["query"], tools, "exhaustive", meter(10**12),
                     lambda x, c=t["teacher"]: run(c, x), random.Random(0))
    return ev


def test_kernel_rejects_tampering():
    ev = _evidence()
    assert ev is not None
    base = K.check(ev)
    assert base["label"] in ("exhaustive_UNIQUE", "AMBIGUOUS")
    bad = dict(ev, claimed_answer=["tampered"])
    assert K.check(bad)["label"] == "ABSTAIN"
    if ev["lemmas"]:
        lm = dict(ev["lemmas"][0], public_index=(ev["lemmas"][0]["public_index"] + 1) % len(ev["public"]))
        r = K.check(dict(ev, lemmas=[lm] + ev["lemmas"][1:]))
        assert r["label"] in ("ABSTAIN", base["label"])   # a mis-cited lemma is either rejected or still true
    assert K.check(dict(ev, candidate=[{"op": "nope"}]))["label"] == "ABSTAIN"
    prop = K.check(dict(ev, scope=dict(ev["scope"], kind="proposal")))
    assert prop["label"] in ("proposal_relative_UNIQUE", "AMBIGUOUS")


def test_kernel_lemmas_do_not_change_the_label():
    ev = _evidence()
    with_l = K.check(ev)
    without = K.check(dict(ev, lemmas=[]))
    assert (with_l["label"], with_l.get("k"), with_l["fitting"]) == (without["label"], without.get("k"), without["fitting"])
    assert with_l["chains_checked"] <= without["chains_checked"]
