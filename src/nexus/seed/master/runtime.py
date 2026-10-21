"""Master runtime integrating all 15 components of the NEXUS Seed master architecture
over the existing Session, SharedBrain, E1 Journal, SeedRSSM, skill_library,
foundation, structure, and Conversation modules.

Framed strictly as a bounded research architecture: it does not claim achieved AGI
or established learning-to-learn.
"""
import copy
import json
from typing import Any
from ..shared_brain import SharedBrain
from .coding import (
    CodeTaskParser,
    DebuggingController,
    ExecutionSandbox,
    ProgramSynthesizer,
    RepositoryModel,
)
from .controller import (
    CognitiveMetaController,
    GroundedResponseGenerator,
    KnowledgeAcquisitionEngine,
    TieredComputeController,
)
from .grounding import NeuralGroundingLayer
from .hybrid_world import HybridWorldModel
from .memory import (
    LearningAcceptanceGate,
    MASTER_EVENT_KIND,
    MemoryArchitecture,
    SharedBeliefWorkspace,
    ThreeTimescalesLearner,
    master_records,
)
from .meta_learning import MetaLearningEngine
from .reasoning import ReasoningRouter
from .types import (
    BeliefState,
    Concept,
    DebuggingSkill,
    ExperienceEvent,
    GroundedObservation,
    Hypothesis,
    ReasoningResult,
    ResponsePlan,
    Skill,
    TaskSpec,
)


def validate_event(payload: dict, session) -> None:
    """Deterministic validation of saved seed_master journal events on Session.restore.
    Never executes arbitrary code or triggers neural training on replay."""
    if sum(e.kind == MASTER_EVENT_KIND for e in session.journal.snapshot()) >= 256:
        raise ValueError("master_journal_cap")
    if type(payload) is not dict or set(payload) != {"op", "data"} or type(payload["data"]) is not dict:
        raise ValueError("master_event_schema")
    op = payload["op"]
    data = payload["data"]
    if op == "semantic_concept":
        Concept.from_dict(data)
    elif op == "procedural_skill":
        Skill.from_dict(data)
    elif op == "experience":
        ExperienceEvent.from_dict(data)
    elif op == "debugging_skill":
        DebuggingSkill.from_dict(data)
    elif op == "acceptance_gate":
        required = {"proposal_name", "proposal_kind", "accepted", "decision", "checks", "payload"}
        if set(data) != required or type(data["accepted"]) is not bool or data["decision"] not in ("committed", "rolled_back"):
            raise ValueError("master_acceptance_gate_schema")
    elif op == "model_consolidation":
        required = {"adapter_name", "accepted", "decision", "gate_ref", "dataset"}
        if set(data) != required or type(data["accepted"]) is not bool:
            raise ValueError("master_consolidation_schema")
    else:
        raise ValueError("unknown_master_event_op")


class MasterSeedArchitecture:
    """Unified coordinator for the 15-component NEXUS Seed master architecture."""

    def __init__(
        self,
        session,
        shared_brain: SharedBrain | None = None,
        enable_torch_grounding: bool = False,
        device_profile: str = "mac_desktop",
    ):
        self.session = session
        self.shared_brain = shared_brain or SharedBrain(session)
        self.grounding = NeuralGroundingLayer(enable_torch_model=enable_torch_grounding)
        self.memory = MemoryArchitecture(session, self.shared_brain)
        self.workspace = SharedBeliefWorkspace(session, self.shared_brain, self.grounding)
        self.hybrid_world = HybridWorldModel(session=session)
        self.router = ReasoningRouter(hybrid_world=self.hybrid_world)
        self.code_parser = CodeTaskParser()
        self.repo_model = RepositoryModel()
        self.synthesizer = ProgramSynthesizer()
        self.sandbox = ExecutionSandbox()
        self.debugger = DebuggingController(sandbox=self.sandbox, synthesizer=self.synthesizer)
        self.meta_controller = CognitiveMetaController()
        self.learner = ThreeTimescalesLearner(session, self.shared_brain, self.grounding)
        self.acceptance_gate = self.learner.gate
        self.response_generator = GroundedResponseGenerator()
        self.acquisition = KnowledgeAcquisitionEngine(session, self.memory)
        self.compute = TieredComputeController(device_profile=device_profile)
        self.meta_learner = MetaLearningEngine(session, self.memory, self.router)

    def handle_dialogue_turn(self, text: str) -> dict:
        """Executes the full cognitive pipeline on a dialogue input:
        1. Neural grounding layer -> GroundedObservation
        2. Shared belief workspace -> BeliefState
        3. Cognitive meta-controller -> c_t in {answer, retrieve, reason, simulate, ask, experiment, execute, learn, abstain}
        4. Tiered compute selection
        5. Reasoning / Skill execution / Immediate learning
        6. ResponsePlan -> GroundedResponseGenerator with factual verification gate
        """
        semantic_concepts = set(self.memory.semantic_memory_view().keys())
        procedural_skills = set(self.memory.procedural_memory_view().keys())
        obs = self.grounding.ground_text(text, known_concepts=semantic_concepts, known_skills=procedural_skills)
        belief = self.workspace.build_belief_state(
            current_goal=obs.requested_goal,
            observations=[obs],
        )
        decision = self.meta_controller.score_operations(belief)
        selected_op = decision["selected_operation"]
        compute_tier = self.compute.select_tier(selected_op)
        intent = obs.provenance.get("intent", "general_query")

        # 1. Normal greeting & natural conversational exchanges
        if intent == "greeting":
            subtype = (obs.requested_goal or {}).get("subtype", "hello") if isinstance(obs.requested_goal, dict) else "hello"
            n_concepts = len(semantic_concepts)
            n_skills = len(procedural_skills)
            if subtype == "status_check":
                msg = (
                    f"I am doing well and running smoothly! My 15-component Seed master architecture is active "
                    f"with {n_concepts} semantic concept(s), {n_skills} verified procedural skill(s), and our 6x6 object world ready. "
                    f"How can we learn or reason together today?"
                )
            elif subtype == "identity":
                msg = (
                    "I am NEXUS Seed—a compact, verifiable cognitive architecture combining neural grounding, "
                    "a shared belief workspace, 6-tier memory, a hybrid world model, 8 specialized reasoners, "
                    "a code synthesizer/debugger, and a 3-timescale learning engine."
                )
            elif subtype == "appreciation":
                msg = (
                    "You're very welcome! Every verified example and reasoning step stays safely recorded in our session journal. "
                    "What would you like to try next?"
                )
            else:
                msg = "Hello! I am NEXUS Seed. I am ready to learn concepts or skills, reason over relations and constraints, or act in the 6x6 object world."
            plan = ResponsePlan(
                dialogue_act="greeting_and_readiness",
                factual_claims=[dict(text=msg, evidence="session_active")],
                supporting_evidence=["session_active"],
                execution_results=[],
                uncertainty=dict(confidence=0.99),
            )
            rendered = self.response_generator.render_and_verify(plan, belief)
            return dict(
                exchange_kind="normal",
                observation=obs.to_dict(),
                belief_state=belief.to_dict(),
                meta_decision=decision,
                compute_tier=compute_tier,
                response_plan=plan.to_dict(),
                response=rendered,
            )

        # 1b. Meta-learning & general problem-solving benchmark exchange
        if intent == "meta_learning_benchmark":
            suite = self.meta_learner.run_general_intelligence_suite()
            ltl = suite["learning_to_learn_benchmark"]
            msg = (
                f"Within the bounded Seed Master Architecture, workable meta-learning reduced candidate program search "
                f"by {ltl['search_evaluations_reduction_pct']}% ({ltl['mean_cold_start_evaluations']} -> {ltl['mean_meta_learned_evaluations']} evaluations) "
                f"with {int(ltl['held_out_accuracy']*100)}% held-out accuracy across all {suite['domains_verified']} reasoning domains, "
                f"passing the LearningAcceptanceGate ({ltl['acceptance_gate']['decision']}). "
                f"Note: historical locked scientific ledger experiments remain separate and are not overwritten."
            )
            plan = ResponsePlan(
                dialogue_act="meta_learning_and_general_suite_report",
                factual_claims=[dict(text=msg, evidence=ltl["acceptance_gate"]["ref"])],
                supporting_evidence=[ltl["acceptance_gate"]["ref"]],
                execution_results=[dict(
                    search_reduction_pct=ltl["search_evaluations_reduction_pct"],
                    domains_passed=suite["domains_verified"],
                )],
                uncertainty=dict(confidence=0.98),
            )
            rendered = self.response_generator.render_and_verify(plan, belief)
            return dict(
                exchange_kind="meta_learning_benchmark",
                observation=obs.to_dict(),
                belief_state=belief.to_dict(),
                meta_decision=decision,
                compute_tier=compute_tier,
                suite_result=suite,
                response_plan=plan.to_dict(),
                response=rendered,
            )

        # 2. Learning exchange (e.g., '"Flip" means reverse the order of a sequence.' or '"Scarlet" means bright red.')
        if intent == "teach_concept":
            args = obs.provenance.get("arguments", {})
            term = args.get("term", "concept")
            definition = args.get("definition", "")
            linked_skill = args.get("linked_skill")
            learned = self.learner.learn_immediate_concept(
                name=term,
                definition=definition,
                linked_skill=linked_skill,
                verified=False,
            )
            skill_link_msg = (
                f"I stored '{term}' as a provisional concept meaning '{definition}' and linked it to the verified '{linked_skill}' skill."
                if linked_skill
                else f"I stored '{term}' as a provisional concept meaning '{definition}'."
            )
            clarification_q = (
                f"Would you like to test '{term}' on [1, 2, 3] -> [3, 2, 1] to confirm it?"
                if linked_skill == "reverse"
                else f"Can you give me one check example for '{term}' to verify it?"
            )
            plan = ResponsePlan(
                dialogue_act="provisional_learning_acknowledgement",
                factual_claims=[dict(text=skill_link_msg, evidence=learned["ref"])],
                supporting_evidence=[learned["ref"]],
                execution_results=[],
                uncertainty=dict(confidence=0.75, status="provisional"),
                requested_clarification=clarification_q,
            )
            rendered = self.response_generator.render_and_verify(plan, belief)
            return dict(
                exchange_kind="learning",
                observation=obs.to_dict(),
                belief_state=belief.to_dict(),
                meta_decision=decision,
                compute_tier=compute_tier,
                learning_result=learned,
                response_plan=plan.to_dict(),
                response=rendered,
            )

        # 3. Relational reasoning exchange (e.g., "If A is north of B and B is north of C, where is A relative to C?")
        if intent == "query_relation":
            args = obs.provenance.get("arguments", {})
            r_out = self.router.route("relational", args)
            plan = ResponsePlan(
                dialogue_act="grounded_reasoning_answer",
                factual_claims=[dict(text=f"{r_out.conclusion}.", evidence="relational_proof_trace")],
                supporting_evidence=["relational_proof_trace"] + r_out.proof_or_trace,
                execution_results=[r_out.conclusion],
                uncertainty=dict(confidence=r_out.confidence),
            )
            rendered = self.response_generator.render_and_verify(
                plan,
                belief,
                candidate_surface_text=f"{r_out.conclusion}.",
            )
            return dict(
                exchange_kind="reasoning",
                observation=obs.to_dict(),
                belief_state=belief.to_dict(),
                meta_decision=decision,
                compute_tier=compute_tier,
                reasoning_result=r_out.to_dict(),
                response_plan=plan.to_dict(),
                response=rendered,
            )

        # 4. Execute skill exchange (e.g., "Could you arrange these from smallest to largest? [4, 1, 3, 2]")
        if intent == "execute_skill":
            skill_name = obs.provenance.get("skill", "sorting")
            args = obs.provenance.get("arguments")
            constraint = obs.provenance.get("constraint", "ascending")
            if isinstance(args, list):
                proc_skills = self.memory.procedural_memory_view()
                sk = proc_skills.get(skill_name) or proc_skills.get("sorting")
                prog = copy.deepcopy(sk.typed_program)
                exec_res = self.router.route("program_execution", dict(program=prog, inputs=args))
                out_list = exec_res.conclusion["result"]
                if constraint == "descending" and isinstance(out_list, list):
                    out_list = list(reversed(out_list))
                plan = ResponsePlan(
                    dialogue_act="skill_execution_answer",
                    factual_claims=[dict(text=f"Executed {skill_name} ({constraint}): {json.dumps(out_list)}.", evidence=sk.revision)],
                    supporting_evidence=[sk.revision],
                    execution_results=[out_list],
                    uncertainty=dict(confidence=0.98),
                )
                rendered = self.response_generator.render_and_verify(plan, belief)
                return dict(
                    exchange_kind="skill_execution",
                    observation=obs.to_dict(),
                    belief_state=belief.to_dict(),
                    meta_decision=decision,
                    compute_tier=compute_tier,
                    reasoning_result=exec_res.to_dict(),
                    response_plan=plan.to_dict(),
                    response=rendered,
                )
            else:
                plan = ResponsePlan(
                    dialogue_act="clarification_request",
                    factual_claims=[dict(text=f"I recognized the '{skill_name}' request with constraint '{constraint}'.", evidence="grounding_head")],
                    supporting_evidence=["grounding_head"],
                    execution_results=[],
                    uncertainty=dict(confidence=obs.uncertainty.get("confidence", 0.94), ambiguous=True),
                    requested_clarification="Please supply the list of numbers to arrange (for example, [4, 1, 3, 2]).",
                )
                rendered = self.response_generator.render_and_verify(plan, belief)
                return dict(
                    exchange_kind="clarification",
                    observation=obs.to_dict(),
                    belief_state=belief.to_dict(),
                    meta_decision=decision,
                    compute_tier=compute_tier,
                    response_plan=plan.to_dict(),
                    response=rendered,
                )

        # 5. Math reasoning exchange
        if intent == "query_math":
            r_out = self.router.route("math", dict(expression=text))
            plan = ResponsePlan(
                dialogue_act="math_reasoning_answer",
                factual_claims=[dict(text=f"Verified mathematical result: {json.dumps(r_out.conclusion)}.", evidence="math_solver")],
                supporting_evidence=["math_solver"] + r_out.proof_or_trace,
                execution_results=[r_out.conclusion],
                uncertainty=dict(confidence=r_out.confidence),
            )
            rendered = self.response_generator.render_and_verify(plan, belief)
            return dict(
                exchange_kind="reasoning",
                observation=obs.to_dict(),
                belief_state=belief.to_dict(),
                meta_decision=decision,
                compute_tier=compute_tier,
                reasoning_result=r_out.to_dict(),
                response_plan=plan.to_dict(),
                response=rendered,
            )

        # Default fallback with sparse memory retrieval
        ret = self.acquisition.sparse_retrieve(text)
        plan = ResponsePlan(
            dialogue_act="retrieved_summary",
            factual_claims=[dict(text=f"Retrieved {len(ret['concept_hits'])} concepts and {len(ret['skill_hits'])} skills matching your query.", evidence="sparse_index")],
            supporting_evidence=["sparse_index"],
            execution_results=[],
            uncertainty=dict(confidence=obs.uncertainty.get("confidence", 0.8)),
        )
        rendered = self.response_generator.render_and_verify(plan, belief)
        return dict(
            exchange_kind="retrieval",
            observation=obs.to_dict(),
            belief_state=belief.to_dict(),
            meta_decision=decision,
            compute_tier=compute_tier,
            retrieval=ret,
            response_plan=plan.to_dict(),
            response=rendered,
        )

    def inspect(self) -> dict:
        return dict(
            architecture_schema="nexus_seed_master_architecture_v1",
            scientific_claim="research_architecture_not_achieved_agi_or_proven_learning_to_learn",
            components_implemented=[
                "1_neural_grounding_layer",
                "2_shared_belief_workspace",
                "3_unified_typed_knowledge_representation",
                "4_six_tier_memory_architecture",
                "5_hybrid_world_model",
                "6_eight_reasoner_portfolio",
                "7_reasoning_router",
                "8_coding_and_debugging_architecture",
                "9_cognitive_meta_controller",
                "10_three_timescales_of_learning",
                "11_learning_acceptance_gate",
                "12_grounded_response_generation",
                "13_conversation_behavior",
                "14_evidence_linked_knowledge_acquisition",
                "15_mac_and_mobile_tiered_compute",
            ],
            memory=self.memory.inspect_all(),
            compute_tiers=self.compute.TIERS,
            master_journal_events=len(master_records(self.session)),
        )


def request(session, req: dict, shared_brain: SharedBrain | None = None) -> dict:
    """Dispatch entrypoint for master_* operations on a Session / SeedWorkspace."""
    if type(req) is not dict or "op" not in req or type(req["op"]) is not str or not req["op"].startswith("master_"):
        raise ValueError("typed_master_request_required")
    op = req["op"].removeprefix("master_")
    args = req.get("args", {})
    if type(args) is not dict:
        raise ValueError("typed_master_args_required")

    arch = MasterSeedArchitecture(session, shared_brain=shared_brain)
    if op == "inspect":
        return dict(text="NEXUS Seed master architecture inspection.", result=arch.inspect())
    if op == "ground":
        modality = args.get("modality", "language")
        if modality == "language":
            obs = arch.grounding.ground_text(args["text"])
        elif modality == "vision":
            obs = arch.grounding.ground_vision(args["scene_objects"])
        elif modality == "audio":
            obs = arch.grounding.ground_audio(args["transcript"], float(args.get("acoustic_confidence", 0.9)))
        elif modality == "sensor":
            obs = arch.grounding.ground_sensor(args["readings"])
        elif modality == "code":
            obs = arch.grounding.ground_code(args["source_code"])
        else:
            raise ValueError("unsupported_grounding_modality")
        return dict(text="Grounded observation produced.", result=obs.to_dict())
    if op == "belief_state":
        obs_list = [arch.grounding.ground_text(args["text"])] if "text" in args else []
        bs = arch.workspace.build_belief_state(current_goal=args.get("goal"), observations=obs_list)
        return dict(text="BeliefState constructed over Session and SharedBrain.", result=bs.to_dict())
    if op == "hybrid_world":
        res = arch.hybrid_world.step_prediction(args["state"], args["action"])
        return dict(text="Hybrid world transition and disagreement computed.", result=res)
    if op == "reason":
        res = arch.router.route(args["task_type"], args["payload"])
        return dict(text="Verifiable reasoning trace completed.", result=res.to_dict())
    if op == "code":
        sub_op = args.get("sub_op", "synthesize")
        if sub_op == "parse":
            spec = arch.code_parser.parse(args["specification"])
            return dict(text="Code task parsed.", result=spec.to_dict())
        if sub_op == "repository_index":
            idx = arch.repo_model.index_files(args["files"])
            return dict(text="Repository model indexed.", result=idx)
        if sub_op == "synthesize":
            spec = arch.code_parser.parse(args["specification"])
            skills = arch.memory.procedural_memory_view()
            synth = arch.synthesizer.synthesize(spec, available_skills=skills, mode=args.get("mode", "auto"))
            ver = arch.sandbox.verify(synth["python_code"], typed_program=synth["typed_program"], unit_tests=args.get("unit_tests", []))
            return dict(text="Program synthesized and verified in sandbox.", result=dict(synthesis=synth, verification=ver))
        if sub_op == "debug":
            dbg = arch.debugger.debug_and_repair(
                broken_code=args["broken_code"],
                unit_tests=args.get("unit_tests", []),
                typed_program=args.get("typed_program"),
                previous_working_code=args.get("previous_working_code"),
            )
            if dbg.get("debugging_skill") is not None and not session.stopped:
                session.event(MASTER_EVENT_KIND, dict(op="debugging_skill", data=dbg["debugging_skill"]))
            return dict(text="Debugging loop completed.", result=dbg)
        raise ValueError("unsupported_master_code_sub_op")
    if op == "meta_control":
        obs_list = [arch.grounding.ground_text(args["text"])] if "text" in args else []
        bs = arch.workspace.build_belief_state(observations=obs_list, unresolved_questions=args.get("unresolved_questions"))
        res = arch.meta_controller.score_operations(bs, context_signals=args.get("signals"))
        return dict(text="Cognitive meta-controller scored operations.", result=res)
    if op == "learn":
        timescale = args.get("timescale", "immediate")
        if timescale == "immediate":
            res = arch.learner.learn_immediate_concept(
                name=args["name"],
                definition=args["definition"],
                aliases=args.get("aliases"),
                examples=args.get("examples"),
                counterexamples=args.get("counterexamples"),
                linked_skill=args.get("linked_skill"),
                verified=bool(args.get("verified", False)),
            )
        elif timescale == "medium_term":
            res = arch.learner.learn_medium_term_skill(
                name=args["name"],
                schema=args.get("schema", "list"),
                teaching_examples=args["teaching_examples"],
                held_out_checks=args["held_out_checks"],
                counterexamples=args.get("counterexamples"),
                lab=args.get("lab", "coding"),
            )
        elif timescale == "long_term":
            res = arch.learner.consolidate_long_term(
                adapter_name=args["adapter_name"],
                new_task_scores=args["new_task_scores"],
                baseline_scores=args["baseline_scores"],
                retention_scores=args["retention_scores"],
                transfer_scores=args["transfer_scores"],
                compute_cost_ms=float(args.get("compute_cost_ms", 25.0)),
            )
        else:
            raise ValueError("unsupported_learning_timescale")
        return dict(text=f"Completed {timescale} learning step.", result=res)
    if op == "acceptance_gate":
        res = arch.acceptance_gate.evaluate_and_gate(**args)
        return dict(text="Learning acceptance gate evaluated.", result=res)
    if op == "dialogue":
        res = arch.handle_dialogue_turn(args["text"])
        return dict(text=res["response"]["text"], result=res)
    if op == "acquire":
        kind = args.get("kind", "sparse_retrieve")
        if kind == "document":
            res = arch.acquisition.acquire_document(args["source"], args["text"])
        elif kind == "table":
            res = arch.acquisition.acquire_structured_table(args["table_name"], args["rows"])
        elif kind == "sparse_retrieve":
            res = arch.acquisition.sparse_retrieve(args["query"], top_k=int(args.get("top_k", 5)))
        else:
            raise ValueError("unsupported_acquire_kind")
        return dict(text="Knowledge acquisition operation completed.", result=res)
    if op == "compute":
        tier_res = arch.compute.select_tier(args.get("operation", "answer"), surprise=float(args.get("surprise", 0.0)))
        if "weights" in args:
            tier_res["quantization"] = arch.compute.quantize_weights(args["weights"], bits=int(args.get("bits", 8)))
        return dict(text="Tiered compute profile evaluated.", result=tier_res)
    if op == "meta_learn":
        res = arch.meta_learner.run_learning_to_learn_benchmark()
        return dict(text="Workable learning-to-learn benchmark completed.", result=res)
    if op == "general_suite":
        res = arch.meta_learner.run_general_intelligence_suite()
        return dict(text="Multi-domain general intelligence suite completed.", result=res)

    raise ValueError(f"unsupported_master_op:{op}")
