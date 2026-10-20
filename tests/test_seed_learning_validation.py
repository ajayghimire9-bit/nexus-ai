import copy
import random
import torch
import pytest
from nexus.seed.learning_benchmark import LessonTask,curve,update,scale_features,collect_task,frozen_scores
from nexus.seed.plasticity import PlasticityController
from nexus.seed.semantic_lessons import Relation,compose_instructions,task as meaning_task
from nexus.seed.learning_selection import episode
from nexus.seed.grounded_meta import OuterSeedMeta
from nexus.seed.list_transfer import authorize
from nexus.world.seed_rssm import SeedRSSM
from nexus.seed.core import Session,Move


def toy():
    g=torch.Generator().manual_seed(7);x=torch.randn(20,62,generator=g);w=torch.randn(62,generator=g)
    scale=scale_features(x[:8]);x=x/scale;y=x@w
    return LessonTask(x[:8],y[:8],x[8:12],y[8:12],x[12:16],y[12:16],x[16:],y[16:])


def test_scaled_replay_step_descends_even_with_large_feature_magnitudes():
    g=torch.Generator().manual_seed(2);x=torch.randn(6,62,generator=g)*100;target=torch.randn(6,generator=g);t=torch.randn(62,generator=g)
    before=(x@t-target).square().mean()
    after=update(t,x[-1],target[-1],x[:2],target[:2],x[2:],target[2:],None,'replay')
    assert (x@after-target).square().mean()<before


def test_budgets_query_isolation_no_adaptation_and_meta_gradients():
    t=toy();m=PlasticityController();rows,snaps=curve(t,m,'learned')
    assert [k for k,_,_ in rows]==[1,2,4,8]
    changed=LessonTask(t.support_x,t.support_y,t.query_x,t.query_y+99,t.old_x,t.old_y,t.retention_x,t.retention_y)
    assert all(torch.equal(v,curve(changed,m,'learned')[1][k]) for k,v in snaps.items())
    loss=torch.stack([e for _,e,_ in rows]).mean();loss.backward()
    assert sum(float(p.grad.abs().sum()) for p in m.parameters())>0
    none=curve(t,m,'none')[1];assert torch.equal(none[1],none[8])


def test_neutral_ablation_matches_untrained_controller_exact_update_scale():
    t=toy();m=PlasticityController()
    a=curve(t,m,'learned')[1];b=curve(t,m,'neutral')[1]
    assert all(torch.allclose(a[k],b[k],atol=1e-6) for k in a)


def test_source_audit_additive_reward_correction_has_state_invariant_action_differences():
    from nexus.seed.adaptive_state import reward_features
    g=torch.Generator().manual_seed(53);theta=torch.randn(62,generator=g)
    x1=reward_features(torch.randn(1,32,generator=g),torch.randn(1,8,generator=g),torch.randn(1,12,generator=g))
    x2=reward_features(torch.randn(1,32,generator=g),torch.randn(1,8,generator=g),torch.randn(1,12,generator=g))
    p1=x1@theta;p2=x2@theta
    assert torch.allclose(p1-p1[0],p2-p2[0],atol=2e-6)
    # This proves a representational restriction of the correction,not that
    # the nonlinear frozen model has state-invariant action rankings.


def test_source_audit_shared_word_hash_only_provides_an_object_independent_offset():
    from nexus.seed.adaptive_state import meaning_features
    theta=torch.arange(53).float()/53
    differences=[]
    for seed in (5,7):
        g=torch.Generator().manual_seed(seed);e=torch.randn(1,32,generator=g);p=torch.randn(1,12,generator=g)
        a=meaning_features(e,p,'dax');b=meaning_features(e,p,'wug')
        differences.append((a-b)@theta)
    assert torch.equal(differences[0],differences[1])


def test_collection_pairs_truth_and_preserves_parent_weights():
    torch.manual_seed(4);m=SeedRSSM();m.world_memory_bank=torch.zeros(32,32);m.semantics='aligned_v1'
    old={k:v.clone() for k,v in m.state_dict().items()};counts={}
    def charge(k):counts[k]=counts.get(k,0)+1
    task,raw=collect_task(m,87000000,charge,lambda:None)
    assert counts==dict(support=8,old=4,query=27,retention=27)
    assert task.query_x.shape==(27,62) and len(raw['records']['query'])==3
    assert all(torch.equal(old[k],v) for k,v in m.state_dict().items())
    allseeds=[r['seed'] for rows in raw['records'].values() for r in rows]
    assert len(allseeds)==len(set(allseeds))


def test_relations_and_composed_programs_use_observations_and_vetted_moves():
    a=dict(x=0,y=1,color='red',shape='circle');b=dict(x=3,y=2,color='blue',shape='circle')
    assert Relation('left_of').matches((a,b)) and Relation('same_shape').matches((a,b))
    moves=compose_instructions('please dax the o2 then wug o3',{'dax':'right','wug':'up'})
    assert moves==(Move('o2','right'),Move('o3','up'))
    assert compose_instructions('dax o2 then unknown o3',{'dax':'right'}) is None
    s=Session();out=s.execute(compose_instructions('dax o1',{'dax':'right'}));assert out['type']=='acted'


def test_selector_cannot_receive_hidden_labels_and_accounts_actual_probes():
    torch.manual_seed(2);m=SeedRSSM();lesson=meaning_task(m,91000000,'unary',0)
    c=PlasticityController();meta=OuterSeedMeta()
    first=episode(lesson,c,meta,'adaptive',training=True)
    assert first['labels']<=16 and len(first['trace'])<=8 and meta.journal.snapshot()
    a=OuterSeedMeta();b=OuterSeedMeta();changed=dict(lesson,qy=list(lesson['qy'][:8])+[not y for y in lesson['qy'][8:]])
    r1=episode(lesson,c,a,'adaptive');r2=episode(changed,c,b,'adaptive')
    assert r1['trace']==r2['trace'] and not a.journal.snapshot()
    with pytest.raises(ValueError):meta.reveal_learning('ask',{},phase='audit')


@pytest.mark.parametrize('gates',[{},dict(learning=True,actions=False),dict(learning=1,actions=True)])
def test_transfer_is_blocked_without_both_meaningful_object_successes(gates):
    with pytest.raises(ValueError):authorize(gates)


def test_registered_seed_blocks_are_disjoint_and_do_not_reuse_closed_seed_tasks():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1];c=json.loads((root/'configs/seed_learning_validation.json').read_text())
    seeds=[s for rows in c['task_seeds'].values() for s in rows]+c['meaning_seeds']+c['selector_train_seeds']+c['selector_audit_seeds']+[c['instruction_seed']]+c['transfer_seeds']
    assert len(seeds)==len(set(seeds))
    for f in ('seed_contract_study.json','seed_action_ranking.json'):
        old=json.loads((root/'artifacts'/f).read_text())
        prior={e['seed'] for role in ('source','states','ranking') for e in old.get(role,[]) if 'seed' in e}
        assert not set(seeds)&prior


def test_registered_worst_case_fits_both_caps_without_assuming_early_success():
    import json
    from pathlib import Path
    from nexus.seed.learning_validation_audit import resource_bound
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/seed_learning_validation.json').read_text())
    b=resource_bound(c)
    assert b==dict(max_world_steps=6960,max_supervised_answers=720,max_authored_interactions=7680,max_imagined_rows=48816)
    assert b['max_authored_interactions']<=c['max_authored_interactions'] and b['max_imagined_rows']<=c['max_imagined_transitions']
