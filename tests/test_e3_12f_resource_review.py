"""Operation metadata and authored feedback only: zero model/simulator steps."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from nexus.evolution1.resources import Work
from nexus.evolution2 import reset_blocks as b,reset_blocked_study as study

ROOT=Path(__file__).resolve().parents[1]


def test_true_operator_bounds_and_worst_union_not_50_call_average():
    envelopes=b.operation_envelopes()
    assert envelopes=={'parent':Work(1,1491,51,51),'switch':Work(1,1536,51,51),'rank_blend':Work(1,1491,67,67)}
    maximum=b.maximum_experiment_work()
    assert maximum==Work(28800,43372800,1622400,1622400)
    assert maximum.model_calls>28800*50
    c=json.loads((ROOT/'configs/e3_12f_reset_blocked_runtime_v2.json').read_text())
    assert study.validate_config(c) is False
    assert maximum.imagined_transitions<=c['imagined_cap']
    old=deepcopy(c);old['model_call_cap']=1440000
    with pytest.raises(ValueError):study.validate_config(old)


def test_real_operation_plan_changes_cannot_silently_exceed_recipe(monkeypatch):
    c=json.loads((ROOT/'configs/e3_12f_reset_blocked_runtime_v2.json').read_text())
    monkeypatch.setattr(b,'maximum_experiment_work',lambda:Work(28800,43372800,1622401,1622401))
    with pytest.raises(ValueError,match='operation_bound'):study.validate_config(c)


def test_verified_bounds_cover_every_possible_balanced_assignment():
    # Metadata only. Each balanced allocation pair has even disagreement;
    # show all possible union sizes, rather than sampling 20 favorable seeds.
    import itertools
    bounds=b.operation_envelopes()
    ids=tuple(range(8));random_switch=set(range(4));all_switches=list(itertools.combinations(ids,4))
    assert len(all_switches)==70
    for subset in all_switches:
        blocked_switch=set(subset);total=Work()
        for i in ids:
            names={'parent','switch' if i in random_switch else 'rank_blend','switch' if i in blocked_switch else 'rank_blend'}
            for name in names:total=total.plus(Work(*(v*200 for v in bounds[name].values())))
        for w in bounds.values():total=total.plus(Work(*(v*4*200 for v in w.values())))
        assert total.fits(Work(*(v//4 for v in b.maximum_experiment_work().values())))


def test_matched_estimator_and_raw_selector_receive_same_mask_but_can_disagree():
    plan=b.make_plan('pendulum',[dict(reset_id=i,observation=[i/8,0.,0.]) for i in range(8)],7)
    condition='public_blocked';rows=[]
    for rid,kinds in b.required_paths(plan).items():
        assigned=plan['schedules'][condition][rid];parent=100. if assigned=='switch' else -100.
        returns={'parent':parent,'switch':parent-2.,'rank_blend':parent+3.}
        rows.append(dict(reset_id=int(rid),paths={k:{'return':returns[k],'cpu_s':1.} for k in kinds}))
    raw=b.select_parent_inclusive(plan,rows,condition,0);paired=b.select_paired_parent_gain(plan,rows,condition,0)
    assert raw['choice']=='switch' and paired['choice']=='rank_blend'
    assert paired['matched_advantages']=={'parent':0.,'switch':-2.,'rank_blend':3.}
    assert raw['observed_counts']==paired['observed_counts']=={'parent':8,'switch':4,'rank_blend':4}
    for row in rows:
        assigned=plan['schedules'][condition][str(row['reset_id'])]
        for kind in row['paths']:
            if kind not in ('parent',assigned):row['paths'][kind]['return']=1e8
    assert b.select_paired_parent_gain(plan,rows,condition,0)==paired


def test_secondary_exact_ties_keep_parent():
    plan=b.make_plan('pendulum',[dict(reset_id=i,observation=[1.,0.,0.]) for i in range(8)],7)
    rows=[dict(reset_id=int(i),paths={k:{'return':1.,'cpu_s':1.} for k in kinds}) for i,kinds in b.required_paths(plan).items()]
    assert b.select_paired_parent_gain(plan,rows,'public_blocked',0)['choice']=='parent'


def test_secondary_positive_estimate_cannot_upgrade_zero_primary(monkeypatch):
    from test_e3_12f_runner_integration import fixture
    p,c=fixture()
    monkeypatch.setattr(study,'validate',lambda *args:True)
    for key,choices in p['sealed_decisions'].items():
        choices['random_balanced']['choice']=choices['public_blocked']['choice']='parent'
        choices['paired_secondary']['random_balanced']['choice']='parent'
        choices['paired_secondary']['public_blocked']['choice']='switch'
    for row in p['rows']:
        if row['role']=='evaluation':
            row['paths']['parent']['return']=0.;row['paths']['switch']['return']=10.
    result=study.analyze(p,c)
    assert result['label']=='reset_blocking_not_established'
    assert all(f['contrasts']['random_balanced']['mean']==0 for f in result['families'].values())
    assert all(f['secondary_contrasts']['public_blocked_paired-minus-random_balanced_paired']['mean']==10 for f in result['families'].values())
