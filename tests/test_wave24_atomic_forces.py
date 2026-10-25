"""v12 AtomicFieldProjector, force roles, UniversalForceFunctor and force-pruned 2-hop."""
from nexus.wave24_auto_laws import (AtomicFieldProjector, AtomicForceClassifier, splitmix64,
    F_SELECT, F_TRANSLATE, F_TRANSMUTE, F_CONDENSE, F_BRANCH)
from nexus.wave24_quotient_core import Grammar, Operator, WorkMeter, ParametricSkillMacro, apply, typed_hole
from nexus.wave24_open_world_arena import (ForcePrunedResidualTwoHop, PromotedChainLibrary, TaskEvalCache,
    run_open_world_arena)
from nexus.wave24_self_evolving_loop import UniversalForceFunctor, force_table, zero_shot_force_transfer

STRS = ("  Hello ", "Abc", "0xff", "a b", "xyz ")


def meter():
    return WorkMeter(limit=1_000_000, wall_limit=5.)


def test_splitmix64_is_deterministic_64_bit():
    assert splitmix64(0) == splitmix64(0) and 0 <= splitmix64(12345) < 2**64
    assert splitmix64(1) != splitmix64(2)


def test_projector_conservation_laws_are_exact_on_permutations_and_selections():
    P = AtomicFieldProjector()
    a, b = P.project([3, 1, 2]), P.project([1, 2, 3])
    assert a.mass == b.mass == 3
    assert a.quantum_multiset_hash == b.quantum_multiset_hash and a.locus_mask == b.locus_mask
    assert a.binding_hash != b.binding_hash  # arrangement differs
    sub = P.project([1, 3])
    assert (sub.quantum_bloom_64 & ~a.quantum_bloom_64) == 0 and sub.mass < a.mass
    assert P.project({"a": 1}).mass == 1 and P.project(255).mass == 8 and P.project(frozenset({1, 2})).mass == 2
    assert P.project({"a": 1, "b": 2}).locus_mask == P.project({"b": 2, "a": 1}).locus_mask


def test_force_classifier_assigns_the_five_universal_forces():
    c = AtomicForceClassifier()
    assert c.classify(str.strip, STRS).force == F_SELECT
    assert c.classify(str.lower, STRS).force == F_TRANSMUTE
    assert c.classify(lambda s: s[::-1], STRS).force == F_TRANSLATE
    assert c.classify(len, STRS).force == F_CONDENSE
    assert c.classify(lambda s: s[::-1] if len(s) > 3 else s.upper(), STRS).force == F_BRANCH


def _str_grammar():
    ops = (Operator("op_0", ("STR",), "STR", str.strip), Operator("op_1", ("STR",), "STR", str.lower),
           Operator("op_2", ("STR",), "STR", lambda s: s[::-1]), Operator("op_3", ("STR",), "INT", len))
    return Grammar("STR", ops)


def test_universal_force_functor_lifts_and_binds_without_target_tasks():
    g = _str_grammar()
    forces = force_table(g, {"STR": STRS})
    skill = ParametricSkillMacro(apply(g.ops["op_1"], apply(g.ops["op_0"], typed_hole("STR"))), ("STR",))
    (functor,) = UniversalForceFunctor.lift(skill, forces, source_domain="SRC")
    assert functor.key() == (F_TRANSMUTE, F_SELECT)
    bound, lineage = zero_shot_force_transfer((functor,), g, forces, STRS, meter=meter())
    assert bound and all(r["target_training_tasks"] == 0 and r["force_functor"] == [F_TRANSMUTE, F_SELECT] for r in lineage)


def test_force_pruned_two_hop_certifies_strip_then_lower_and_prunes_soundly():
    g = _str_grammar()
    two = ForcePrunedResidualTwoHop(g, {"STR": STRS}, meter=meter())
    task = dict(public=(("  Hello ", "hello"), ("  WORLD ", "world")), query="  Nexus ", output_sort="STR")
    out = two.search(g, task, meter=meter())
    assert out["status"] == two.STATUS_UNIQUE and out["query_value"] == "nexus"
    assert out["direction"] == "DECREASE" and out["stepping_stones"] <= 4
    # Every pruned op_2 is genuinely unable to reach Y_pub from its stepping stone.
    assert two.learn(out["witness"]) == (F_TRANSMUTE, F_SELECT)


def test_promoted_chain_library_reuses_a_solved_chain_cheaply():
    g = _str_grammar()
    lib = PromotedChainLibrary()
    lib.promote(("op_0", "op_1"))
    m = meter()
    out = lib.search(g, dict(public=(("  MixED ", "mixed"), ("  OK ", "ok")), query="  Shift ", output_sort="STR"),
                     meter=m, cache=TaskEvalCache())
    assert out["status"] == lib.STATUS_UNIQUE and out["query_value"] == "shift" and m.total <= 6


def test_arena_v12_default_dominates_static_and_counts_every_fallback():
    arena = run_open_world_arena(meter())
    summ = arena["method_summary"]
    evo, static = summ["nexus_self_evolving_open_world"], summ["nexus_static_quotient_open_world"]
    assert arena["force_two_hop"] is True and arena["false_certificate_count"] == 0
    assert evo["solved"] >= 13 > static["solved"] and evo["work_per_solved"] < static["work_per_solved"]
    assert arena["matched_subset"]["evolving_work"] < arena["matched_subset"]["static_work"]
    assert arena["learned_force_functors"] and arena["promoted_chains"]
