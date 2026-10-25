"""Wave 25 S1-Auto + S3: contract learner soundness, answer-directed objective, H enumeration (dev only)."""
import random
from collections import Counter

from nexus.wave24_domains import vkey
from nexus.wave24_v4_core import AMBIGUOUS, meter
from nexus.wave25_contracts import (certify_with, item_map, learn_contracts, make_contract_pruner, usable_props)
from nexus.wave25_factored import (binding_grammar, ints_world, make_tasks, records_world, run, task_grammar)
from nexus.wave25_s3 import S3_ARMS, cond_info, enumerate_H, outputs, solve_s3


def test_contract_learner_proves_sound_contracts_and_rejects_distractors():
    lib = learn_contracts()
    status = Counter((c.prop, c.status) for c in lib.contracts)
    assert lib.role_classes == {"Agg": "to_scalar", "F": "submultiset", "Map": "itemwise", "S": "submultiset",
                                "Sort": "permutation"}
    rec = usable_props(lib, {"F", "S", "Sort", "Agg"})
    ints = usable_props(lib, {"F", "S", "Sort", "Map", "Agg"})
    assert "parity" not in rec["numeric"] and "first_sign" not in rec["numeric"]
    assert set(rec["numeric"]) == {"length", "distinct_count", "max_atom"} and rec["provenance"]
    assert set(ints["numeric"]) == {"length", "distinct_count"}
    assert ints["provenance"] and ints["provenance_image"] and not rec["provenance_image"]   # derived image_subset
    assert status[("first_sign", "proved")] == 0 and status[("parity", "refuted")] > 0


def test_learned_contracts_never_prune_a_reachable_target():
    lib = learn_contracts()
    for world in (ints_world(1), records_world(1)):
        rng = random.Random(9)
        xs = [world["sample"](rng) for _ in range(12)]
        mechs = [t.fn for t in binding_grammar(xs[:4], maps=world["maps"])]
        props = usable_props(lib, {m.role for m in mechs})
        prune = make_contract_pruner(props, maps=[item_map(m) for m in mechs if item_map(m) is not None])
        checked = 0
        for _ in range(400):
            x = rng.choice(xs)
            pre, suf = [rng.choice(mechs)], [rng.choice(mechs) for _ in range(rng.randint(1, 2))]
            try:
                v = run(pre, x)
                y = run(suf, v)
            except Exception:
                continue
            assert not prune([v], [y], len(suf), meter(10**6))
            checked += 1
        assert checked > 200


def test_learned_contracts_preserve_verdicts():
    lib = learn_contracts()
    for world in (ints_world(2), records_world(2)):
        props = usable_props(lib, {"F", "S", "Sort", "Agg"} | ({"Map"} if world["maps"] else set()))
        for t in make_tasks(world, 11, 10, active=False, max_depth=3):
            a, b = certify_with(t, world, None), certify_with(t, world, props)
            assert a.status == b.status
            assert {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}


def test_hypothesis_set_matches_certificate_witness_set():
    for world in (ints_world(1), records_world(1)):
        for t in make_tasks(world, 12, 5, active=True):
            res = certify_with(t, world, None)
            m = meter(10**9)
            H = enumerate_H(list(t.public), [x.fn for x in task_grammar(t, world)], res.size, m)
            assert res.status == AMBIGUOUS and len(H) >= 2
            assert set(outputs(H, t.query, m)) == {vkey(h[1]) for h in res.hypotheses}


def test_answer_objective_ignores_answer_irrelevant_splits():
    yq = ["a", "a", "b", "b"]
    assert cond_info(yq, [1, 2, 1, 2]) == 0.0        # splits bindings within each answer cluster only
    assert abs(cond_info(yq, [1, 1, 2, 2]) - 1.0) < 1e-12


def test_s3_arms_run_and_never_falsely_certify():
    world = records_world(1)
    t = make_tasks(world, 13, 1, active=True)[0]
    for arm in S3_ARMS:
        r = solve_s3(t, world, arm, None, seed=1)
        assert not r["false_certificate"] and r["probes"] <= 3
