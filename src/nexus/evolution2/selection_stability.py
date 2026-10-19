"""Training-only diagnostic over the existing partial-feedback/credit contracts.

Container hashing/span scanning reads bytes, but query outcomes are never JSON
decoded, projected, scored or passed to a learner. No worlds/models constructed.
"""
import hashlib
import itertools
import json
import math
import statistics
from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import StrategyGenerator
from nexus.evolution2.mutation_control import number
from nexus.evolution2 import operator_headroom as panel

KINDS=('switch','rank_blend')
RULES=('mean','recent','conservative')


def span_end(text,start):
    """Locate a JSON value without deserializing its contents."""
    if text[start] not in '{[':
        if text[start]=='"':return json.JSONDecoder().raw_decode(text,start)[1]
        end=start
        while end<len(text) and text[end] not in ',}]':end+=1
        return end
    stack=[];quoted=False;escaped=False
    for i in range(start,len(text)):
        ch=text[i]
        if quoted:
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch=='"':quoted=False
        elif ch=='"':quoted=True
        elif ch in '{[':stack.append(ch)
        elif ch in '}]':
            if not stack or (stack.pop(),ch) not in (('{','}'),('[',']')):raise ValueError('json_container')
            if not stack:return i+1
    raise ValueError('unfinished_json_container')


def whitespace(text,pos):
    while pos<len(text) and text[pos].isspace():pos+=1
    return pos


def members(text,start=0):
    pos=whitespace(text,start)
    if text[pos]!='{':raise ValueError('json_object_required')
    pos=whitespace(text,pos+1);out={}
    while text[pos]!='}':
        key,pos=json.JSONDecoder().raw_decode(text,pos)
        if type(key) is not str or key in out:raise ValueError('unique_json_keys')
        pos=whitespace(text,pos)
        if text[pos]!=':':raise ValueError('json_member_separator')
        begin=whitespace(text,pos+1);end=span_end(text,begin);out[key]=(begin,end);pos=whitespace(text,end)
        if text[pos]=='}':break
        if text[pos]!=',':raise ValueError('json_member_delimiter')
        pos=whitespace(text,pos+1)
    return out


def project_training(text,c):
    """Strict typed scalar projection; skip every non-training row body."""
    top=members(text);start,end=top['rows'];pos=whitespace(text,start+1);rows=[];skipped=0
    while pos<end and text[pos]!=']':
        stop=span_end(text,pos);fields=members(text,pos)
        def value(key):
            a,b=fields[key];return json.loads(text[a:b])
        role=value('role')
        if role=='training':
            paths=value('paths');kind=value('training_operator')
            if kind not in KINDS or set(paths)!={'parent',kind}:raise ValueError('revealed_training_paths_only')
            projected={}
            for key,path in paths.items():
                steps=path['steps']
                if len(steps)!=200 or any(type(s['reward']) not in (int,float) or not math.isfinite(s['reward']) for s in steps):raise ValueError('complete_finite_training_path')
                actual=number(path['return']);cpu=number(path['cpu_s'])
                if cpu<=0 or abs(actual-math.fsum(s['reward'] for s in steps))>1e-8:raise ValueError('training_reward_accounting')
                projected[key]={'return':actual,'cpu_s':cpu,'transition_sha256':digest(steps)}
            row={k:value(k) for k in ('family','bundle','episode','training_operator','protocol')}
            row.update(role='training',paths=projected);rows.append(row)
        elif role=='evaluation':skipped+=1
        else:raise ValueError('known_source_role')
        pos=whitespace(text,stop)
        if text[pos]==']':break
        if text[pos]!=',':raise ValueError('json_array_delimiter')
        pos=whitespace(text,pos+1)
    expected={(f,b,e) for f in c['families'] for b in c['model_bundles'] for e in c['training_episodes']}
    keys=[(r['family'],r['bundle'],r['episode']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected or skipped!=16:raise ValueError('complete_config_training_grid')
    for r in rows:
        if type(r['bundle']) is not int or type(r['episode']) is not int:raise ValueError('typed_training_identity')
        schedule=c['training_schedule'][f'{r["family"]}:{r["bundle"]}']
        if r['training_operator']!=schedule[c['training_episodes'].index(r['episode'])] or r['protocol']['phase']!='training':raise ValueError('registered_training_feedback')
    rows.sort(key=lambda r:(r['family'],r['bundle'],r['episode']))
    return dict(kind='revealed_training_only_projection',rows=rows,training_rows_sha256=digest(rows),
        skipped_query_rows=skipped,query_outcomes_decoded=0,cached_training_interactions=len(rows)*400)


def choices(rows,c):
    parent=statistics.mean(number(r['paths']['parent']['return']) for r in rows)
    raw={};gains={};offset={};counts={}
    for kind in KINDS:
        group=[r for r in rows if r['training_operator']==kind]
        if not group:raise ValueError('both_observed_arms_required')
        raw[kind]=statistics.mean(number(r['paths'][kind]['return']) for r in group)
        gains[kind]=statistics.mean(r['paths'][kind]['return']-r['paths']['parent']['return'] for r in group)
        offset[kind]=statistics.mean(r['paths']['parent']['return'] for r in group)-parent;counts[kind]=len(group)
        if abs(raw[kind]-parent-gains[kind]-offset[kind])>1e-9:raise ValueError('decomposition_identity')
    means={'parent':parent,**raw};best=max(KINDS,key=gains.get)
    selected=dict(raw_parent=max(means,key=means.get),raw_children=max(KINDS,key=raw.get),paired_guard=best if gains[best]>0 else 'parent')
    probabilities={}
    for rule in RULES:
        generator=StrategyGenerator(c['proposal_seed'],mutation_credit=True,mutation_rule=rule)
        for r in sorted(rows,key=lambda r:r['episode']):panel.replay_feedback(generator,r,c,kinds=(r['training_operator'],))
        probs=generator.mutation_probabilities();selected['credit_'+rule]=max(KINDS,key=probs.get);probabilities[rule]=probs
    return dict(choices=selected,training_means=means,paired_advantages=gains,reset_offsets=offset,
        raw_advantages={k:raw[k]-parent for k in KINDS},counts=counts,credit_probabilities=probabilities)


def analyze(projection,c):
    rows=projection['rows'];models=[]
    expected={(f,b,e) for f in c['families'] for b in c['model_bundles'] for e in c['training_episodes']}
    if len(rows)!=len(expected) or {(r['family'],r['bundle'],r['episode']) for r in rows}!=expected or any(r['role']!='training' for r in rows):raise ValueError('training_only_complete_bank')
    for f,b in itertools.product(c['families'],c['model_bundles']):
        train=[r for r in rows if (r['family'],r['bundle'])==(f,b)];full=choices(train,c)
        if full['counts']!={'switch':4,'rank_blend':4}:raise ValueError('balanced_training_evidence')
        cases={}
        cases['leave_one_reset_out']=[dict(omitted=[r['episode']],**choices([x for x in train if x is not r],c)) for r in train]
        groups=[[r for r in train if r['training_operator']==k] for k in KINDS]
        cases['balanced_leave_pair_out']=[dict(omitted=[a['episode'],z['episode']],**choices([r for r in train if r is not a and r is not z],c)) for a,z in itertools.product(*groups)]
        stability={name:{method:sum(v['choices'][method]!=pick for v in values) for method,pick in full['choices'].items()} for name,values in cases.items()}
        parent_values=[r['paths']['parent']['return'] for r in train]
        actual=abs(statistics.mean(r['paths']['parent']['return'] for r in groups[0])-statistics.mean(r['paths']['parent']['return'] for r in groups[1]))
        gaps=[]
        for subset in itertools.combinations(range(8),4):
            gaps.append(abs(statistics.mean(parent_values[i] for i in subset)-statistics.mean(parent_values[i] for i in range(8) if i not in subset)))
        models.append(dict(family=f,bundle=b,full=full,deletions=cases,choice_flip_counts=stability,
            raw_paired_sign_disagreements=[k for k in KINDS if (full['raw_advantages'][k]>0)!=(full['paired_advantages'][k]>0)],
            parent_group_gap=actual,balanced_partition_count=len(gaps),partitions_at_least_as_extreme=sum(v>=actual-1e-10 for v in gaps)))
    return dict(kind='exploratory_training_diagnostic_not_policy_evaluation',models=models,
        limitations='Deletion cases/partitions are dependent diagnostics, not independent model replicates or calibrated significance tests. No query returns, new tasks or selected rule promotion.',
        query_outcomes_used=0,new_environment_interactions=0,new_imagined_transitions=0,neural_inference=0)
