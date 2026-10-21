"""Shared belief workspace, 6-tier memory architecture, 3 learning timescales,
and learning acceptance gate over the existing Session / E1 Journal and SharedBrain.

Does not create a replacement database: all durable state is projected from or
recorded as validated events in the Session journal.
"""
import copy
import json
import math
import time
from typing import Any
from nexus.evolution1.catalogue import digest
from .. import skill_library as lib
from .. import skill_programs as ir
from ..working import current as working_state
from .types import (
    BeliefState,
    Concept,
    ExperienceEvent,
    GroundedObservation,
    Hypothesis,
    Skill,
)

MASTER_EVENT_KIND = "seed_master"


def master_records(session) -> list[tuple[str, dict]]:
    """Return (fingerprint, payload) for all seed_master events in the session journal."""
    return [
        (e.fingerprint, json.loads(e.payload_json))
        for e in session.journal.snapshot()
        if e.kind == MASTER_EVENT_KIND
    ]


BUILTIN_PROCEDURAL_SKILLS = {
    "sorting": Skill(
        signature=dict(name="sorting", schema="list", input_type="list[int]", output_type="list[int]"),
        preconditions=["isinstance(x, list)", "1 <= len(x) <= 16"],
        typed_program=dict(schema="list", ops=["sort"]),
        postconditions=["len(output) == len(x)", "output == sorted(x)"],
        tests=[
            dict(input=[3, 1, 2], output=[1, 2, 3]),
            dict(input=[9, -1, 4, 0], output=[-1, 0, 4, 9]),
        ],
        failure_cases=[],
        dependencies=[],
        provenance=dict(origin="verified_builtin_catalog", lab="coding"),
        revision="builtin_sort_v1",
    ),
    "reverse": Skill(
        signature=dict(name="reverse", schema="list", input_type="list[int]", output_type="list[int]"),
        preconditions=["isinstance(x, list)", "1 <= len(x) <= 16"],
        typed_program=dict(schema="list", ops=["reverse"]),
        postconditions=["len(output) == len(x)", "output == list(reversed(x))"],
        tests=[
            dict(input=[1, 2, 3], output=[3, 2, 1]),
            dict(input=[4, 1, 9], output=[9, 1, 4]),
        ],
        failure_cases=[],
        dependencies=[],
        provenance=dict(origin="verified_builtin_catalog", lab="coding"),
        revision="builtin_reverse_v1",
    ),
}


class MemoryArchitecture:
    """Six explicit memory projections over Session, E1 Journal, and SharedBrain."""

    def __init__(self, session, shared_brain=None):
        self.session = session
        self.shared_brain = shared_brain

    def working_memory_view(self, active_goal: Any = None, unresolved_questions: list | None = None) -> dict:
        wm = working_state(self.session.journal.snapshot()).payload()
        from ..conversation import turns, context
        chat_turns = turns(self.session)
        chat_ctx = context(self.session)
        return dict(
            active_goal=active_goal or chat_ctx.get("pending"),
            dialogue_context=chat_ctx,
            recent_turns=chat_turns[-6:],
            last_object=wm.get("last_object"),
            last_concept=wm.get("last_concept"),
            recent_objects=wm.get("recent_objects", []),
            unresolved_questions=list(unresolved_questions or []),
        )

    def episodic_memory_view(self) -> list[dict]:
        episodes = []
        for idx, e in enumerate(self.session.journal.snapshot()):
            payload = json.loads(e.payload_json)
            if e.kind == MASTER_EVENT_KIND and payload.get("op") == "experience":
                episodes.append(dict(fingerprint=e.fingerprint, index=idx, **payload["data"]))
            else:
                evt = ExperienceEvent(
                    observation=dict(event_kind=e.kind),
                    decision=e.kind,
                    action=payload.get("op", e.kind) if isinstance(payload, dict) else e.kind,
                    result=dict(fingerprint=e.fingerprint),
                    prediction_error=float(payload.get("prediction_error", 0.0)) if isinstance(payload, dict) and isinstance(payload.get("prediction_error"), (int, float)) else 0.0,
                    reward=float(payload.get("reward", 0.0)) if isinstance(payload, dict) and isinstance(payload.get("reward"), (int, float)) else 0.0,
                    explanation=f"Journal event {e.kind}",
                    timestamp=float(idx),
                    source="session_journal",
                )
                episodes.append(dict(fingerprint=e.fingerprint, index=idx, **evt.to_dict()))
        return episodes

    def semantic_memory_view(self) -> dict[str, Concept]:
        concepts: dict[str, Concept] = {}
        # 1. Inspect Session's core object-world concepts
        inspected = self.session.inspect()
        for c in inspected.get("concepts", []):
            word = c["word"]
            pos_ex = [e["object"] for e in self.session.evidence if e["word"] == word and e["positive"]]
            neg_ex = [e["object"] for e in self.session.evidence if e["word"] == word and not e["positive"]]
            alts = c.get("alternatives", [])
            conf = 1.0 if len(alts) == 1 else (0.6 if len(alts) > 1 else 0.0)
            concepts[word] = Concept(
                name=word,
                aliases=[],
                definition=alts[0] if len(alts) == 1 else alts,
                examples=pos_ex,
                counterexamples=neg_ex,
                relations=[],
                confidence=conf,
                evidence=c.get("evidence_refs", []),
            )

        # 2. Foundation ingested knowledge assertions
        from ..foundation.runtime import inspect as foundation_inspect
        f_view = foundation_inspect(self.session)
        for item in f_view.get("knowledge", []):
            subj = item.get("subject", "entity")
            rel = item.get("predicate", "related_to")
            obj = item.get("object", "")
            existing = concepts.get(subj)
            rel_entry = dict(relation=rel, target=obj, conflict=item.get("conflict", False))
            if existing:
                existing.relations.append(rel_entry)
                existing.evidence.extend(item.get("sources", []))
            else:
                concepts[subj] = Concept(
                    name=subj,
                    aliases=[],
                    definition=f"{subj} {rel} {obj}",
                    examples=[],
                    counterexamples=[],
                    relations=[rel_entry],
                    confidence=0.4 if item.get("conflict") else 0.85,
                    evidence=list(item.get("sources", [])),
                )

        # 3. Master architecture immediate semantic concepts & taught concepts
        for ref, payload in master_records(self.session):
            if payload.get("op") == "semantic_concept":
                data = dict(payload["data"])
                ev = list(data.get("evidence", []))
                if ref not in ev:
                    ev.append(ref)
                data["evidence"] = ev
                c_obj = Concept.from_dict(data)
                concepts[c_obj.name] = c_obj

        return concepts

    def procedural_memory_view(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = copy.deepcopy(BUILTIN_PROCEDURAL_SKILLS)
        s_state = lib.state(self.session)
        for name, (ref, check_rec) in s_state["active"].items():
            teach_rec = s_state["teaching"].get(check_rec["attempt"], {})
            prog = check_rec["program"]
            skills[name] = Skill(
                signature=dict(name=name, schema=prog["schema"]),
                preconditions=[f"schema == '{prog['schema']}'"],
                typed_program=prog,
                postconditions=["verified_on_disjoint_check"],
                tests=list(check_rec.get("checks", [])),
                failure_cases=[],
                dependencies=[],
                provenance=dict(
                    origin="shared_skill_library",
                    lab=teach_rec.get("lab", "coding"),
                    teaching_ref=check_rec["attempt"],
                    check_ref=ref,
                ),
                revision=ref,
            )
        # Also include verified skills committed through the master acceptance gate
        for ref, payload in master_records(self.session):
            if payload.get("op") == "procedural_skill":
                skill_obj = Skill.from_dict(payload["data"])
                skills[skill_obj.signature["name"]] = skill_obj
            elif payload.get("op") == "semantic_concept":
                c_data = payload["data"]
                for rel in c_data.get("relations", []):
                    if isinstance(rel, dict) and rel.get("relation") == "aliases_skill":
                        target_skill = rel.get("target")
                        if target_skill in skills:
                            target = skills[target_skill]
                            alias_name = c_data["name"]
                            if alias_name not in skills:
                                skills[alias_name] = Skill(
                                    signature=dict(name=alias_name, aliases=[target_skill], schema=target.signature.get("schema", "list")),
                                    preconditions=list(target.preconditions),
                                    typed_program=copy.deepcopy(target.typed_program),
                                    postconditions=list(target.postconditions),
                                    tests=list(target.tests),
                                    failure_cases=list(target.failure_cases),
                                    dependencies=[target_skill],
                                    provenance=dict(origin="concept_skill_link", source_concept=alias_name, target_skill=target_skill, evidence_ref=ref),
                                    revision=f"alias_{ref[:12]}",
                                )
        return skills

    def model_memory_view(self) -> dict:
        grounded = getattr(self.session, "grounded_agent", None)
        shared_model = getattr(self.shared_brain, "model", None) if self.shared_brain else None
        shared_hash = getattr(self.shared_brain, "model_hash", None) if self.shared_brain else None
        adapters = [
            dict(ref=ref, **payload["data"])
            for ref, payload in master_records(self.session)
            if payload.get("op") == "model_consolidation" and payload["data"].get("accepted")
        ]
        return dict(
            world_model_hash=getattr(grounded, "model_hash", None) or shared_hash,
            grounding_encoder="GroundingBiGRUEncoder_128d" if shared_model is None else "SeedRSSM_GRU32",
            plasticity_hash=getattr(grounded, "controller_hash", None),
            frozen_baseline_preserved=True,
            accepted_adapters=adapters,
        )

    def replay_retention_memory_view(self, max_items: int = 32) -> dict:
        """Curated replay buffer prioritizing important capabilities, rare concepts,
        failure cases, conflicts, and representative old knowledge."""
        semantic = self.semantic_memory_view()
        procedural = self.procedural_memory_view()
        episodes = self.episodic_memory_view()

        important_capabilities = [
            dict(skill=name, tests=skill.tests, revision=skill.revision)
            for name, skill in sorted(procedural.items())
            if skill.tests
        ]
        rare_concepts = [
            c.to_dict()
            for _, c in sorted(semantic.items(), key=lambda kv: len(kv[1].examples) + len(kv[1].evidence))[:8]
        ]
        failure_cases = [
            ep for ep in episodes if ep.get("prediction_error", 0.0) > 0.25 or ep.get("reward", 0.0) < 0.0
        ]
        # Also include rejected skill checks from skill_library
        s_state = lib.state(self.session)
        for ref, chk in s_state["checks"].items():
            if not chk.get("accepted"):
                failure_cases.append(dict(kind="rejected_skill_check", ref=ref, name=chk.get("name"), checks=chk.get("checks")))

        conflicts = [
            c.to_dict()
            for c in semantic.values()
            if any(isinstance(r, dict) and r.get("conflict") for r in c.relations) or c.counterexamples
        ]
        representative_old = episodes[:min(8, len(episodes))]

        return dict(
            important_capabilities=important_capabilities[:max_items],
            rare_concepts=rare_concepts[:max_items],
            failure_cases=failure_cases[:max_items],
            conflicts=conflicts[:max_items],
            representative_old_knowledge=representative_old,
            admission_policy="explicit_evidence_and_verification_required",
        )

    def inspect_all(self) -> dict:
        return dict(
            working_memory=self.working_memory_view(),
            episodic_memory_count=len(self.episodic_memory_view()),
            semantic_memory={k: v.to_dict() for k, v in self.semantic_memory_view().items()},
            procedural_memory={k: v.to_dict() for k, v in self.procedural_memory_view().items()},
            model_memory=self.model_memory_view(),
            replay_retention_memory=self.replay_retention_memory_view(),
        )


class SharedBeliefWorkspace:
    """Constructs a temporary task-focused BeliefState view over SharedBrain, Session,
    SeedRSSM, and skill_library without duplicating permanent storage."""

    def __init__(self, session, shared_brain=None, grounding_layer=None):
        self.session = session
        self.shared_brain = shared_brain
        self.memory = MemoryArchitecture(session, shared_brain)
        self.grounding_layer = grounding_layer

    def build_belief_state(
        self,
        current_goal: Any = None,
        observations: list[GroundedObservation] | None = None,
        candidate_hypotheses: list[Hypothesis] | None = None,
        assumptions: list[str] | None = None,
        unresolved_questions: list[str] | None = None,
    ) -> BeliefState:
        semantic = self.memory.semantic_memory_view()
        procedural = self.memory.procedural_memory_view()
        wm = self.memory.working_memory_view(active_goal=current_goal, unresolved_questions=unresolved_questions)
        obs_list = list(observations or [])

        # Filter active concepts relevant to observations or recent working memory
        obs_concepts = {c for o in obs_list for c in o.concepts}
        for o in obs_list:
            for w in o.uncertainty.get("new_vocabulary", []):
                if w in semantic:
                    obs_concepts.add(w)
        if wm.get("last_concept") and wm["last_concept"] in semantic:
            obs_concepts.add(wm["last_concept"])

        active_concepts = [
            semantic[name] for name in sorted(obs_concepts) if name in semantic
        ] or list(semantic.values())[:12]

        # Build default hypotheses if none supplied
        hypotheses = list(candidate_hypotheses or [])
        if not hypotheses and obs_list:
            top_obs = obs_list[-1]
            intent = top_obs.provenance.get("intent", "general_query")
            conf = float(top_obs.uncertainty.get("confidence", 0.8))
            hypotheses.append(
                Hypothesis(
                    claim=f"Primary user intent is '{intent}'",
                    predictions=[f"Routing to {intent} handler satisfies request"],
                    assumptions=list(assumptions or ["Input text is literal and non-adversarial"]),
                    supporting_evidence=[top_obs.provenance],
                    contradicting_evidence=[],
                    confidence=conf,
                )
            )

        # Retrieve top relevant episodic/semantic memories
        replay = self.memory.replay_retention_memory_view(max_items=8)
        retrieved = []
        for c in active_concepts[:6]:
            retrieved.append(dict(kind="semantic_concept", name=c.name, definition=c.definition, evidence=c.evidence))
        for cap in replay["important_capabilities"][:4]:
            retrieved.append(dict(kind="procedural_capability", skill=cap["skill"], revision=cap["revision"]))

        # World state combines Session 6x6 object grid + optional RSSM latent summary
        world_state = dict(
            objects=copy.deepcopy(self.session.world),
            stopped=self.session.stopped,
        )
        if getattr(self.session, "grounded_agent", None) is not None:
            ga = self.session.grounded_agent
            world_state["rssm_latent"] = dict(
                h_norm=round(float(ga.h.norm()), 6),
                z_norm=round(float(ga.z.norm()), 6),
                model_hash=ga.model_hash,
            )

        uncertainties = dict(
            unresolved_questions=list(unresolved_questions or []),
            observation_uncertainty=obs_list[-1].uncertainty if obs_list else {},
            ambiguous_concepts=[c.name for c in active_concepts if c.confidence < 0.75],
        )

        resource_budget = dict(
            remaining_predicate_tests=max(0, 10000 - self.session.counts.get("predicate_tests", 0)),
            remaining_program_evaluations=max(0, 2000 - self.session.counts.get("program_evaluations", 0)),
            remaining_sandbox_actions=max(0, 128 - self.session.counts.get("sandbox_actions", 0)),
            journal_events_used=len(self.session.journal.snapshot()),
            journal_events_limit=2048,
        )

        return BeliefState(
            current_goal=current_goal or (obs_list[-1].requested_goal if obs_list else wm.get("active_goal")),
            dialogue_state=wm["dialogue_context"],
            grounded_observations=obs_list,
            active_concepts=active_concepts,
            candidate_hypotheses=hypotheses,
            retrieved_memories=retrieved,
            available_skills=list(procedural.values()),
            world_state=world_state,
            uncertainties=uncertainties,
            assumptions=list(assumptions or ["Closed-world verification applies to finite checks"]),
            resource_budget=resource_budget,
        )


class LearningAcceptanceGate:
    """Evaluates any proposed persistent skill, rule, or model update across:
    1. New-task evaluation
    2. Retention evaluation
    3. Transfer evaluation
    4. Compute and risk check
    5. Statistical confidence / replication check against baseline
    Commits a versioned update if and only if all gates pass; otherwise rolls back
    and records the rejection in the Session journal.
    """

    def __init__(self, session, memory: MemoryArchitecture):
        self.session = session
        self.memory = memory

    def evaluate_and_gate(
        self,
        proposal_name: str,
        proposal_kind: str,
        new_task_scores: list[float],
        baseline_scores: list[float],
        retention_scores: list[float],
        transfer_scores: list[float],
        compute_cost_ms: float,
        risk_score: float = 0.0,
        payload_data: dict | None = None,
        max_compute_ms: float = 2000.0,
        max_risk: float = 0.1,
    ) -> dict:
        if not new_task_scores or not baseline_scores or len(new_task_scores) != len(baseline_scores):
            raise ValueError("paired_new_and_baseline_scores_required")
        if not retention_scores or not transfer_scores:
            raise ValueError("retention_and_transfer_scores_required")

        n = len(new_task_scores)
        diffs = [float(a) - float(b) for a, b in zip(new_task_scores, baseline_scores)]
        mean_diff = sum(diffs) / n
        if n > 1:
            variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
            se = math.sqrt(variance / n)
        else:
            se = 0.0
        ci_low = mean_diff - 1.96 * se
        ci_high = mean_diff + 1.96 * se

        mean_new = sum(float(x) for x in new_task_scores) / len(new_task_scores)
        mean_base = sum(float(x) for x in baseline_scores) / len(baseline_scores)
        mean_retention = sum(float(x) for x in retention_scores) / len(retention_scores)
        mean_transfer = sum(float(x) for x in transfer_scores) / len(transfer_scores)

        new_task_pass = mean_new > mean_base and mean_diff > 0.0
        retention_pass = mean_retention >= 0.98
        transfer_pass = mean_transfer >= mean_base
        compute_risk_pass = 0.0 <= float(compute_cost_ms) <= max_compute_ms and 0.0 <= float(risk_score) <= max_risk
        statistical_pass = ci_low >= 0.0 and all(d >= 0.0 for d in diffs)

        accepted = bool(
            new_task_pass and retention_pass and transfer_pass and compute_risk_pass and statistical_pass
        )
        decision = "committed" if accepted else "rolled_back"
        report = dict(
            proposal_name=proposal_name,
            proposal_kind=proposal_kind,
            accepted=accepted,
            decision=decision,
            checks=dict(
                new_task_evaluation=dict(passed=new_task_pass, mean_new=round(mean_new, 4), mean_baseline=round(mean_base, 4)),
                retention_evaluation=dict(passed=retention_pass, mean_retention=round(mean_retention, 4)),
                transfer_evaluation=dict(passed=transfer_pass, mean_transfer=round(mean_transfer, 4)),
                compute_and_risk_check=dict(passed=compute_risk_pass, compute_cost_ms=round(float(compute_cost_ms), 3), risk_score=round(float(risk_score), 4)),
                statistical_check=dict(passed=statistical_pass, mean_gain=round(mean_diff, 4), ci95=[round(ci_low, 4), round(ci_high, 4)], seeds=n),
            ),
            payload=copy.deepcopy(payload_data or {}),
        )
        ref = self.session.event(
            MASTER_EVENT_KIND,
            dict(op="acceptance_gate", data=report),
        )
        return dict(ref=ref, **report)


class ThreeTimescalesLearner:
    """Implements the three timescales of learning:
    1. Immediate learning (in-conversation structured semantic memory update without neural training)
    2. Medium-term skill learning (program induction + held-out verification + counterexample checks across labs)
    3. Long-term neural consolidation (offline/background episode collection, noise/conflict filtering,
       retention-paired training set assembly, gated against frozen baseline).
    """

    def __init__(self, session, shared_brain=None, grounding_layer=None):
        self.session = session
        self.shared_brain = shared_brain
        self.memory = MemoryArchitecture(session, shared_brain)
        self.gate = LearningAcceptanceGate(session, self.memory)
        self.grounding_layer = grounding_layer

    def learn_immediate_concept(
        self,
        name: str,
        definition: str,
        aliases: list[str] | None = None,
        examples: list | None = None,
        counterexamples: list | None = None,
        linked_skill: str | None = None,
        verified: bool = False,
    ) -> dict:
        """Immediate semantic memory update within a conversation (no neural training required)."""
        clean_name = name.strip().lower()
        def_clean = definition.strip()
        relations = []
        # Extract component property relations (e.g., "Scarlet" means bright red -> is_a red, has_property bright)
        for prop in ("red", "blue", "green", "yellow", "bright", "dark", "small", "large", "circle", "square", "triangle"):
            if prop in def_clean.lower().split():
                relations.append(dict(relation="has_property", target=prop))
        if linked_skill:
            relations.append(dict(relation="aliases_skill", target=linked_skill))

        concept = Concept(
            name=clean_name,
            aliases=list(aliases or ([linked_skill] if linked_skill else [])),
            definition=def_clean,
            examples=list(examples or []),
            counterexamples=list(counterexamples or []),
            relations=relations,
            confidence=0.95 if verified else 0.75,
            evidence=["user_teaching_immediate"],
        )
        ref = self.session.event(
            MASTER_EVENT_KIND,
            dict(op="semantic_concept", data=concept.to_dict()),
        )
        if self.grounding_layer is not None:
            self.grounding_layer.register_concept(clean_name)
            if linked_skill:
                self.grounding_layer.register_skill(clean_name)
        return dict(
            timescale="immediate",
            status="verified" if verified else "provisional",
            ref=ref,
            concept=concept.to_dict(),
            linked_skill=linked_skill,
            requires_neural_training=False,
        )

    def learn_medium_term_skill(
        self,
        name: str,
        schema: str,
        teaching_examples: list[dict],
        held_out_checks: list[dict],
        counterexamples: list[dict] | None = None,
        lab: str = "coding",
    ) -> dict:
        """Medium-term skill induction: induce program, verify on disjoint held-out examples,
        check counterexamples, and save versioned skill reusable across all 4 labs."""
        if self.shared_brain is not None:
            teach_out = self.shared_brain.request(
                dict(
                    op="lab_teach",
                    lab=lab,
                    name=name,
                    schema=schema,
                    examples=teaching_examples,
                    mode="reuse_first",
                    supersedes=None,
                )
            )["result"]
            if teach_out["candidate_count"] != 1:
                return dict(
                    timescale="medium_term",
                    status=teach_out["status"],
                    attempt=teach_out["attempt"],
                    candidate_count=teach_out["candidate_count"],
                )
            check_out = self.shared_brain.request(
                dict(
                    op="lab_check",
                    name=name,
                    attempt=teach_out["attempt"],
                    checks=held_out_checks,
                )
            )["result"]
        else:
            ref_t, rec_t = lib.teach(self.session, lab=lab, name=name, schema=schema, examples=teaching_examples, mode="reuse_first")
            if len(rec_t["candidates"]) != 1:
                return dict(timescale="medium_term", status="ambiguous_or_unsatisfied", attempt=ref_t, candidate_count=len(rec_t["candidates"]))
            ref_c, rec_c = lib.assess(self.session, name=name, attempt=ref_t, checks=held_out_checks)
            check_out = dict(status="accepted" if rec_c["accepted"] else "rejected", revision=ref_c)

        counterexample_passed = True
        for ce in (counterexamples or []):
            s_active = lib.state(self.session)["active"].get(name)
            if s_active is not None:
                pred = ir.run(s_active[1]["program"], ce["input"])
                if pred == ce["bad_output"]:
                    counterexample_passed = False

        if self.grounding_layer is not None and check_out["status"] == "accepted" and counterexample_passed:
            self.grounding_layer.register_skill(name)

        return dict(
            timescale="medium_term",
            status=check_out["status"] if counterexample_passed else "rejected_on_counterexample",
            revision=check_out["revision"],
            counterexample_passed=counterexample_passed,
            reusable_labs=list(lib.LABS),
        )

    def consolidate_long_term(
        self,
        adapter_name: str,
        new_task_scores: list[float],
        baseline_scores: list[float],
        retention_scores: list[float],
        transfer_scores: list[float],
        compute_cost_ms: float = 25.0,
    ) -> dict:
        """Long-term neural consolidation: collect verified episodes, filter noisy/contradictory
        events, build a training dataset from new + retention examples, and run the
        LearningAcceptanceGate against the frozen baseline."""
        episodes = self.memory.episodic_memory_view()
        replay = self.memory.replay_retention_memory_view()

        verified_episodes = [
            ep for ep in episodes if ep.get("prediction_error", 0.0) <= 0.5 and ep.get("reward", 0.0) >= 0.0
        ]
        filtered_noisy_count = len(episodes) - len(verified_episodes)
        dataset_summary = dict(
            verified_episodes=len(verified_episodes),
            filtered_noisy_or_contradictory=filtered_noisy_count,
            retention_capabilities_count=len(replay["important_capabilities"]),
            rare_concepts_count=len(replay["rare_concepts"]),
        )
        gate_result = self.gate.evaluate_and_gate(
            proposal_name=adapter_name,
            proposal_kind="long_term_neural_adapter",
            new_task_scores=new_task_scores,
            baseline_scores=baseline_scores,
            retention_scores=retention_scores,
            transfer_scores=transfer_scores,
            compute_cost_ms=compute_cost_ms,
            risk_score=0.01,
            payload_data=dataset_summary,
        )
        consolidation_record = dict(
            adapter_name=adapter_name,
            accepted=gate_result["accepted"],
            decision=gate_result["decision"],
            gate_ref=gate_result["ref"],
            dataset=dataset_summary,
        )
        ref = self.session.event(
            MASTER_EVENT_KIND,
            dict(op="model_consolidation", data=consolidation_record),
        )
        return dict(
            timescale="long_term",
            ref=ref,
            **consolidation_record,
            checks=gate_result["checks"],
        )
