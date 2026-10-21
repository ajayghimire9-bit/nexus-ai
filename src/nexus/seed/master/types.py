"""Unified typed knowledge representations for the NEXUS Seed master architecture.

All structures are bounded, deterministically serializable, and explicitly
validate their fields and invariants. None of these types imply achieved AGI
or established learning-to-learn; they provide the structured representations
used by the grounding, belief workspace, memory, reasoning, coding, and
response-generation layers.
"""
from dataclasses import asdict, dataclass, field
import copy
import math
from typing import Any


def _check_prob(value: Any, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"invalid_probability_{name}")
    return float(value)


def _check_nonneg(value: Any, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or float(value) < 0.0:
        raise ValueError(f"invalid_nonneg_{name}")
    return float(value)


def _check_str(value: Any, name: str, max_len: int = 2000, allow_empty: bool = False) -> str:
    if type(value) is not str or len(value) > max_len or (not allow_empty and not value.strip()) or "\x00" in value:
        raise ValueError(f"invalid_string_{name}")
    return value


def _check_list(value: Any, name: str, max_items: int = 256) -> list:
    if type(value) not in (list, tuple) or len(value) > max_items:
        raise ValueError(f"invalid_list_{name}")
    return list(value)


def _check_dict(value: Any, name: str, max_items: int = 256) -> dict:
    if type(value) is not dict or len(value) > max_items:
        raise ValueError(f"invalid_dict_{name}")
    return copy.deepcopy(value)


@dataclass
class GroundedObservation:
    """Typed output produced by every modality encoder in the neural grounding layer."""
    concepts: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    quantities: list = field(default_factory=list)
    requested_goal: Any = None
    uncertainty: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.concepts = _check_list(self.concepts, "concepts")
        self.entities = _check_list(self.entities, "entities")
        self.relations = _check_list(self.relations, "relations")
        self.quantities = _check_list(self.quantities, "quantities")
        self.uncertainty = _check_dict(self.uncertainty, "uncertainty")
        self.provenance = _check_dict(self.provenance, "provenance")
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "GroundedObservation":
        if type(data) is not dict:
            raise ValueError("grounded_observation_dict_required")
        return cls(**data)


@dataclass
class Concept:
    """Unified typed concept representation."""
    name: str
    aliases: list = field(default_factory=list)
    definition: Any = None
    examples: list = field(default_factory=list)
    counterexamples: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    confidence: float = 0.0
    evidence: list = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.name = _check_str(self.name, "concept_name", max_len=128)
        self.aliases = _check_list(self.aliases, "aliases", max_items=64)
        self.examples = _check_list(self.examples, "examples", max_items=128)
        self.counterexamples = _check_list(self.counterexamples, "counterexamples", max_items=128)
        self.relations = _check_list(self.relations, "relations", max_items=128)
        self.confidence = _check_prob(self.confidence, "concept_confidence")
        self.evidence = _check_list(self.evidence, "evidence", max_items=128)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "Concept":
        if type(data) is not dict:
            raise ValueError("concept_dict_required")
        return cls(**data)


@dataclass
class TaskSpec:
    """Unified typed task specification."""
    goal: str
    inputs: Any = field(default_factory=dict)
    expected_outputs: Any = None
    constraints: list = field(default_factory=list)
    success_tests: list = field(default_factory=list)
    permitted_actions: list = field(default_factory=list)
    uncertainty: dict = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.goal = _check_str(self.goal, "task_goal", max_len=1000)
        self.constraints = _check_list(self.constraints, "constraints", max_items=64)
        self.success_tests = _check_list(self.success_tests, "success_tests", max_items=64)
        self.permitted_actions = _check_list(self.permitted_actions, "permitted_actions", max_items=64)
        self.uncertainty = _check_dict(self.uncertainty, "uncertainty", max_items=64)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "TaskSpec":
        if type(data) is not dict:
            raise ValueError("task_spec_dict_required")
        return cls(**data)


@dataclass
class Hypothesis:
    """Unified typed hypothesis representation."""
    claim: str
    predictions: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    supporting_evidence: list = field(default_factory=list)
    contradicting_evidence: list = field(default_factory=list)
    confidence: float = 0.5

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.claim = _check_str(self.claim, "hypothesis_claim", max_len=1000)
        self.predictions = _check_list(self.predictions, "predictions", max_items=64)
        self.assumptions = _check_list(self.assumptions, "assumptions", max_items=64)
        self.supporting_evidence = _check_list(self.supporting_evidence, "supporting_evidence", max_items=128)
        self.contradicting_evidence = _check_list(self.contradicting_evidence, "contradicting_evidence", max_items=128)
        self.confidence = _check_prob(self.confidence, "hypothesis_confidence")
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "Hypothesis":
        if type(data) is not dict:
            raise ValueError("hypothesis_dict_required")
        return cls(**data)


@dataclass
class Skill:
    """Unified typed skill representation."""
    signature: dict
    preconditions: list = field(default_factory=list)
    typed_program: dict = field(default_factory=dict)
    postconditions: list = field(default_factory=list)
    tests: list = field(default_factory=list)
    failure_cases: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    revision: str = "v1"

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.signature = _check_dict(self.signature, "skill_signature", max_items=32)
        if "name" not in self.signature:
            raise ValueError("skill_signature_name_required")
        _check_str(self.signature["name"], "skill_name", max_len=128)
        self.preconditions = _check_list(self.preconditions, "preconditions", max_items=64)
        self.typed_program = _check_dict(self.typed_program, "typed_program", max_items=64)
        self.postconditions = _check_list(self.postconditions, "postconditions", max_items=64)
        self.tests = _check_list(self.tests, "tests", max_items=128)
        self.failure_cases = _check_list(self.failure_cases, "failure_cases", max_items=64)
        self.dependencies = _check_list(self.dependencies, "dependencies", max_items=64)
        self.provenance = _check_dict(self.provenance, "provenance", max_items=64)
        self.revision = _check_str(self.revision, "revision", max_len=128)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        if type(data) is not dict:
            raise ValueError("skill_dict_required")
        return cls(**data)


@dataclass
class ExperienceEvent:
    """Unified typed episodic experience event."""
    observation: Any
    decision: str
    action: Any
    result: Any
    prediction_error: float = 0.0
    reward: float = 0.0
    explanation: str = ""
    timestamp: float = 0.0
    source: str = "session"

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.decision = _check_str(self.decision, "decision", max_len=128)
        self.prediction_error = _check_nonneg(self.prediction_error, "prediction_error")
        if type(self.reward) not in (int, float) or isinstance(self.reward, bool) or not math.isfinite(self.reward):
            raise ValueError("invalid_reward")
        self.reward = float(self.reward)
        self.explanation = _check_str(self.explanation, "explanation", max_len=2000, allow_empty=True)
        self.timestamp = _check_nonneg(self.timestamp, "timestamp")
        self.source = _check_str(self.source, "source", max_len=128)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "ExperienceEvent":
        if type(data) is not dict:
            raise ValueError("experience_event_dict_required")
        return cls(**data)


@dataclass
class ResponsePlan:
    """Unified typed response plan before grounded natural-language rendering."""
    dialogue_act: str
    factual_claims: list = field(default_factory=list)
    supporting_evidence: list = field(default_factory=list)
    execution_results: list = field(default_factory=list)
    uncertainty: dict = field(default_factory=dict)
    requested_clarification: Any = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.dialogue_act = _check_str(self.dialogue_act, "dialogue_act", max_len=128)
        self.factual_claims = _check_list(self.factual_claims, "factual_claims", max_items=64)
        self.supporting_evidence = _check_list(self.supporting_evidence, "supporting_evidence", max_items=128)
        self.execution_results = _check_list(self.execution_results, "execution_results", max_items=64)
        self.uncertainty = _check_dict(self.uncertainty, "uncertainty", max_items=64)
        if self.requested_clarification is not None and type(self.requested_clarification) not in (str, dict):
            raise ValueError("invalid_requested_clarification")
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "ResponsePlan":
        if type(data) is not dict:
            raise ValueError("response_plan_dict_required")
        return cls(**data)


@dataclass
class ReasoningResult:
    """Unified typed output of every reasoner in the reasoning portfolio."""
    conclusion: Any
    proof_or_trace: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    confidence: float = 1.0
    cost: int = 1
    unresolved_questions: list = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.proof_or_trace = _check_list(self.proof_or_trace, "proof_or_trace", max_items=256)
        self.assumptions = _check_list(self.assumptions, "assumptions", max_items=64)
        self.confidence = _check_prob(self.confidence, "reasoning_confidence")
        if type(self.cost) is not int or isinstance(self.cost, bool) or self.cost < 0:
            raise ValueError("invalid_reasoning_cost")
        self.unresolved_questions = _check_list(self.unresolved_questions, "unresolved_questions", max_items=64)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "ReasoningResult":
        if type(data) is not dict:
            raise ValueError("reasoning_result_dict_required")
        return cls(**data)


@dataclass
class DebuggingSkill:
    """Reusable debugging pattern extracted from verified code repairs."""
    symptom: str
    diagnostic_tests: list = field(default_factory=list)
    likely_causes: list = field(default_factory=list)
    repair_pattern: dict = field(default_factory=dict)
    applicability_conditions: list = field(default_factory=list)
    counterexamples: list = field(default_factory=list)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.symptom = _check_str(self.symptom, "symptom", max_len=500)
        self.diagnostic_tests = _check_list(self.diagnostic_tests, "diagnostic_tests", max_items=64)
        self.likely_causes = _check_list(self.likely_causes, "likely_causes", max_items=64)
        self.repair_pattern = _check_dict(self.repair_pattern, "repair_pattern", max_items=64)
        self.applicability_conditions = _check_list(self.applicability_conditions, "applicability_conditions", max_items=64)
        self.counterexamples = _check_list(self.counterexamples, "counterexamples", max_items=64)
        return self

    def to_dict(self) -> dict:
        return copy.deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, data: dict) -> "DebuggingSkill":
        if type(data) is not dict:
            raise ValueError("debugging_skill_dict_required")
        return cls(**data)


@dataclass
class BeliefState:
    """Central task-focused belief workspace view over NEXUS subsystems."""
    current_goal: Any = None
    dialogue_state: dict = field(default_factory=dict)
    grounded_observations: list = field(default_factory=list)
    active_concepts: list = field(default_factory=list)
    candidate_hypotheses: list = field(default_factory=list)
    retrieved_memories: list = field(default_factory=list)
    available_skills: list = field(default_factory=list)
    world_state: Any = field(default_factory=dict)
    uncertainties: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)
    resource_budget: dict = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self):
        self.dialogue_state = _check_dict(self.dialogue_state, "dialogue_state", max_items=128)
        self.grounded_observations = [
            obs if isinstance(obs, GroundedObservation) else GroundedObservation.from_dict(obs)
            for obs in _check_list(self.grounded_observations, "grounded_observations", max_items=64)
        ]
        self.active_concepts = [
            c if isinstance(c, Concept) else Concept.from_dict(c)
            for c in _check_list(self.active_concepts, "active_concepts", max_items=128)
        ]
        self.candidate_hypotheses = [
            h if isinstance(h, Hypothesis) else Hypothesis.from_dict(h)
            for h in _check_list(self.candidate_hypotheses, "candidate_hypotheses", max_items=128)
        ]
        self.retrieved_memories = _check_list(self.retrieved_memories, "retrieved_memories", max_items=128)
        self.available_skills = [
            s if isinstance(s, Skill) else Skill.from_dict(s)
            for s in _check_list(self.available_skills, "available_skills", max_items=128)
        ]
        self.uncertainties = _check_dict(self.uncertainties, "uncertainties", max_items=128)
        self.assumptions = _check_list(self.assumptions, "assumptions", max_items=128)
        self.resource_budget = _check_dict(self.resource_budget, "resource_budget", max_items=64)
        return self

    def to_dict(self) -> dict:
        return dict(
            current_goal=copy.deepcopy(self.current_goal),
            dialogue_state=copy.deepcopy(self.dialogue_state),
            grounded_observations=[o.to_dict() for o in self.grounded_observations],
            active_concepts=[c.to_dict() for c in self.active_concepts],
            candidate_hypotheses=[h.to_dict() for h in self.candidate_hypotheses],
            retrieved_memories=copy.deepcopy(self.retrieved_memories),
            available_skills=[s.to_dict() for s in self.available_skills],
            world_state=copy.deepcopy(self.world_state),
            uncertainties=copy.deepcopy(self.uncertainties),
            assumptions=copy.deepcopy(self.assumptions),
            resource_budget=copy.deepcopy(self.resource_budget),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "BeliefState":
        if type(data) is not dict:
            raise ValueError("belief_state_dict_required")
        return cls(**data)
