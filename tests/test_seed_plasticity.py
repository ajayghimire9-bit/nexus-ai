import copy
import torch
import pytest
from nexus.seed.plasticity import correction,PlasticityController,TrainingLesson,learning_curve
from nexus.seed.adaptive_state import AdaptiveState,validate_state


def test_local_equation_reproduces_attached_example_and_contradiction():
    theta=torch.tensor([1.,0.],dtype=torch.float64);x=torch.ones(2,dtype=torch.float64)
    a=torch.tensor([[1.,0.]],dtype=torch.float64);d=torch.ones(2,dtype=torch.float64)
    new=correction(theta,x,2.,a,d,epsilon=0)
    assert new.tolist()==pytest.approx([1+1/11,10/11],abs=1e-12)
    plain=correction(theta,x,2.,a,d,protection=0,epsilon=0)
    assert float((a@plain-1).square()/(a@new-1).square())==pytest.approx(30.25)
    impossible=correction(theta,a[0],2.,a,d,epsilon=0)
    assert float(a@impossible)==pytest.approx(2) # same input cannot retain answer1


def test_woodbury_matches_direct_precision_solve_100_systems():
    g=torch.Generator().manual_seed(991)
    for i in range(100):
        n=3+i%9;m=i%5
        t=torch.randn(n,generator=g,dtype=torch.float64);x=torch.randn(n,generator=g,dtype=torch.float64)
        a=torch.randn(m,n,generator=g,dtype=torch.float64);d=torch.rand(n,generator=g,dtype=torch.float64)+.1
        p=torch.linalg.solve(torch.diag(1/d)+9*a.T@a,x)
        expected=t+.8*(1.7-x@t)*p/(.01+x@p)
        assert torch.allclose(correction(t,x,1.7,a,d,damping=.8),expected,atol=1e-11,rtol=1e-11)


def test_outer_gradient_changes_update_rule_not_inner_labels():
    m=PlasticityController(2)
    task=TrainingLesson(torch.ones(1,2),torch.tensor([2.]),torch.tensor([[0.,1.]]),torch.tensor([1.]),torch.tensor([[1.,0.]]),torch.tensor([1.]))
    loss,theta,*_=learning_curve(m,task);loss.backward()
    assert sum(float(p.grad.abs().sum()) for p in m.parameters())>0
    changed=TrainingLesson(task.support_x,task.support_y,task.query_x,task.query_y+100,task.old_x,task.old_y)
    assert torch.equal(theta,learning_curve(m,changed)[1])
    baseline=learning_curve(m,task,baseline=True)[0]
    assert not baseline.requires_grad


def test_true_lessons_only_duplicates_rejected_and_assessments_separate():
    a=AdaptiveState();x=torch.ones(62)
    for i in range(8):a.update('reward',x,.4,f'{i:064x}')
    assert len(a.anchors['reward'])==6 and len(a.development['reward'])==2
    assert a.work['actual_updates']==6
    with pytest.raises(ValueError):a.update('reward',x,.4,f'{0:064x}')
    state=a.snapshot();b=AdaptiveState();b.restore(state);assert b.snapshot()==state
    broken=copy.deepcopy(state);broken['anchors']['reward'].append(broken['development']['reward'][0])
    with pytest.raises(ValueError):validate_state(broken)


def test_hypothetical_questions_do_not_learn_or_access_assessment():
    a=AdaptiveState();x=torch.ones(53)
    a.update('meaning',x,.5,'a'*64)
    before=a.snapshot();a.expected_question([x,x*.5]);after=a.snapshot()
    assert before['blocks']==after['blocks'] and before['anchors']==after['anchors'] and before['seen']==after['seen']
    assert after['work']['question_hypotheses']==4
    changed=AdaptiveState();changed.restore(before);changed.development['meaning']=[dict(x=x.tolist(),y=100.,ref='a'*64,key='')]
    assert a.expected_question([x,x*.5])[1]==changed.expected_question([x,x*.5])[1]


def test_structural_edits_are_bounded_scoped_and_keep_can_win():
    a=AdaptiveState();x=torch.zeros(62);x[0]=1
    for i in range(12):a.update('reward',x,0.,f'{i:064x}',key='known')
    result=a.review('reward','known')
    assert result['adopted']=='keep' and not a.skills
    assert result['candidates'][0]['edit']=='keep'
    assert all(r['bytes_added']>=0 for r in result['candidates'])
    assert a.review('reward','unseen')['status']=='needs_separate_development'


def test_channel_routing_does_not_modify_other_block_and_cap():
    a=AdaptiveState();before=a.blocks['reward'].clone()
    for i in range(24):a.update('meaning',torch.ones(53),.5,f'{i:064x}',key='dax')
    assert torch.equal(before,a.blocks['reward'])
    assert a.update('meaning',torch.ones(53),.5,'f'*64)['status']=='lesson_cap'
    assert len(a.anchors['meaning'])==8 and len(a.development['meaning'])==4


def test_controller_hash_architecture_roundtrip(tmp_path):
    m=PlasticityController();p=tmp_path/'m.json';h=m.export(p,dict(test=True));n=PlasticityController.load(p,h)
    assert torch.equal(m(torch.ones(4)),n(torch.ones(4)))
    with pytest.raises(ValueError):PlasticityController.load(p,'a'*64)


def test_meta_training_is_deterministic_and_parameters_really_update():
    task=TrainingLesson(torch.ones(1,2),torch.tensor([2.]),torch.tensor([[0.,1.]]),torch.tensor([1.]),torch.tensor([[1.,0.]]),torch.tensor([1.]))
    def run():
        torch.manual_seed(6);m=PlasticityController(2);o=torch.optim.Adam(m.parameters(),lr=.01)
        original=m.logits.weight.detach().clone()
        for _ in range(3):
            loss,*_=learning_curve(m,task);o.zero_grad();loss.backward();o.step()
        assert not torch.equal(original,m.logits.weight)
        return copy.deepcopy(m.state_dict())
    a,b=run(),run();assert all(torch.equal(a[k],b[k]) for k in a)


def study_fixture():
    c=dict(controller_seeds=[1],meta_updates=1,support_rows=2,max_imagined_transitions=4,
           split_episode_indices={'train':[0,1],'development':[1,2],'audit':[2,3]},expected_episode_ids={'train':[1],'development':[2],'audit':[3]})
    metric=dict(objective=.1,query_learning_curve=[.1,.1],query_auc=.1,forgetting=0.,theta_norm=1.)
    r=dict(config=c,new_real_steps=0,model_work=dict(frozen_core=True,imagined_candidate_rows=3),episode_ids=c['expected_episode_ids'],
           seeds=[dict(seed=1,parameter_change=1.,training=[{}],evaluation={k:[dict(source_episode_seed=i,methods={m:copy.deepcopy(metric) for m in ('learned','fixed_protected','replay_sgd')})] for k,i in [('train',1),('development',2),('audit',3)]})])
    return c,r


@pytest.mark.parametrize('fault',['seed','episode','method','metric','nan','curve','wrong_expected_ids'])
def test_study_missing_cells_fail_from_locked_grid(fault):
    from nexus.seed.plasticity_study import validate_result
    c,r=study_fixture();assert validate_result(r,c)
    if fault=='seed':r['seeds']=[]
    elif fault=='episode':r['seeds'][0]['evaluation']['audit']=[]
    elif fault=='wrong_expected_ids':r['episode_ids']=dict(r['episode_ids'],audit=[])
    else:
        row=r['seeds'][0]['evaluation']['audit'][0]['methods']
        if fault=='method':row.pop('learned')
        elif fault=='metric':row['learned'].pop('forgetting')
        elif fault=='nan':row['learned']['query_auc']=float('nan')
        elif fault=='curve':row['learned']['query_learning_curve']=[]
    with pytest.raises(ValueError):validate_result(r,c)


@pytest.mark.parametrize('fault',['nan','negative','zero_gradient','too_many_anchors'])
def test_invalid_updates_fail_closed(fault):
    t=torch.zeros(2);x=torch.ones(2);a=torch.zeros(0,2);d=torch.ones(2)
    if fault=='nan':x[0]=float('nan')
    if fault=='negative':d[0]=-1
    if fault=='zero_gradient':x*=0
    if fault=='too_many_anchors':a=torch.ones(17,2)
    with pytest.raises(ValueError):correction(t,x,1.,a,d,epsilon=0)
