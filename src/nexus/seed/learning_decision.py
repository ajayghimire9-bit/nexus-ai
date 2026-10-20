"""Auditable learn/ask/retain advisory; no hidden assessments or mutation.

Known-anchor damage is an observed-memory proxy, not a guarantee about every
old task. Error scale is a training residual scale, not a calibrated confidence
interval. Asking requests a label; it does not invent an answer.
"""
from dataclasses import asdict,dataclass
from .grounded_audit import finite


@dataclass(frozen=True)
class LearningDecision:
    action: str
    reason: str
    predicted_gain: float
    error_scale: float
    known_damage: float
    damage_cap: float
    remaining_examples: int

    def payload(self):
        row=asdict(self)
        row['question']=('Please give another labeled example of this task before I change the learned correction.'
                         if self.action=='ask' else None)
        return row


def decide(*,predicted_gain,error_scale,known_damage,damage_cap,remaining_examples):
    """Only revealed support/anchor evidence and remaining label budget allowed."""
    if (any(not finite(x) for x in (predicted_gain,error_scale,known_damage,damage_cap)) or
        error_scale<0 or damage_cap<0 or type(remaining_examples) is not int or remaining_examples<0):
        raise ValueError('finite_learning_evidence_and_budget_required')
    if known_damage>damage_cap:
        action='ask' if remaining_examples else 'retain';reason='known_memory_risk'
    elif predicted_gain>error_scale:
        action='learn';reason='predicted_benefit'
    elif predicted_gain < -error_scale:
        action='retain';reason='predicted_harm'
    else:
        action='ask' if remaining_examples else 'retain';reason='uncertain_benefit'
    return LearningDecision(action,reason,float(predicted_gain),float(error_scale),float(known_damage),float(damage_cap),remaining_examples)
