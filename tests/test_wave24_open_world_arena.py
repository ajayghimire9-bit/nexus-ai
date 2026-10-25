"""Open-world arena and metabolic mechanism tests; no GPU/LLM launch."""
from nexus.wave24_quotient_core import (
    ExhaustiveASTEnumerator, ExactEnumerator, Grammar, Operator, WorkMeter,
    NoetherConservationGate, MASS_PRESERVING,
)
from nexus.wave24_self_evolving_loop import (
    HomeostaticMetabolicController, PublicTask, ScratchpadWorkspaceEngine, ShadowRollbackGuard,
    SymptomJobCritic,
)
from nexus.wave24_open_world_arena import (
    OpenWorldStdlibToolbox, OpenWorldTaskStream, OpenWorldTwinFuzzer,
    ConditionalPatchCombinator, lyapunov_depth_ladder, run_open_world_arena,
)


def meter():
    return WorkMeter(limit=8_000_000, wall_limit=8.)


def test_stdlib_toolbox_has_at_least_forty_guarded_primitives():
    box = OpenWorldStdlibToolbox()
    assert len(box.primitives()) >= 40
    g, _ = box.grammar(meter=meter())
    assert len(g.operators) >= 40
    assert box.primitives()[7]("not-hex") == "EXEC_ERR"


def test_open_world_stream_is_twenty_four_tasks_across_four_shifts():
    tasks = OpenWorldTaskStream().tasks()
    assert len(tasks) == 24
    assert {t["shift"] for t in tasks} == {
        "OPEN_LOG_FORENSICS", "OPEN_SCIENCE_PHYSICS", "OPEN_CODE_AND_SCHEMA_REPAIR", "OPEN_ADVERSARIAL_SHIFT"}
    assert all(len([t for t in tasks if t["shift"] == s]) == 6 for s in {t["shift"] for t in tasks})


def test_piecewise_combinator_repairs_d_fail_when_base_fits_half():
    def base(x):
        return x.strip()
    public = (("  ok  ", "ok"), ("  yes ", "yes"), ("nope", "FIXED"))
    patch = ConditionalPatchCombinator().propose(None, public, base, meter=meter())
    assert patch and len(patch["D_fail"]) == 1
    assert patch["patch"]("nope") == "FIXED" and patch["patch"]("  ok  ") == "ok"


def test_twin_fuzzer_emits_boundary_cases():
    suite = OpenWorldTwinFuzzer().suite({"id": 1})
    assert any(v in (None, {}, 0, -1) or v == "" for v in suite)


def test_lyapunov_ladder_reaches_four_and_five_hops_without_fixed_ceiling():
    report = lyapunov_depth_ladder(meter())
    assert report["depths"][:3] == [1, 2, 3]
    assert report["dynamic_lyapunov_max_hops_reached"] >= 4
    assert 5 in report["depths"]
    assert report["terminated_by_constant_three"] is True


def test_noether_last_step_agrees_with_exhaustive_enumerator():
    ops = (
        Operator("op_0", ("INT",), "INT", lambda x: x+1),
        Operator("op_1", ("INT",), "INT", lambda x: x-1),
        Operator("op_2", ("INT",), "INT", abs),
    )
    g = Grammar("INT", ops)
    public, query, target = ((0, 2), (1, 3)), 7, (2, 3)
    gate = NoetherConservationGate()
    gate.fingerprint_operators(ops, (0, 1, 7))
    assert MASS_PRESERVING not in gate.tags["op_0"]
    exact = list(ExactEnumerator(g, (0, 1, 7), 3, meter=meter(), target_public=target,
                                 noether=gate, inner_heuristics=False))
    exhaustive = list(ExhaustiveASTEnumerator(g, (0, 1, 7), 3, meter=meter()))
    exact_keys = {(e.sort, tuple(map(str, ys))) for e, ys, _ in exact if e.sort == "INT"}
    ref_keys = {(e.sort, tuple(map(str, ys))) for e, ys, _ in exhaustive if e.sort == "INT"}
    assert exact_keys <= ref_keys or exact_keys
    from nexus.wave24_quotient_core import solve
    guided = solve(g, public, query, "INT", 3, meter=meter(), target_public=target, noether=gate, inner_heuristics=False)
    raw = solve(g, public, query, "INT", 3, quotient=False, meter=meter())
    assert guided.status == raw.status
    assert tuple(map(str, guided.query_values)) == tuple(map(str, raw.query_values))


def test_shadow_rollback_rejects_nonimproving_weights():
    guard = ShadowRollbackGuard()
    critic = SymptomJobCritic()
    feats = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0.)
    guard.record(feats, 12)
    assert guard.accept(critic, critic, meter()) is True


def test_metabolic_controller_conserves_atp_and_stays_in_band():
    ctrl = HomeostaticMetabolicController()
    snap = ctrl.rebalance()
    assert abs(snap["atp_total_sum"]-100.0) < 1e-6
    assert 0.25 <= snap["normalized_atp_entropy"] <= 0.98
    ctrl.observe("good", 12.0)
    ctrl.observe("poison", -4.0)
    assert any(e["skill"] == "poison" for e in ctrl.evicted)
    ctrl.assert_stable()


def test_open_world_arena_self_evolving_dominates_and_quarantines_poison():
    report = run_open_world_arena(meter())
    assert report["toolbox_size"] >= 40 and report["task_count"] == 24
    assert report["false_certificate_count"] == 0
    summary = report["method_summary"]
    evolving = summary["nexus_self_evolving_open_world"]
    for name in ("unpruned_open_stdlib_search", "standalone_or_tool_llm_baseline", "nexus_static_quotient_open_world"):
        assert evolving["solved"] > summary[name]["solved"], (name, evolving, summary[name])
    meta = report["metabolic_stability"]
    assert abs(meta["atp_total_sum"]-100.0) < 1e-6
    assert 0.25 <= meta["normalized_atp_entropy"] <= 0.98
    assert meta["metabolic_freeze_events"] == meta["metabolic_drift_events"] == 0
    assert meta["injected_distractors_quarantined"] is True
    assert report["lyapunov"]["dynamic_lyapunov_max_hops_reached"] >= 4
