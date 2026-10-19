"""Stdlib-only typed checkpoint validation; loading data grants no neural mode."""
import math
from .core import GRAMMAR,concept_word
from nexus.evolution1.catalogue import digest


def vector(v,n):
    return type(v) is list and len(v)==n and all(type(x) in (int,float) and math.isfinite(x) and abs(x)<1000 for x in v)


def validate_record(kind,p,session):
    if kind in ('seed_grounded_state','seed_grounded_concept'):
        h=p.get('model_hash')
        if type(h) is not str or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('grounded_model_hash')
    if kind=='seed_grounded_state':
        if set(p)!={'model_hash','h','z','context','actual_action','actual_reward','done','flags'} or not vector(p['h'],32) or not vector(p['z'],8) or type(p['actual_action']) is not int or not 0<=p['actual_action']<9 or type(p['done']) is not bool or type(p['actual_reward']) not in (int,float) or not math.isfinite(p['actual_reward']) or type(p['flags']) is not list or len(p['flags'])!=3 or any(type(v) is not int or v not in (0,1) for v in p['flags']):
            raise ValueError('grounded_state_schema')
        c=p['context']
        if type(c) is not dict or set(c)!={'reference','goal','world','done'} or c['world']!=digest(session.world) or c['reference'] not in [o['id'] for o in session.world] or type(c['done']) is not bool or type(c['goal']) is not list or len(c['goal'])!=2 or any(type(x) is not int or not 0<=x<6 for x in c['goal']):raise ValueError('grounded_context_schema')
        obj=next(o for o in session.world if o['id']==c['reference'])
        if c['done']!=p['done'] or p['done']!=([obj['x'],obj['y']]==c['goal']):raise ValueError('grounded_done_consistency')
    elif kind=='seed_grounded_concept':
        if set(p)!={'word','program_index','expression_tree','prototype','validation_error','baseline_error','evidence_hash','model_hash','evidence_refs','development_only'} or not concept_word(p['word']) or type(p['program_index']) is not int or not 0<=p['program_index']<len(GRAMMAR) or not vector(p['prototype'],32) or p['development_only'] is not True:
            raise ValueError('grounded_concept_schema')
        for key in ('validation_error','baseline_error'):
            if type(p[key]) not in (int,float) or not math.isfinite(p[key]) or not 0<=p[key]<=1:raise ValueError('grounded_error_schema')
        if p['validation_error']>=p['baseline_error'] or p['validation_error']>.2:raise ValueError('unverified_concept')
        evidence=[e for e in session.evidence if e['word']==p['word']]
        if p['evidence_hash']!=digest(evidence) or not p['evidence_refs'] or not set(p['evidence_refs'])<={e['ref'] for e in evidence}:raise ValueError('concept_evidence_provenance')
        index=p['program_index'];predicate=GRAMMAR[index]
        val=[e for e in evidence if e['ref'] in p['evidence_refs']]
        error=sum(predicate.matches(e['object'])!=e['positive'] for e in val)/len(val)
        if error!=p['validation_error']:raise ValueError('concept_validation_replay')
        expected=['x'] if len(predicate.literals)==1 else ['binary','add',['x'],['x']]
        if p['expression_tree']!=expected:raise ValueError('concept_expression_schema')
    elif kind=='seed_grounded_information':
        if set(p)!={'label_ref','information_gain','task_reward','mixed_reward'} or p['label_ref'] not in [e['ref'] for e in session.evidence] or type(p['information_gain']) not in (int,float) or not 0<=p['information_gain']<=1 or p['task_reward']!=0. or p['mixed_reward']!=.05*p['information_gain']:raise ValueError('grounded_feedback_schema')
