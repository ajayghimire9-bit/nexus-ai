"""Fixed-scale investigation gate and one-use candidate assessment, no fitting.

Callers provide actual-feedback receipts. The gate has no model edit authority.
One candidate batch per fresh assessment set; final-audit rows are prohibited.
"""
import math
from nexus.evolution1.catalogue import digest


def finite(x):
    if type(x) not in (float,int) or not math.isfinite(x):raise ValueError('finite_numeric_required')
    return float(x)


def promotion_gain(*,keep_loss,candidate_loss,forgetting,cost,margin=.01,retention_cap=.01,lambda_f=1.,mu_c=.0001):
    vals=[finite(v) for v in (keep_loss,candidate_loss,forgetting,cost,margin,retention_cap,lambda_f,mu_c)]
    if any(v<0 for v in vals):raise ValueError('nonnegative_assessment')
    gain=keep_loss-candidate_loss-lambda_f*forgetting-mu_c*cost
    return dict(accept=gain>margin and forgetting<=retention_cap,gain=gain,cost=cost)


class SurpriseGate:
    def __init__(self,development_errors,*,development_hash,threshold=3.,epsilon=1e-6):
        errors=[finite(v) for v in development_errors]
        if not errors or len(development_hash)!=64 or finite(threshold)<=0 or finite(epsilon)<=0:raise ValueError('fixed_development_scale_required')
        self.scale=(sum(e*e for e in errors)/len(errors))**.5
        self.threshold=threshold;self.epsilon=epsilon;self.development_hash=development_hash;self.seen=set()

    def observe(self,*,actual_reward,predicted_reward,receipt_id,phase):
        if phase!='actual_experience' or type(receipt_id) is not str or receipt_id in self.seen:raise ValueError('unique_actual_feedback_only')
        error=abs(finite(actual_reward)-finite(predicted_reward));self.seen.add(receipt_id)
        surprise=error/(self.scale+self.epsilon)
        return dict(surprise=surprise,investigate=surprise>self.threshold,modified=False,development_hash=self.development_hash,scale=self.scale,threshold=self.threshold,epsilon=self.epsilon,actual_reward=float(actual_reward),predicted_reward=float(predicted_reward))


class AssessmentLedger:
    """One-use development leases. Reserve before opening candidate outcomes."""
    def __init__(self):self.used=set();self.pending={}

    def reserve(self,ids,*,phase):
        if phase!='fresh_development' or not ids or len(ids)!=len(set(ids)) or any(type(i) is not str or i in self.used for i in ids):raise ValueError('fresh_assessment_only')
        self.used.update(ids);token=digest(list(ids));self.pending[token]=tuple(ids);return token

    def assess(self,token,*,keep_loss,candidate_loss,forgetting,cost,margin=.01,retention_cap=.01,lambda_f=1.,mu_c=.0001):
        if token not in self.pending:raise ValueError('one_use_assessment_required')
        self.pending.pop(token)
        return dict(promotion_gain(keep_loss=keep_loss,candidate_loss=candidate_loss,forgetting=forgetting,cost=cost,margin=margin,retention_cap=retention_cap,lambda_f=lambda_f,mu_c=mu_c),assessment=token)


def load_calibration(path,sha,parent):
    import hashlib,json
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('calibration_file_hash')
    r=json.loads(raw);rows=r['development'];cal=r['surprise_calibration']
    dh=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    if r['declared_complete'] is not True or not r['frozen_core'] or not r['frozen_bank'] or r['config']['parent_sha256']!=parent or dh!=cal['development_hash'] or cal['predictor']!=parent:raise ValueError('calibration_provenance')
    errors=[a-b for row in rows for a,b in zip(row['actual'],row['base'])]
    gate=SurpriseGate(errors,development_hash=dh,threshold=cal['threshold'])
    if abs(gate.scale-cal['scale'])>1e-6:raise ValueError('calibration_scale')
    return gate
