"""Comprehensive verification suite for the 15-component NEXUS Seed master architecture.

All tests are deterministic unit and integration checks; they do not run metered
scientific experiments or claim achieved AGI / learning-to-learn.
"""
import uuid
import pytest
from nexus.seed.core import Session
from nexus.seed.lab import SeedWorkspace
from nexus.seed.shared_brain import SharedBrain
from nexus.seed.master import (
    ActiveInvestigationReasoner,
    AnalogicalReasoner,
    BeliefState,
    COGNITIVE_OPERATIONS,
    CausalReasoner,
    CodeTaskParser,
    CognitiveMetaController,
    CompactSubwordTokenizer,
    Concept,
    ConstraintReasoner,
    DebuggingController,
    DebuggingSkill,
    ExecutionSandbox,
    ExperienceEvent,
    GroundedObservation,
    GroundedResponseGenerator,
    HierarchicalPlanner,
    HybridWorldModel,
    Hypothesis,
    KnowledgeAcquisitionEngine,
    LearningAcceptanceGate,
    MasterSeedArchitecture,
    MathematicalReasoner,
    MemoryArchitecture,
    NeuralGroundingLayer,
    ProgramExecutionReasoner,
    ProgramSynthesizer,
    ReasoningResult,
    ReasoningRouter,
    RelationalReasoner,
    RepositoryModel,
    ResponsePlan,
    SharedBeliefWorkspace,
    Skill,
    TaskSpec,
    ThreeTimescalesLearner,
    TieredComputeController,
    build_torch_grounding_encoder,
)


def test_component1_neural_grounding_layer_and_modalities():
    grounder = NeuralGroundingLayer(enable_torch_model=True)
    assert grounder.torch_model is not None
    param_count = grounder.torch_model.parameter_count()
    # Recommended ~1-5 million parameters, 128-D embeddings, 2-layer BiGRU
    assert 1_000_000 <= param_count <= 5_000_000
    assert grounder.torch_model.embed_dim == 128

    obs = grounder.ground_text("Could you arrange these from smallest to largest?")
    assert isinstance(obs, GroundedObservation)
    assert obs.provenance["intent"] == "execute_skill"
    assert obs.provenance["skill"] == "sorting"
    assert obs.provenance["arguments"] == "supplied_list"
    assert obs.provenance["constraint"] == "ascending"
    assert obs.uncertainty["confidence"] == 0.94

    emb = grounder.embed_text("Could you arrange these from smallest to largest?")
    assert len(emb) == 128

    # Vision, audio, sensor, and code encoders produce the same GroundedObservation type
    vis_obs = grounder.ground_vision([
        dict(id="o1", color="red", shape="circle", size="small", x=1, y=1),
        dict(id="o2", color="blue", shape="square", size="large", x=1, y=3),
    ])
    assert "red" in vis_obs.concepts and "o1" in vis_obs.entities
    assert any(r["relation"] == "north" and r["subject"] == "o1" for r in vis_obs.relations)

    aud_obs = grounder.ground_audio("Could you arrange these from smallest to largest?", acoustic_confidence=0.9)
    assert aud_obs.provenance["modality"] == "audio_speech"
    assert aud_obs.uncertainty["confidence"] == round(0.94 * 0.9, 4)

    sen_obs = grounder.ground_sensor(dict(temperature=22.5, battery=0.85))
    assert sen_obs.provenance["modality"] == "sensor_environment"
    assert 22.5 in sen_obs.quantities

    code_obs = grounder.ground_code("import math\ndef compute_norm(x):\n    return x\n")
    assert "compute_norm" in code_obs.entities
    assert code_obs.provenance["modality"] == "code"


def test_component2_and_3_belief_workspace_and_typed_representations():
    session = Session()
    brain = SharedBrain(session)
    arch = MasterSeedArchitecture(session, brain)

    obs = arch.grounding.ground_text("Could you arrange these from smallest to largest? [4, 2, 1]")
    belief = arch.workspace.build_belief_state(observations=[obs])
    assert isinstance(belief, BeliefState)
    roundtrip = BeliefState.from_dict(belief.to_dict())
    assert roundtrip.to_dict() == belief.to_dict()
    assert len(belief.available_skills) >= 2
    assert belief.resource_budget["journal_events_limit"] == 2048

    # Validate all unified typed structures
    c = Concept(name="scarlet", aliases=["bright_red"], definition="bright red", confidence=0.9, evidence=["ev1"])
    assert Concept.from_dict(c.to_dict()) == c
    ts = TaskSpec(goal="sort list", inputs=[3, 1, 2], expected_outputs=[1, 2, 3])
    assert TaskSpec.from_dict(ts.to_dict()) == ts
    h = Hypothesis(claim="sorting is O(n log n)", confidence=0.95)
    assert Hypothesis.from_dict(h.to_dict()) == h
    sk = Skill(signature=dict(name="sort_skill", schema="list"), typed_program=dict(schema="list", op="sort"))
    assert Skill.from_dict(sk.to_dict()) == sk
    ev = ExperienceEvent(observation="obs", decision="execute", action="sort", result=[1, 2], reward=1.0)
    assert ExperienceEvent.from_dict(ev.to_dict()) == ev
    rp = ResponsePlan(dialogue_act="answer", factual_claims=["sorted"], supporting_evidence=["ev1"])
    assert ResponsePlan.from_dict(rp.to_dict()) == rp
    rr = ReasoningResult(conclusion="A is north of C", confidence=0.98, cost=3)
    assert ReasoningResult.from_dict(rr.to_dict()) == rr
    ds = DebuggingSkill(symptom="SyntaxError", likely_causes=["missing colon"])
    assert DebuggingSkill.from_dict(ds.to_dict()) == ds


def test_component4_six_tier_memory_architecture():
    session = Session()
    brain = SharedBrain(session)
    learner = ThreeTimescalesLearner(session, brain)
    learner.learn_immediate_concept("scarlet", "bright red", verified=True)

    mem = MemoryArchitecture(session, brain)
    all_views = mem.inspect_all()
    assert set(all_views) == {
        "working_memory",
        "episodic_memory_count",
        "semantic_memory",
        "procedural_memory",
        "model_memory",
        "replay_retention_memory",
    }
    assert "scarlet" in all_views["semantic_memory"]
    assert "sorting" in all_views["procedural_memory"]
    assert "reverse" in all_views["procedural_memory"]
    assert all_views["replay_retention_memory"]["admission_policy"] == "explicit_evidence_and_verification_required"


def test_component5_hybrid_world_model_and_disagreement_triggers():
    hw = HybridWorldModel(disagreement_threshold=0.35)
    state = dict(objects=[dict(id="o1", x=1, y=2, color="red", shape="circle", size="small")])

    # Low disagreement transition
    low = hw.step_prediction(state, dict(kind="grid_move", object="o1", direction="right", steps=2, neural_residual=[0.05, -0.02]))
    assert low["combined_coordinates"] == [3.05, 1.98]
    assert not low["high_disagreement"]
    assert low["recommended_operation"] == "execute"

    # High disagreement transition triggers clarifying question / experiment / retrieval / revision / cautious action
    high = hw.step_prediction(state, dict(kind="grid_move", object="o1", direction="right", steps=2, neural_predicted_x=0.0, neural_predicted_y=5.0))
    assert high["high_disagreement"]
    assert "clarifying_question" in high["triggered_responses"]
    assert "active_experiment" in high["triggered_responses"]
    assert high["recommended_operation"] == "abstain"


def test_component6_and_7_reasoning_portfolio_and_router():
    router = ReasoningRouter(hybrid_world=HybridWorldModel())

    # 1. Relational reasoner (transitive older & spatial north)
    rel_older = router.route("relational", dict(
        relations=[
            dict(relation="older", subject="Alice", object="Bob"),
            dict(relation="older", subject="Bob", object="Charlie"),
        ],
        query_subject="Alice",
        query_object="Charlie",
    ))
    assert rel_older.conclusion == "Alice is older than Charlie"
    assert any("transitive(older)" in step for step in rel_older.proof_or_trace)

    rel_north = router.route("relational", dict(
        relations=[
            dict(relation="north", subject="A", object="B"),
            dict(relation="north", subject="B", object="C"),
        ],
        query_subject="A",
        query_object="C",
    ))
    assert rel_north.conclusion == "A is north of C"

    # 2. Constraint reasoner (CSP)
    csp_res = router.route("constraint", dict(
        variables=dict(T1=[1, 2, 3], T2=[1, 2, 3], T3=[1, 2, 3]),
        constraints=[
            dict(kind="all_different", vars=["T1", "T2", "T3"]),
            dict(kind="less_than", a="T1", b="T2"),
            dict(kind="less_than", a="T2", b="T3"),
        ],
    ))
    assert csp_res.conclusion == dict(T1=1, T2=2, T3=3)

    # 3. Mathematical reasoner (equation solving + substitution check + dimensional check)
    math_res = router.route("math", dict(expression="2*x + 5 = 17", variable="x"))
    assert math_res.conclusion == dict(x=6, verified=True)
    dim_bad = router.route("math", dict(expression="10 + 5", units=dict(lhs="meters", rhs="seconds")))
    assert dim_bad.conclusion == "dimensional_mismatch"

    # 4. Program execution reasoner
    prog_res = router.route("program_execution", dict(
        program=dict(schema="list", op="chain", steps=("sort", "unique")),
        inputs=[3, 1, 3, 2],
        postcondition_check=lambda inp, out: out == sorted(set(inp)),
    ))
    assert prog_res.conclusion["result"] == [1, 2, 3]
    assert prog_res.conclusion["verification"]["passed"]

    # 5. Causal reasoner (observational vs interventional)
    causal_obs = router.route("causal", dict(variable_x="Rain", variable_y="WetGrass", candidate_confounder="Sprinkler"))
    assert causal_obs.conclusion["classification"] == "Rain correlates with WetGrass"
    assert len(causal_obs.unresolved_questions) == 1

    causal_int = router.route("causal", dict(
        variable_x="Switch",
        variable_y="Light",
        interventional_data=[dict(do_X=1, Y=1.0), dict(do_X=1, Y=0.95), dict(do_X=0, Y=0.0)],
    ))
    assert causal_int.conclusion["classification"] == "Switch causes Light"

    # 6. Analogical reasoner (list reversal <-> reverse movement sequence)
    ana_res = router.route("analogical", dict(
        source_domain=dict(domain="list_domain", operation="reverse_order"),
        target_domain=dict(
            domain="movement_domain",
            sequence=[dict(direction="right", steps=2), dict(direction="up", steps=1)],
            invert_directions=True,
        ),
    ))
    assert ana_res.conclusion["analogy"] == "list_reversal <-> reverse_movement_sequence"
    assert ana_res.conclusion["mapped_sequence"] == [
        dict(direction="down", steps=1),
        dict(direction="left", steps=2),
    ]

    # 7. Hierarchical planner
    plan_res = router.route("planning", dict(
        goal=dict(object="o1", x=3, y=2),
        world_state=[dict(id="o1", x=0, y=0, color="red", shape="circle", size="small")],
    ))
    assert len(plan_res.conclusion["subgoals"]) == 2
    assert len(plan_res.conclusion["verified_action"]) == 2

    # 8. Active investigation reasoner (VOI)
    voi_res = router.route("active_investigation", dict(
        hypotheses=["h1", "h2", "h3", "h4"],
        candidate_probes=[
            dict(id="balanced_probe", cost=1.0, predictions=dict(h1=True, h2=True, h3=False, h4=False)),
            dict(id="skewed_probe", cost=1.0, predictions=dict(h1=True, h2=False, h3=False, h4=False)),
        ],
    ))
    assert voi_res.conclusion["selected_probe"] == "balanced_probe"
    assert voi_res.conclusion["voi"] > 0.9


def test_component8_coding_and_debugging_architecture():
    parser = CodeTaskParser()
    repo = RepositoryModel()
    synth = ProgramSynthesizer()
    sandbox = ExecutionSandbox()
    debugger = DebuggingController(sandbox=sandbox, synthesizer=synth)

    idx = repo.index_files({
        "transform.py": "import math\ndef helper(v):\n    return v\ndef run_all(x):\n    return helper(x)\n",
        "test_transform.py": "def test_run_all():\n    assert True\n",
    })
    assert "run_all" in idx["symbols"]["transform.py"]
    assert "test_transform.py::test_run_all" in idx["tests"]
    assert any(edge["callee"] == "helper" for edge in idx["call_graph"])

    # Synthesis + Sandbox verification
    spec = parser.parse("Write code to sort and remove duplicates")
    s_out = synth.synthesize(spec, mode="compose_programs")
    v_out = sandbox.verify(
        s_out["python_code"],
        typed_program=s_out["typed_program"],
        unit_tests=[dict(input=[3, 1, 3, 2], output=[1, 2, 3])],
    )
    assert v_out["passed"]

    # Security check rejects unsafe code
    unsafe = sandbox.verify("import os\ndef bad(x):\n    os.system('echo hi')\n    return x\n")
    assert not unsafe["passed"]
    assert unsafe["failure_stage"] == "security_resource_limits"

    # Debugging loop 1: repair_syntax
    broken_syntax = "def transform(x)\n    x = sorted(x)"
    dbg_syn = debugger.debug_and_repair(
        broken_syntax,
        unit_tests=[dict(input=[3, 1, 2], output=[1, 2, 3])],
    )
    assert dbg_syn["status"] == "repaired"
    assert dbg_syn["action_taken"] == "repair_syntax"
    assert dbg_syn["debugging_skill"]["repair_pattern"]["action"] == "repair_syntax"

    # Debugging loop 2: change_implementation
    wrong_impl = "def transform(x: list) -> list:\n    x = sorted(x)\n    return x\n"
    dbg_impl = debugger.debug_and_repair(
        wrong_impl,
        unit_tests=[
            dict(input=[1, 2, 3], output=[3, 2, 1]),
            dict(input=[4, 0, 9], output=[9, 0, 4]),
        ],
    )
    assert dbg_impl["status"] == "repaired"
    assert dbg_impl["action_taken"] == "change_implementation"

    # Debugging loop 3: revise_specification on contradictory tests
    dbg_spec = debugger.debug_and_repair(
        wrong_impl,
        unit_tests=[
            dict(input=[1, 2], output=[1, 2]),
            dict(input=[1, 2], output=[2, 1]),
        ],
    )
    assert dbg_spec["action_taken"] == "revise_specification"


def test_component9_cognitive_meta_controller():
    session = Session()
    arch = MasterSeedArchitecture(session)
    obs = arch.grounding.ground_text("If A is north of B and B is north of C, where is A relative to C?")
    belief = arch.workspace.build_belief_state(observations=[obs])
    scored = arch.meta_controller.score_operations(belief)
    assert set(scored["scores"]) == set(COGNITIVE_OPERATIONS)
    assert scored["selected_operation"] == "reason"

    # High disagreement / unsafe signal selects abstain
    abstain_scored = arch.meta_controller.score_operations(belief, context_signals=dict(world_disagreement=1.5))
    assert abstain_scored["selected_operation"] == "abstain"


def test_component10_and_11_three_timescales_and_acceptance_gate():
    session = Session()
    brain = SharedBrain(session)
    learner = ThreeTimescalesLearner(session, brain)

    # 1. Immediate learning ("Scarlet" means bright red)
    imm = learner.learn_immediate_concept("scarlet", "bright red")
    assert imm["timescale"] == "immediate"
    assert not imm["requires_neural_training"]
    sem = learner.memory.semantic_memory_view()
    assert "scarlet" in sem
    assert any(r["target"] == "red" for r in sem["scarlet"].relations)

    # 2. Medium-term skill learning across labs
    med = learner.learn_medium_term_skill(
        name="flipseq",
        schema="list",
        teaching_examples=[
            dict(input=[1, 2, 3, 1], output=[1, 3, 2, 1]),
            dict(input=[4, 0, 2], output=[2, 0, 4]),
        ],
        held_out_checks=[dict(input=[9, 5, 1], output=[1, 5, 9])],
        counterexamples=[dict(input=[1, 2, 3], bad_output=[1, 2, 3])],
        lab="coding",
    )
    assert med["timescale"] == "medium_term"
    assert med["status"] == "accepted"
    assert med["counterexample_passed"]
    # Verify reusable across reasoning lab too
    run_out = brain.request(dict(op="lab_run", lab="reasoning", name="flipseq", input=[7, 8, 9]))["result"]
    assert run_out["output"] == [9, 8, 7]

    # 3. Long-term consolidation & Acceptance Gate (accept case + rollback case)
    acc = learner.consolidate_long_term(
        adapter_name="grounding_adapter_v1",
        new_task_scores=[0.88, 0.90, 0.89, 0.91],
        baseline_scores=[0.75, 0.76, 0.74, 0.75],
        retention_scores=[0.99, 1.0, 0.99, 1.0],
        transfer_scores=[0.80, 0.82, 0.81, 0.80],
        compute_cost_ms=18.0,
    )
    assert acc["accepted"] and acc["decision"] == "committed"

    rej = learner.consolidate_long_term(
        adapter_name="degrading_adapter_v2",
        new_task_scores=[0.85, 0.86, 0.84],
        baseline_scores=[0.75, 0.76, 0.74],
        retention_scores=[0.80, 0.82, 0.79],  # Fails retention >= 0.98
        transfer_scores=[0.78, 0.79, 0.77],
        compute_cost_ms=20.0,
    )
    assert not rej["accepted"] and rej["decision"] == "rolled_back"


def test_component12_grounded_response_generation_verification_gates():
    gen = GroundedResponseGenerator()
    plan = ResponsePlan(
        dialogue_act="inform",
        factual_claims=[
            dict(text="Verified calculation produced 42.", evidence="calc_trace_1"),
            dict(text="Unsupported hallucinated claim.", evidence=None),
        ],
        supporting_evidence=["calc_trace_1"],
        execution_results=[42],
        uncertainty=dict(confidence=0.70, status="provisional"),
    )
    # Candidate surface text that tries to alter 42 -> 43 or include unsupported claim is rejected in favor of verified fallback
    out = gen.render_and_verify(plan, candidate_surface_text="Verified calculation produced 43. Unsupported hallucinated claim.")
    assert out["used_fallback_template"]
    assert "42" in out["text"]
    assert "Unsupported hallucinated claim" not in out["text"]
    assert out["uncertainty_preserved"]


def test_component13_conversation_exchanges_and_deterministic_restore(tmp_path):
    w = SeedWorkspace(tmp_path)
    sid = w.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    # 1. Normal exchange
    r1 = w.dispatch(dict(session_id=sid, request=dict(op="master_dialogue", args=dict(text="Hello"))))["response"]["result"]
    assert r1["exchange_kind"] == "normal"
    assert "NEXUS Seed" in r1["response"]["text"]

    # 2. Learning exchange: '"Flip" means reverse the order of a sequence.'
    r2 = w.dispatch(dict(
        session_id=sid,
        request=dict(op="chat_send", text='"Flip" means reverse the order of a sequence.', id=uuid.uuid4().hex),
    ))["response"]
    assert "provisional concept" in r2["text"]
    assert "reverse" in r2["text"]
    assert "[1, 2, 3] -> [3, 2, 1]" in r2["text"]

    # 3. Reasoning exchange: 'If A is north of B and B is north of C, where is A relative to C?'
    r3 = w.dispatch(dict(
        session_id=sid,
        request=dict(op="chat_send", text="If A is north of B and B is north of C, where is A relative to C?", id=uuid.uuid4().hex),
    ))["response"]
    assert "A is north of C" in r3["text"]

    # 4. Sorting exchange via chat
    r4 = w.dispatch(dict(
        session_id=sid,
        request=dict(op="chat_send", text="Could you arrange these from smallest to largest? [4, 1, 3, 2]", id=uuid.uuid4().hex),
    ))["response"]
    assert "[1, 2, 3, 4]" in r4["text"]

    # Verify Session snapshot and deterministic restore with seed_master events
    snap = w.sessions[sid].snapshot()
    restored = Session.restore(snap)
    assert restored.snapshot() == snap


def test_component14_and_15_knowledge_acquisition_and_tiered_compute():
    session = Session()
    arch = MasterSeedArchitecture(session, device_profile="mobile_ios")

    doc_res = arch.acquisition.acquire_document("manual_note", "Mercury orbits Sun. Earth orbits Sun.")
    assert len(doc_res["units"]) == 2

    tbl_res = arch.acquisition.acquire_structured_table(
        "planets",
        [dict(subject="Mars", predicate="orbits", object="Sun")],
    )
    assert tbl_res["row_count"] == 1

    ret = arch.acquisition.sparse_retrieve("What orbits Sun?")
    assert not ret["scanned_full_memory"]
    assert len(ret["document_hits"]) >= 1

    # Tiered compute on mobile battery vs charging
    arch.compute.on_battery = True
    arch.compute.is_charging = False
    arch.compute.is_idle = False
    assert not arch.compute.should_run_background_consolidation()
    tier_consolidate = arch.compute.select_tier("consolidate")
    assert tier_consolidate["deferred_until_charging_and_idle"]
    assert tier_consolidate["tier"] == 1

    # 8-bit and 4-bit weight quantization
    q8 = arch.compute.quantize_weights([-0.5, 0.0, 0.25, 0.5], bits=8)
    assert q8["compression_ratio"] == 4.0 and q8["mean_absolute_error"] < 0.01
    q4 = arch.compute.quantize_weights([-0.5, 0.0, 0.25, 0.5], bits=4)
    assert q4["compression_ratio"] == 8.0 and q4["mean_absolute_error"] < 0.05


def test_natural_conversation_and_workable_learning_to_learn_suite(tmp_path):
    w = SeedWorkspace(tmp_path, attach_local_runtime=False)
    sid = w.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]

    how = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="how are u?", id=uuid.uuid4().hex)))["response"]
    assert "15-component" not in how["text"]
    assert "not a template" in how["text"]

    who = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="Who are you?", id=uuid.uuid4().hex)))["response"]
    assert "15-component" not in who["text"]
    assert "not a template" in who["text"]

    thx = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="Thank you!", id=uuid.uuid4().hex)))["response"]
    assert "15-component" not in thx["text"]
    assert "not a template" in thx["text"]

    arch = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="Explain how NEXUS works.", id=uuid.uuid4().hex)))["response"]
    assert "15" in arch["text"] and "architecture" in arch["text"].lower()

    math_reply = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="Solve 3*x + 7 = 22", id=uuid.uuid4().hex)))["response"]
    assert "5" in math_reply["text"]

    # Bounded exact-motif program-prior reuse demo & bounded multi-reasoner integration suite via chat and via master_general_suite
    ltl_chat = w.dispatch(dict(session_id=sid, request=dict(op="chat_send", text="Did we achieve learning to learn?", id=uuid.uuid4().hex)))["response"]
    assert ltl_chat["text"] == "Not yet. I demonstrated bounded program-prior reuse, but genuine held-out learning-to-learn remains unestablished."

    suite = w.dispatch(dict(session_id=sid, request=dict(op="master_general_suite", args={})))["response"]["result"]
    assert suite["suite_label"] == "bounded multi-reasoner integration suite"
    assert suite["all_domains_passed"]
    assert suite["domains_verified"] == 6
    bench = suite["learning_to_learn_benchmark"]
    assert bench["benchmark_label"] == "bounded exact-motif program-prior reuse demo"
    assert bench["claim_classification"] == "engineering demonstration of within-family search-prior reuse"
    assert len(bench["limitations"]) == 5
    assert bench["mean_meta_learned_evaluations"] < bench["mean_cold_start_evaluations"]
    assert bench["search_evaluations_reduction_pct"] > 50.0
    assert bench["acceptance_gate"]["accepted"]

    # Verify Session restore with all new events
    snap = w.sessions[sid].snapshot()
    assert Session.restore(snap).snapshot() == snap

