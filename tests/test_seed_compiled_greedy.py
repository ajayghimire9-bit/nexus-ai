"""Constructed table fixtures. No registered experiment or collector runs."""
import copy
import inspect
import json
from pathlib import Path
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import compiled_greedy as c, investigation_transfer as b, investigation_hybrid as h


def test_exact_all_laws_and_snapshots():
    policy=c.compile_policy();before=digest(policy)
    for law in range(8):
        compiled=c.adapt(policy,b.LabelOracle(b.TABLE[law],8).reveal)
        online=h.adapt('greedy',{},b.LabelOracle(b.TABLE[law],8).reveal)
        assert c.decision(compiled)==c.decision(online)
        assert compiled['costs']['hypothesis_predictions']==sum(len(x['posterior_before']) for x in compiled['steps'])
        assert compiled['costs']['tree_nodes']==len(compiled['steps'])
    assert digest(policy)==before


def test_construction_meter_independent():
    p=c.compile_policy();reads=partitions=candidates=0
    for k,node in p['nodes'].items():
        ids,available=k.split('|');ids=ids.split(',');available=available.split(',')
        if node['question'] is None:continue
        reads+=len(ids)*len(available);partitions+=len(ids);candidates+=len(available)
    assert p['construction']==dict(score_table_reads=reads,partition_table_reads=partitions,candidate_scores=candidates,nodes=len(p['nodes']))
    assert reads>0 and len(p['nodes'])==15


def test_source_free_and_answer_boundary():
    assert not inspect.signature(c.compile_policy).parameters
    with pytest.raises(TypeError):c.compile_policy({'labels':[True]})
    p=c.compile_policy();initial=None
    # Different future answers cannot affect the first locked choice.
    for law in range(8):
        seen=[]
        def reveal(q):
            seen.append(q)
            return b.TABLE[law][q]
        out=c.adapt(p,reveal)
        initial=out['steps'][0]['question'] if initial is None else initial
        assert seen[0]==initial
        assert seen==[x['question'] for x in out['steps']]
        assert len(seen)==len(set(seen))<=8
    # Assessment data is a scoring-only argument, not an optimizer or selector input.
    d=c.adapt(p,b.LabelOracle(b.TABLE[2],8).reveal)
    a=[dict(bits=list(x),answer=False) for x in b.BITS]
    z=[dict(bits=list(x),answer=True) for x in b.BITS]
    assert c.scored(copy.deepcopy(d),a)['steps']==c.scored(copy.deepcopy(d),z)['steps']


@pytest.fixture
def constructed(monkeypatch):
    from test_seed_investigation_replication import fixture
    parent,_,_=fixture();records=parent['study']['replications'];p=c.compile_policy()
    for x in records:x['resources']['source_fit_wall_s']=.001
    config=c.configuration();blocks=[c.replay_block(s,p) for s in records]
    monkeypatch.setattr(c,'load_parent',lambda root,config:dict(replications=records))
    analysis=c.summarize(blocks,p)
    analysis['screen']='passed' if analysis['exact_decisions_and_predictions'] and analysis['primary_work_reduction']>=config['minimum_work_reduction'] else 'failed'
    study=dict(config=config,declared_complete=True,blocks=blocks,policy=p,policy_hash=digest(p),analysis=analysis,
        frozen_checkpoints_before=b.FROZEN,frozen_checkpoints_after=b.FROZEN,
        compiled_before_saved_answers_loaded=True,build_wall_s=.001,
        serialized_policy_bytes=len(json.dumps(p,sort_keys=True,separators=(',',':')).encode()))
    resources=dict(real_steps=0,updates=0,imagined_transitions=0,network_forwards=0,source_fits=0,
        cached_target_tasks=96,cached_final_observations=3072,assessment_predictions=36864,
        answer_exposures=sum(len(row['methods'][m]['steps']) for x in blocks for row in x['rows'] for m in c.METHODS),cpu_s=.1,worker_wall_s=.1)
    return dict(study=study,resources=resources),config,dict(real_steps=0)


def test_complete_fixture_and_primary_charge(constructed):
    o,config,caps=constructed;c.validate_output(o,config,caps)
    a=o['study']['analysis'];p=o['study']['policy']['construction']
    assert a['means']['compiled_greedy']['construction_work']==3*(p['score_table_reads']+p['partition_table_reads'])
    assert a['means']['compiled_greedy']['source_observations']==0
    assert a['means']['tree_greedy']['source_observations']==768


@pytest.mark.parametrize('damage',['block','task','method','budget','prediction','counter','hash','policy','nan','resource','phase'])
def test_reject_incomplete_or_tampered(constructed,damage):
    o,config,caps=constructed;s=o['study'];row=s['blocks'][0]['rows'][0]
    if damage=='block':s['blocks'].pop()
    elif damage=='task':s['blocks'][0]['rows'].pop()
    elif damage=='method':row['methods'].pop('compiled_greedy')
    elif damage=='budget':row['methods']['compiled_greedy']['metrics'].pop('2')
    elif damage=='prediction':row['methods']['compiled_greedy']['predictions']['2'][0]=.123
    elif damage=='counter':row['methods']['compiled_greedy']['costs']['tree_nodes']+=1
    elif damage=='hash':s['frozen_checkpoints_after']={}
    elif damage=='policy':s['policy']['construction']['nodes']+=1
    elif damage=='nan':s['blocks'][0]['policy_wall_s']['greedy']=float('nan')
    elif damage=='phase':s['compiled_before_saved_answers_loaded']=False
    else:o['resources']['real_steps']=True
    with pytest.raises((ValueError,KeyError)):c.validate_output(o,config,caps)


def test_exact_locked_recipe_and_no_new_execution_calls():
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'configs/seed_compiled_greedy.json').read_text())
    c.config_check(config)
    config['max_wall_s']=31
    with pytest.raises(ValueError):c.config_check(config)
    source=inspect.getsource(c.run)
    assert 'b.run(' not in source and '.learn(' not in source and 'b.encode(' not in source
    assert source.index('compile_policy()')<source.index('load_parent(root,c)')
