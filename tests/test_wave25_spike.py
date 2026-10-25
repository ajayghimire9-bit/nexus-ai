"""Wave 25 spike: soundness of tier-1 abstract rules, the learned F/S diagnostic rule, probe plumbing.
Dev generator seeds only; no evaluation seeds."""
import random
from itertools import product

from nexus.wave24_domains import vkey
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, meter
from nexus.wave25_factored import (MAPS, RULES, Mech, Order, Pred, binding_grammar, certify, collect_pair_data,
                                   design_probe, fs_composition_ambiguous, ints_world, make_abstract, make_tasks,
                                   mine_rules, phi_holds, records_world, run, s1_compare, scope_check,
                                   solve_active, _edit_space)


def _reachability_cases(world, seed, n_inputs=12):
    rng = random.Random(seed)
    xs = [world["sample"](rng) for _ in range(n_inputs)]
    mechs = [t.fn for t in binding_grammar(xs[:4], maps=world["maps"])]
    return xs, mechs


def test_abstract_rules_never_prune_a_reachable_target():
    for world in (ints_world(1), records_world(1)):
        xs, mechs = _reachability_cases(world, 7)
        maps = list(MAPS.values()) if world["maps"] else ()
        prune = make_abstract(RULES, maps=maps)
        rng = random.Random(3)
        checked = 0
        for _ in range(400):
            x = rng.choice(xs)
            prefix = [rng.choice(mechs)]
            suffix = [rng.choice(mechs) for _ in range(rng.randint(1, 2))]
            try:
                v = run(prefix, x)
                y = run(suffix, v)
            except Exception:
                continue
            assert not prune([v], [y], len(suffix), meter(10**6)), (prefix, suffix)
            checked += 1
        assert checked > 200


def test_abstract_pruning_preserves_every_verdict_and_cuts_work():
    for world in (ints_world(4), records_world(4)):
        rows = s1_compare(make_tasks(world, 5, 15, active=False, max_depth=3), world, RULES)
        assert rows and all(r["same"] for r in rows)
        assert sum(r["evals_ab"] for r in rows) < sum(r["evals_fd"] for r in rows)


def test_fs_law_by_hand():
    p, s = Mech("F", (Pred(".", "ge", 0),)), Mech("S", (2, Order("#")))
    x = [-1, 5, 4]
    assert s(p(x)) == [5, 4] and p(s(x)) == [5]


def test_rule_learner_finds_fs_law_and_nothing_for_commuting_pairs():
    data, _ = collect_pair_data(ints_world(1), 1, 30)
    rules, _ = mine_rules(data)
    fs = rules.get(("F", "S"))
    assert fs is not None and set(fs.phi) == {("Ks-Kt", ">=", 1), ("Kt-Ks", ">=", 1)}
    checked, viol = scope_check(fs)
    assert checked > 1000 and viol == 0 and fs.tier == "scope-verified"
    for commuting in (("F", "F"), ("F", "Sort")):
        if commuting in rules:
            assert rules[commuting] is None


def test_rule_probe_resolves_record_fs_task_with_unknown_field_names():
    data, _ = collect_pair_data(ints_world(1), 1, 30)
    rules = {k: r for k, r in mine_rules(data)[0].items() if r is not None}
    tgt = records_world(2)
    tasks = [t for t in make_tasks(tgt, 302, 40, active=True) if fs_composition_ambiguous(t)]
    assert tasks
    t = tasks[0]
    res = certify(t, tgt)
    assert res.status == AMBIGUOUS
    x, label = design_probe("rule", res, list(t.public), t.query, tgt, rules, random.Random(0), meter(10**9))
    assert x is not None and label.startswith("rule")
    outs = {vkey(run([tl.fn for tl in prog], x)) for prog in
            [p for rest, (p, v) in res.searcher.graph.classes[tuple(res.searcher.targets)].items()]}
    assert len(outs) >= 2                         # the concretised probe splits the hypothesis set
    row = solve_active(t, tgt, "rule", rules)
    assert row["status"] == UNIQUE and row["solved"] and not row["false_certificate"]


def test_edit_space_is_breadth_first_over_edit_count():
    bases = [[1, 2, 3], [4, 5, 6, 7]]
    out = _edit_space(bases, (".",), {".": [0, 9]}, cap=14)
    assert any(len(x) == 4 for x in out)          # 1-edits of the second base come before any 2-edit
