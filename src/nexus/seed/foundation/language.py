"""Compact source-count surface decoder over evidence-grounded answer records.

This is a learned categorical wording model, not unrestricted language modeling.
Only vetted slot-preserving surfaces compete. Facts always come from the answer
record. Source feedback changes wording probabilities, never factual content.
"""
from collections import Counter
import math

SURFACES=(
    'Decision: {decision}. Reason: {reason}. Uncertainty: {uncertainty}. Evidence: {evidence}.',
    'I suggest {decision} because {reason}. Uncertainty: {uncertainty}. Sources: {evidence}.',
)


def render(record, traces, known_refs):
    if type(record) is not dict or set(record)!={'intent','decision','reason','evidence','uncertainty'}: raise ValueError('grounded_answer_record')
    if any(type(record[k]) is not str or not 1<=len(record[k])<=256 for k in ('intent','decision','reason')): raise ValueError('answer_text')
    if type(record['uncertainty']) not in (int,float) or not math.isfinite(record['uncertainty']) or not 0<=record['uncertainty']<=1: raise ValueError('answer_uncertainty')
    if type(record['evidence']) is not list or not 1<=len(record['evidence'])<=8 or any(r not in known_refs for r in record['evidence']): raise ValueError('known_answer_evidence_required')
    if len(traces)>128: raise ValueError('language_trace_cap')
    counts=Counter()
    for t in traces:
        if set(t)!={'role','intent','surface'} or t['role']!='source' or type(t['surface']) is not int or t['surface'] not in range(len(SURFACES)): raise ValueError('source_language_trace')
        if t['intent']==record['intent']: counts[t['surface']]+=1
    probabilities=[(counts[i]+1)/(sum(counts.values())+len(SURFACES)) for i in range(len(SURFACES))]
    index=max(range(len(SURFACES)),key=lambda i:(probabilities[i],-i))
    slots=dict(record,evidence=', '.join(record['evidence']))
    return dict(text=SURFACES[index].format(**slots),surface=index,probabilities=probabilities,
                evidence=list(record['evidence']),model='source_count_surface_decoder',
                factual_status='attributed_record_not_independent_verification')
