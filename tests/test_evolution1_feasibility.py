"""Check design arithmetic and preservation only; no scientific stack imports."""
import hashlib
import json
from pathlib import Path
import re

import pytest

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/NEXUS_EVOLUTION1_FEASIBILITY.md'


def worksheet():
    blocks=re.findall(r'```json\n(.*?)\n```',DOC.read_text(),re.S)
    assert len(blocks)==1
    return json.loads(blocks[0])


def validate_counts(d):
    keys=('independent_bundles','training_families','variant_count','proposal_slots_per_family',
          'source_train_steps','source_validation_steps','episode_steps','development_conditions',
          'development_tasks','source_collection_steps','training_matrix_steps',
          'development_evaluation_steps','first_screen_total_steps','imagined_cap_per_decision',
          'first_screen_imagined_upper_bound','future_final_collection_steps',
          'future_final_evaluation_steps','future_retention_steps_upper_bound','full_campaign_steps_upper_bound')
    if any(type(d[k]) is not int or d[k]<=0 for k in keys):raise ValueError('positive integer design counts required')
    n,f,v,h=d['independent_bundles'],d['training_families'],d['variant_count'],d['episode_steps']
    source=n*f*(d['source_train_steps']+d['source_validation_steps'])
    matrix=n*v*f*h
    dev=n*d['development_conditions']*d['development_tasks']*h
    if (source,matrix,dev)!=(d['source_collection_steps'],d['training_matrix_steps'],d['development_evaluation_steps']):
        raise ValueError('source/matrix/development accounting mismatch')
    if source+matrix+dev!=d['first_screen_total_steps']:raise ValueError('first-screen total mismatch')
    if (matrix+dev)*d['imagined_cap_per_decision']!=d['first_screen_imagined_upper_bound']:raise ValueError('imagined bound mismatch')
    total=source+matrix+dev+d['future_final_collection_steps']+d['future_final_evaluation_steps']+d['future_retention_steps_upper_bound']
    if total!=d['full_campaign_steps_upper_bound']:raise ValueError('full-study total mismatch')
    if d['proposal_slots_per_family']>v:raise ValueError('proposal budget exceeds unique catalogue')
    return source,matrix,dev,total


def test_worksheet_counts_source_validation_and_all_control_conditions():
    d=worksheet()
    assert validate_counts(d)==(25600,48000,24000,206400)
    assert d['first_screen_total_steps']<=100000<d['full_campaign_steps_upper_bound']
    assert d['first_screen_imagined_upper_bound']==110592000


@pytest.mark.parametrize('field',['source_validation_steps','development_conditions','episode_steps',
                                  'first_screen_imagined_upper_bound','future_retention_steps_upper_bound'])
def test_missing_cost_or_changed_episode_grid_cannot_preserve_reported_total(field):
    d=worksheet();d[field]+=1
    with pytest.raises(ValueError):validate_counts(d)


@pytest.mark.parametrize('value',[True,'10',-1,0,1.5])
def test_numeric_strings_booleans_and_invalid_counts_rejected(value):
    d=worksheet();d['independent_bundles']=value
    with pytest.raises(ValueError):validate_counts(d)


@pytest.mark.parametrize('actions',[3,5])
@pytest.mark.parametrize('horizon',[4,8,16])
def test_proposed_search_rule_costs_obey_cap_without_padding(actions,horizon):
    cap=worksheet()['imagined_cap_per_decision']
    flat=cap//horizon
    successor=(cap-actions)//(actions*horizon)
    assert flat>0 and successor>0
    assert flat*horizon<=cap<(flat+1)*horizon
    assert actions+actions*successor*horizon<=cap<actions+actions*(successor+1)*horizon
    if actions==5 and horizon==16:assert actions+actions*16*16==1285
    if actions==3 and horizon==16:assert actions+actions*16*16==771


@pytest.mark.parametrize('path,digest',[
    ('AGENTS.md','6ccda31c10dfc40ea8c6f42b085efa9ad45aab0af5094521e7a5cc9b1947daca'),
    ('docs/MASTER_CONTEXT.md','e4556b11d6e09c1102fcdc5450e4eb6b7ed03c5852e1ac869fb19e35566c41d8'),
    ('artifacts/research_session_h16_same_state_library_usage.json','ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117'),
    ('configs/h17_occupancy_draft.json','4eb9401465744e2f29d026b9a42f6480015c1774cf66f676018eeaf256b45f0f'),
    ('artifacts/h17_seed_dependency_coverage_validated.json','42eee2ea11e4ffbc4a870af77f7faf84472797fda5a9052888f62094b2ebc6bf'),
])
def test_preserved_research_inputs_match_documented_hashes(path,digest):
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    assert digest in DOC.read_text()


def test_no_protocol_lock_authorization_or_numerical_holdout_registration():
    d=worksheet()
    assert d['status']=='feasibility_only'
    assert d['protocol_locked'] is False and d['execution_authorized'] is False
    assert d['holdout_seed_ids']==[]
    text=DOC.read_text()
    assert '<!-- protocol-lock' not in text
    for paper in ('2505.22954','1901.01753','1611.02779','1711.09846','1603.08983','1603.06560'):
        assert 'https://arxiv.org/abs/'+paper in text


def test_proposed_parameter_and_memory_estimates_are_consistent():
    d=worksheet()
    models=d['plain_mlp_estimates']
    assert [m['family'] for m in models]==['pendulum','acrobot','proposed_navigation']
    for m in models:
        o,a=m['obs_dim'],m['n_actions']
        assert m['parameters']==64*(o+a+1)+64*65+(o+1)*65
    n=d['independent_bundles']
    assert n*sum(m['parameters'] for m in models[:2])*4==d['source_weight_bytes']
    assert n*models[2]['parameters']*4==d['future_navigation_weight_bytes']
    f=d['proposed_bandit_features']
    assert d['variant_count']*(f*f+f)*8==d['proposed_bandit_matrix_vector_bytes']
    # Compact proposed layout, excluding string/object storage and runtime overhead.
    row=2*max(m['obs_dim'] for m in models)*4+3*8+4+2
    assert row==d['compact_source_row_bytes_upper_bound']
    assert row*d['source_collection_steps']==d['compact_source_payload_bytes_upper_bound']


def test_literature_extensions_are_primary_source_links():
    text=DOC.read_text()
    for paper in ('1606.04474','2211.15944'):
        assert 'https://arxiv.org/abs/'+paper in text
    assert 'https://www.cs.ubc.ca/labs/algorithms/Projects/ParamILS/' in text
