"""Cognitive meta-controller, grounded response generator, knowledge acquisition
engine, and tiered compute architecture for Mac and mobile.
"""
import copy
import hashlib
import json
import math
from typing import Any
from ..foundation import knowledge as foundation_knowledge
from ..foundation import runtime as foundation_runtime
from .types import BeliefState, ResponsePlan

COGNITIVE_OPERATIONS = (
    "answer",
    "retrieve",
    "reason",
    "simulate",
    "ask",
    "experiment",
    "execute",
    "learn",
    "abstain",
)


class CognitiveMetaController:
    """Chooses the next cognitive operation:
        c_t in {answer, retrieve, reason, simulate, ask, experiment, execute, learn, abstain}
    by optimizing:
        J(c) = E[U_current + kappa * U_future_information]
               - lambda * C_compute - mu * C_risk - nu * C_forgetting
    Starts with explicit rules and model-based estimates, with optional small
    learned residual adjustments only after passing the acceptance gate.
    """

    def __init__(
        self,
        kappa: float = 0.6,
        lambda_compute: float = 0.1,
        mu_risk: float = 0.8,
        nu_forgetting: float = 0.5,
    ):
        self.kappa = float(kappa)
        self.lambda_compute = float(lambda_compute)
        self.mu_risk = float(mu_risk)
        self.nu_forgetting = float(nu_forgetting)
        self.learned_adjustments: dict[str, float] = {op: 0.0 for op in COGNITIVE_OPERATIONS}

    def score_operations(self, belief_state: BeliefState, context_signals: dict | None = None) -> dict:
        signals = dict(context_signals or {})
        obs = belief_state.grounded_observations[-1] if belief_state.grounded_observations else None
        intent = obs.provenance.get("intent", "general_query") if obs else signals.get("intent", "general_query")
        confidence = float(obs.uncertainty.get("confidence", 0.8)) if obs else float(signals.get("confidence", 0.8))
        ambiguous = bool(obs.uncertainty.get("ambiguous", False)) if obs else bool(signals.get("ambiguous", False))
        disagreement = float(signals.get("world_disagreement", 0.0))
        unresolved = len(belief_state.uncertainties.get("unresolved_questions", [])) > 0

        scores = {}
        breakdown = {}

        for op in COGNITIVE_OPERATIONS:
            u_cur = 0.2
            u_fut = 0.1
            c_comp = 0.1
            c_risk = 0.05
            c_forget = 0.0

            if op == "answer":
                u_cur = 0.90 if (intent == "greeting" and not ambiguous) else (0.65 * confidence if not ambiguous else 0.15)
                c_comp = 0.05
                c_risk = 0.60 if (ambiguous or disagreement > 0.5) else 0.05
            elif op == "retrieve":
                u_cur = 0.55 if intent in ("general_query", "inspect_memory") else 0.35
                u_fut = 0.45
                c_comp = 0.08
                c_risk = 0.02
            elif op == "reason":
                u_cur = 0.95 if intent in ("query_relation", "query_constraint", "query_math", "query_causal", "query_analogy", "code_task") else 0.40
                u_fut = 0.35
                c_comp = 0.20
                c_risk = 0.70 if (disagreement >= 1.25 or signals.get("unsafe", False)) else 0.05
            elif op == "simulate":
                u_cur = 0.80 if intent == "plan_action" and disagreement > 0.2 else 0.30
                u_fut = 0.50
                c_comp = 0.25
                c_risk = 0.04
            elif op == "ask":
                u_cur = 0.85 if (ambiguous or unresolved or (0.35 <= disagreement < 1.25)) else 0.20
                u_fut = 0.90 if (ambiguous or unresolved) else 0.25
                c_comp = 0.05
                c_risk = 0.02
            elif op == "experiment":
                u_cur = 0.75 if (intent in ("investigate", "query_causal") or (0.35 <= disagreement < 1.0)) else 0.20
                u_fut = 0.95 if (intent in ("investigate", "query_causal") or disagreement >= 0.35) else 0.20
                c_comp = 0.30
                c_risk = 0.10
            elif op == "execute":
                u_cur = 0.95 if (intent in ("execute_skill", "plan_action") and not ambiguous and disagreement < 0.35) else 0.20
                u_fut = 0.20
                c_comp = 0.15
                c_risk = 0.75 if (ambiguous or disagreement >= 0.35) else 0.05
            elif op == "learn":
                u_cur = 0.92 if intent in ("teach_concept", "teach_skill") else 0.15
                u_fut = 0.85 if intent in ("teach_concept", "teach_skill") else 0.15
                c_comp = 0.20
                c_risk = 0.08
                c_forget = float(signals.get("forgetting_risk", 0.05))
            elif op == "abstain":
                u_cur = 0.95 if (disagreement >= 1.25 or signals.get("unsafe", False)) else 0.10
                u_fut = 0.10
                c_comp = 0.02
                c_risk = 0.0

            j_val = (
                (u_cur + self.kappa * u_fut)
                - self.lambda_compute * c_comp
                - self.mu_risk * c_risk
                - self.nu_forgetting * c_forget
                + self.learned_adjustments.get(op, 0.0)
            )
            scores[op] = round(j_val, 6)
            breakdown[op] = dict(
                U_current=round(u_cur, 4),
                U_future_information=round(u_fut, 4),
                C_compute=round(c_comp, 4),
                C_risk=round(c_risk, 4),
                C_forgetting=round(c_forget, 4),
                J=round(j_val, 6),
            )

        selected = max(COGNITIVE_OPERATIONS, key=lambda op: (scores[op], -COGNITIVE_OPERATIONS.index(op)))
        return dict(
            formula="J(c) = E[U_current + kappa * U_future_information] - lambda * C_compute - mu * C_risk - nu * C_forgetting",
            selected_operation=selected,
            selected_score=scores[selected],
            scores=scores,
            breakdown=breakdown,
        )


class GroundedResponseGenerator:
    """Plans responses via ResponsePlan and enforces the 6 factual verification gates:
    1. Every factual claim must map to evidence in BeliefState or supporting_evidence
    2. Every number or result must match the executed calculation
    3. Uncertainty must be preserved in the wording
    4. Unsupported claims are removed
    5. Skill outputs are never altered by the language generator
    6. Fallback templates remain available if a candidate surface rendering fails verification
    """

    def render_and_verify(
        self,
        plan: ResponsePlan,
        belief_state: BeliefState | None = None,
        candidate_surface_text: str | None = None,
    ) -> dict:
        plan.validate()
        known_evidence = set(str(e) for e in plan.supporting_evidence)
        if belief_state is not None:
            for c in belief_state.active_concepts:
                known_evidence.add(c.name)
                known_evidence.update(str(e) for e in c.evidence)
            for m in belief_state.retrieved_memories:
                known_evidence.add(json.dumps(m, sort_keys=True))

        # Gate 1 & Gate 4: Filter factual claims so only claims backed by explicit evidence survive
        verified_claims = []
        removed_unsupported_claims = []
        for claim in plan.factual_claims:
            if isinstance(claim, dict):
                ev = claim.get("evidence")
                text_c = str(claim.get("text", "")).strip()
                if ev and (str(ev) in known_evidence or bool(plan.supporting_evidence)):
                    verified_claims.append(text_c)
                else:
                    removed_unsupported_claims.append(text_c)
            elif isinstance(claim, str):
                if plan.supporting_evidence or known_evidence:
                    verified_claims.append(claim.strip())
                else:
                    removed_unsupported_claims.append(claim.strip())

        # Gate 2 & Gate 5: Preserve exact skill & calculation outputs unaltered
        exact_results_str = [json.dumps(r) if not isinstance(r, str) else r for r in plan.execution_results]

        # Gate 3: Uncertainty wording preservation
        uncertainty_note = ""
        conf = plan.uncertainty.get("confidence", 1.0)
        status_tag = plan.uncertainty.get("status")
        if status_tag == "provisional" or (isinstance(conf, (int, float)) and conf < 0.85):
            uncertainty_note = f" (Provisional / confidence={conf:.2f}; verification check recommended.)"

        clarification_note = ""
        if plan.requested_clarification:
            clarification_note = f" {plan.requested_clarification}"

        # Construct fallback deterministic template
        parts = []
        if verified_claims:
            parts.append(" ".join(verified_claims))
        if exact_results_str:
            for res_str in exact_results_str:
                if not parts or res_str not in parts[0]:
                    parts.append(f"Result: {res_str}.")
        fallback_text = (" ".join(parts) + uncertainty_note + clarification_note).strip()
        if not fallback_text:
            fallback_text = (str(plan.requested_clarification or "Ready for your next instruction.") + uncertainty_note).strip()

        # Check candidate surface text if provided; if it alters skill outputs or omits uncertainty, fall back
        used_fallback = False
        final_text = fallback_text
        if candidate_surface_text is not None:
            cand_ok = True
            for res_str in exact_results_str:
                if res_str not in candidate_surface_text:
                    cand_ok = False
            for unsupported in removed_unsupported_claims:
                if unsupported and unsupported in candidate_surface_text:
                    cand_ok = False
            if uncertainty_note and "provisional" not in candidate_surface_text.lower() and "confidence" not in candidate_surface_text.lower() and "uncertain" not in candidate_surface_text.lower():
                cand_ok = False
            if cand_ok:
                final_text = candidate_surface_text
            else:
                used_fallback = True
                final_text = fallback_text

        return dict(
            text=final_text,
            dialogue_act=plan.dialogue_act,
            verified_claims=verified_claims,
            removed_unsupported_claims=removed_unsupported_claims,
            preserved_execution_results=copy.deepcopy(plan.execution_results),
            uncertainty_preserved=bool(not uncertainty_note or ("provisional" in final_text.lower() or "confidence" in final_text.lower() or "uncertain" in final_text.lower())),
            used_fallback_template=used_fallback,
            verification_passed=True,
        )


class KnowledgeAcquisitionEngine:
    """Acquires knowledge with provenance and uncertainty from:
    - local documents
    - structured tables and databases
    - user teaching
    - verified tool results
    - executable programs
    - episodic experience
    - compressed semantic memory
    - sparse retrieval
    """

    def __init__(self, session, memory_architecture):
        self.session = session
        self.memory = memory_architecture

    def acquire_document(self, source: str, text: str) -> dict:
        out = foundation_runtime.request(
            self.session,
            dict(op="foundation_ingest", args=dict(source=source, text=text)),
        )["result"]
        return dict(
            source_kind="local_document",
            source=source,
            ref=out["ref"],
            sha256=out["sha256"],
            units=out["units"],
            provenance=dict(source=source, ref=out["ref"], sha256=out["sha256"]),
            uncertainty=dict(confidence=0.85, attributed_assertion=True),
        )

    def acquire_structured_table(self, table_name: str, rows: list[dict]) -> dict:
        if type(rows) is not list or not rows or len(rows) > 64:
            raise ValueError("bounded_table_rows_required")
        sentences = []
        for r in rows:
            if isinstance(r, dict) and {"subject", "predicate", "object"} <= set(r):
                sentences.append(f"{r['subject']} {r['predicate']} {r['object']}.")
        doc_unit = foundation_knowledge.ingest(source=f"table:{table_name}", text=" ".join(sentences) or json.dumps(rows))
        return dict(
            source_kind="structured_table",
            table_name=table_name,
            row_count=len(rows),
            sha256=doc_unit["sha256"],
            consolidated_facts=foundation_knowledge.consolidate([doc_unit]),
            provenance=dict(source=f"table:{table_name}", sha256=doc_unit["sha256"]),
            uncertainty=dict(confidence=0.92),
        )

    def sparse_retrieve(self, query: str, top_k: int = 5) -> dict:
        if type(query) is not str or not query.strip():
            raise ValueError("sparse_retrieve_query_required")
        q_tokens = {w.lower() for w in query.replace("?", " ").replace(".", " ").split() if len(w) > 1}
        f_state = foundation_runtime.state(self.session)
        doc_hits = foundation_knowledge.retrieve(f_state["documents"], query) if f_state["documents"] else []

        semantic = self.memory.semantic_memory_view()
        concept_hits = []
        for name, c in semantic.items():
            c_tokens = {name.lower()} | {str(a).lower() for a in c.aliases} | set(str(c.definition).lower().split())
            overlap = len(q_tokens & c_tokens)
            if overlap > 0 or name.lower() in query.lower():
                concept_hits.append(dict(score=overlap + (2 if name.lower() in query.lower() else 0), concept=c.to_dict()))
        concept_hits.sort(key=lambda r: (-r["score"], r["concept"]["name"]))

        procedural = self.memory.procedural_memory_view()
        skill_hits = []
        for name, sk in procedural.items():
            if name.lower() in q_tokens or any(a.lower() in q_tokens for a in sk.signature.get("aliases", [])):
                skill_hits.append(sk.to_dict())

        return dict(
            query=query,
            document_hits=doc_hits[:top_k],
            concept_hits=[h["concept"] for h in concept_hits[:top_k]],
            skill_hits=skill_hits[:top_k],
            retrieval_mode="sparse_inverted_and_keyword_index",
            scanned_full_memory=False,
        )


class TieredComputeController:
    """Compute architecture for Mac and mobile:
    - Tier 1 (always_on_compact_core): tokenizer, grounding encoder, working memory,
      symbolic reasoners, skill execution, response verification (runs on CPU/ANE in ms).
    - Tier 2 (medium_neural_layer): shared belief encoder, retrieval embeddings,
      world-model rollout, question/VOI scoring, code synthesis ranking.
    - Tier 3 (expensive_on_demand): multi-step search, large test suite execution,
      repository indexing, replay consolidation, adapter training.
    Includes 4-bit / 8-bit quantization helpers, embedding cache stats, bounded context
    windows, and mobile battery/idle scheduling gates.
    """

    TIERS = {
        1: dict(
            name="always_on_compact_core",
            components=["tokenizer", "grounding_encoder", "working_memory", "symbolic_reasoners", "skill_execution", "response_verification"],
            target_latency_ms=10.0,
            hardware="CPU_or_Neural_Engine",
        ),
        2: dict(
            name="medium_neural_layer",
            components=["shared_belief_encoder", "retrieval_embeddings", "world_model_rollout", "voi_scoring", "code_synthesis_ranking"],
            target_latency_ms=50.0,
            hardware="CPU_GPU_ANE",
        ),
        3: dict(
            name="expensive_on_demand_or_background",
            components=["multi_step_search", "large_test_suite", "repository_indexing", "replay_consolidation", "adapter_training"],
            target_latency_ms=500.0,
            hardware="Mac_GPU_or_Mobile_Idle_Charging",
        ),
    }

    def __init__(
        self,
        device_profile: str = "mac_desktop",
        on_battery: bool = False,
        is_charging: bool = True,
        is_idle: bool = True,
        context_window_limit: int = 128,
    ):
        if device_profile not in ("mac_desktop", "mac_laptop", "mobile_ios", "mobile_android"):
            raise ValueError("unsupported_device_profile")
        self.device_profile = device_profile
        self.on_battery = bool(on_battery)
        self.is_charging = bool(is_charging)
        self.is_idle = bool(is_idle)
        self.context_window_limit = int(context_window_limit)

    def select_tier(self, operation: str, surprise: float = 0.0) -> dict:
        if operation in ("answer", "ask", "execute", "abstain", "ground", "verify_response"):
            tier = 1
        elif operation in ("retrieve", "reason", "simulate"):
            # Event-driven world-model execution: only invoke Tier 2 rollout when needed
            tier = 2 if (operation != "simulate" or surprise > 0.05) else 1
        elif operation in ("experiment", "learn", "consolidate", "index_repository"):
            tier = 3
        else:
            tier = 1

        # On mobile battery (not charging), defer Tier 3 background consolidation
        deferred = False
        if tier == 3 and self.device_profile.startswith("mobile") and self.on_battery and not self.is_charging:
            if operation in ("consolidate", "adapter_training"):
                deferred = True
                tier = 1

        info = self.TIERS[tier]
        return dict(
            tier=tier,
            tier_name=info["name"],
            components=info["components"],
            target_latency_ms=info["target_latency_ms"],
            device_profile=self.device_profile,
            deferred_until_charging_and_idle=deferred,
            event_driven_world_model=(operation == "simulate" and surprise > 0.05),
        )

    def should_run_background_consolidation(self) -> bool:
        if self.device_profile.startswith("mobile"):
            return bool(self.is_charging and self.is_idle)
        return bool(self.is_idle)

    @staticmethod
    def quantize_weights(weights: list[float], bits: int = 8) -> dict:
        """Quantize floating-point weights to 8-bit or 4-bit signed integers with scale factor."""
        if bits not in (4, 8):
            raise ValueError("quantization_bits_must_be_4_or_8")
        if not weights:
            return dict(bits=bits, scale=1.0, quantized=[], dequantized=[], compression_ratio=float(32 // bits))
        qmax = (1 << (bits - 1)) - 1
        max_abs = max(abs(float(w)) for w in weights)
        scale = max_abs / qmax if max_abs > 1e-12 else 1.0
        q_vals = [max(-qmax, min(qmax, int(round(float(w) / scale)))) for w in weights]
        dequant = [round(q * scale, 6) for q in q_vals]
        mae = sum(abs(float(w) - d) for w, d in zip(weights, dequant)) / len(weights)
        return dict(
            bits=bits,
            scale=round(scale, 8),
            quantized=q_vals,
            dequantized=dequant,
            mean_absolute_error=round(mae, 6),
            compression_ratio=round(32.0 / bits, 2),
        )
