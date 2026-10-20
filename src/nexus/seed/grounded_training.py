"""Bounded coherent-sequence training/evaluation for the authored Seed domain."""
import random
import time
import numpy as np
import torch
from torch import nn
from nexus.world.seed_rssm import SeedRSSM,ACTION_NAMES,TRACE_WORDS
from .core import GRAMMAR,examples
from .grounded_world import AuthoredWorld,observation,tensors,token_trace
from .latent_planner import plan,RSSMStepAdapter
from .state_contract import Belief,value_targets


def collect(seeds,max_steps,charge,episodes=None,information_reward=True):
    if episodes is None:episodes=[]
    for seed in seeds:
        world=AuthoredWorld(seed);rng=random.Random(seed+917)
        world.information_reward=information_reward
        frames=[world.observe()];steps=[]
        episodes.append(dict(seed=seed,frames=frames,steps=steps))
        for _ in range(max_steps):
            action=rng.randrange(9);before=dict(world.obj);charge()
            obs,reward,done,info=world.step(action)
            steps.append(dict(action=action,reward=reward,done=done,trace=info['trace'],before=before,after=dict(world.obj),goal=list(world.goal)))
            frames.append(obs)
            if done:break
    return episodes


def train(recipe,episodes,config,check,progress=None,semantics='legacy'):
    torch.manual_seed(config['model_seed'])
    model=SeedRSSM(recipe.trunk_width,recipe.activation)
    if semantics=='aligned_v1':
        model.semantics=semantics
        if len(episodes)<32:raise ValueError('source_memory_requires_32_episodes')
        with torch.no_grad():model.world_memory_bank=model.encode(*tensors([e['frames'][0] for e in episodes[:32]])).detach().clone()
    optimizer=torch.optim.Adam(model.parameters(),lr=config['learning_rate'])
    rng=random.Random(config['schedule_seed']);eligible=[e for e in episodes if len(e['steps'])>=4]
    if not eligible:raise ValueError('coherent_training_windows_missing')
    losses=[];encoder_grad=[]
    for update in range(config['updates']):
        check();batch=[rng.choice(eligible) for _ in range(config['batch_size'])]
        windows=[];aligned_values=[];aligned_masks=[]
        for ep in batch:
            start=rng.randrange(len(ep['steps'])-3)
            windows.append((ep['frames'][start:start+5],ep['steps'][start:start+4]))
            v,mask=value_targets(ep['steps'],start);aligned_values.append(v);aligned_masks.append(mask)
        b=len(batch)
        text,pixels,prop=tensors([o for frames,steps in windows for o in frames])
        encoded=model.encode(text,pixels,prop).reshape(b,5,32)
        targets=prop.reshape(b,5,12)
        actions=torch.tensor([[s['action'] for s in steps] for frames,steps in windows])
        rewards=torch.tensor([[s['reward'] for s in steps] for frames,steps in windows])
        dones=torch.tensor([[s['done'] for s in steps] for frames,steps in windows],dtype=torch.float32)
        returns=[]
        for frames,steps in windows:
            total=0.;seq=[]
            for s in reversed(steps):total=s['reward']+.9*total*(not s['done']);seq.append(total)
            returns.append(list(reversed(seq)))
        values=torch.tensor(returns)
        h,z=model.initial(b);belief=Belief(model,b);prev=torch.zeros(b,dtype=torch.long)
        loss=0.;parts={k:0. for k in ('state','latent','reward','done','value','kl','language','retrieval','concept')}
        for t in range(4):
            _,weights=model.retrieve(encoded[:,t],encoded[:,t].detach())
            if semantics=='aligned_v1':
                h,z,dist=belief.observe(encoded[:,t],prev,t,sample=True);memory=belief.memory
            else:
                memory,_=model.retrieve(encoded[:,t],encoded[:,t].detach())
                h,z,dist=model.observe(h,z,prev,encoded[:,t],memory,sample=True)
            predicted_h,predicted_z,_,_=model.transition(h,z,actions[:,t],memory,sample=True)
            pred=model.heads(predicted_h,predicted_z)
            mean,std,pm,ps=dist
            terms=dict(state=nn.functional.mse_loss(pred['state'],targets[:,t+1]),
                latent=.1*nn.functional.mse_loss(pred['latent'],encoded[:,t+1].detach()),
                reward=nn.functional.mse_loss(pred['reward'],rewards[:,t]),
                done=nn.functional.binary_cross_entropy_with_logits(pred['done'],dones[:,t]),
                value=.1*nn.functional.mse_loss(pred['value'],values[:,t]),
                kl=.01*(torch.log(ps/std)+(std.square()+(mean-pm).square())/(2*ps.square())-.5).mean(),
                retrieval=.05*nn.functional.nll_loss(weights.clamp_min(1e-9).log(),torch.arange(b)))
            if semantics=='aligned_v1':
                mask=torch.tensor(aligned_masks,dtype=torch.bool)[:,t]
                current_value=model.heads(h,z)['value']
                desired=torch.tensor(aligned_values)[:,t]
                terms['value']=.1*nn.functional.mse_loss(current_value[mask],desired[mask]) if mask.any() else current_value.sum()*0
            trace=torch.tensor([token_trace(steps[t]['trace']) for frames,steps in windows])
            # Decode the ACTUAL action trace from its resulting recurrent state.
            resulting_h,resulting_z,_=model.observe(h,z,actions[:,t],encoded[:,t+1],memory,sample=True)
            if semantics=='aligned_v1' and dones[:,t].bool().any():
                terminal=dones[:,t].bool();terms['value']=terms['value']+.1*model.heads(resulting_h,resulting_z)['value'][terminal].square().mean()
            inputs=torch.cat((torch.ones(b,1,dtype=torch.long),trace[:,:-1]),1)
            terms['language']=.2*nn.functional.cross_entropy(model.language_logits(resulting_h,resulting_z,memory,inputs).reshape(-1,len(TRACE_WORDS)),trace.reshape(-1),ignore_index=0)
            for k,v in terms.items():parts[k]+=float(v.detach())/4;loss=loss+v/4
            prev=actions[:,t]
        # Missing-modality training supplies all three streams to the SAME GRU.
        mode=update%3
        ablated=model.encode(text,pixels,prop,mask=tuple(i==mode for i in range(3)))
        parts['state']+=float(nn.functional.mse_loss(ablated,encoded.reshape(-1,32).detach()).detach())*.05
        loss=loss+.05*nn.functional.mse_loss(ablated,encoded.reshape(-1,32).detach())
        predicate_index=rng.randrange(len(GRAMMAR));predicate=GRAMMAR[predicate_index]
        all_objects=examples();positives=[o for o in all_objects if predicate.matches(o)];negatives=[o for o in all_objects if not predicate.matches(o)]
        p=model.encode(*tensors([observation(rng.choice(positives)) for _ in range(4)]))
        n=model.encode(*tensors([observation(rng.choice(negatives)) for _ in range(4)]))
        concept=.2*nn.functional.cross_entropy(model.propose(p,n).reshape(1,-1),torch.tensor([predicate_index]))
        loss=loss+concept;parts['concept']=float(concept.detach())
        if not torch.isfinite(loss):raise ValueError('nonfinite_grounded_training')
        optimizer.zero_grad();loss.backward()
        norm=sum(float(p.grad.norm()) for p in model.encoder.parameters() if p.grad is not None)
        encoder_grad.append(norm);optimizer.step()
        losses.append(dict(update=update+1,total=float(loss.detach()),**parts))
        if progress is not None:progress(losses[-1])
    model.eval()
    for p in model.parameters():p.requires_grad_(False)
    return model,dict(losses=losses,encoder_gradient_norms=encoder_grad,
        updates=config['updates'],query_transition_presentations=config['updates']*config['batch_size']*4,
        authored_program_target_presentations=config['updates']*8,
        parameter_count=sum(p.numel() for p in model.parameters()))


def prediction_metrics(model,episodes):
    errors=[];reward_errors=[];done_losses=[];texts=[];modalities={k:[] for k in ('text','pixels','proprioception')}
    for ep in episodes:
        h,z=model.initial();previous=0
        for t,step in enumerate(ep['steps']):
            args=tensors([ep['frames'][t]]);target=torch.tensor(ep['frames'][t+1]['proprio']).unsqueeze(0)
            with torch.no_grad():
                e=model.encode(*args);h,z,_=model.observe(h,z,torch.tensor([previous]),e)
                nh,nz,_,_=model.transition(h,z,torch.tensor([step['action']]))
                out=model.heads(nh,nz);errors.append(float((out['state']-target).abs().mean()))
                reward_errors.append(abs(float(out['reward'][0])-step['reward']))
                done_losses.append(float(nn.functional.binary_cross_entropy_with_logits(out['done'],torch.tensor([float(step['done'])]))))
                ne=model.encode(*tensors([ep['frames'][t+1]]));rh,rz,_=model.observe(h,z,torch.tensor([step['action']]),ne)
                generated=model.generate(rh,rz,torch.zeros(1,16));texts.append(dict(target=step['trace'],generated=generated,correct=generated==step['trace']))
                for i,key in enumerate(modalities):
                    partial=model.encode(*args,mask=tuple(j==i for j in range(3)))
                    modalities[key].append(float((partial-e).abs().mean()))
            previous=step['action']
    return dict(state_mae=float(np.mean(errors)),reward_mae=float(np.mean(reward_errors)),
        done_bce=float(np.mean(done_losses)),trace_exact_accuracy=sum(t['correct'] for t in texts)/len(texts),
        traces=texts,modality_latent_mae={k:float(np.mean(v)) for k,v in modalities.items()},
        observations=len(errors))


def evaluate_control(model,seeds,max_steps,method,charge,check,rows=None,imagine_charge=None,*,prune=True,information_reward=True):
    if rows is None:rows=[]
    for seed in seeds:
        world=AuthoredWorld(seed);rng=random.Random(seed+91);h,z=model.initial();previous=0;steps=[]
        world.information_reward=information_reward;belief=Belief(model)
        row=dict(seed=seed,return_sum=0.,success=False,steps=steps);rows.append(row)
        for t in range(max_steps):
            check();info={}
            with torch.no_grad():
                if belief.token is None:belief.observe(model.encode(*tensors([world.observe()])),torch.zeros(1,dtype=torch.long),0)
                h,z=belief.h,belief.z
                if method=='latent_mpc':
                    if imagine_charge is not None:imagine_charge(48 if prune else 64)
                    action,info=plan(model,h,z,belief.memory,seed=seed*100+t,prune=prune)
                elif method=='random':action=rng.randrange(9)
                else:
                    dx=world.goal[0]-world.obj['x'];dy=world.goal[1]-world.obj['y']
                    action=(1 if dx>0 else 0) if dx else (3 if dy>0 else 2)
            before=dict(world.obj);charge();next_obs,reward,done,actual=world.step(action)
            steps.append(dict(action=action,reward=reward,done=done,trace=actual['trace'],planning=info,
                before=before,after=dict(world.obj),goal=list(world.goal),information_gain_proxy=actual['information_gain_proxy']))
            row['return_sum']+=reward;row['success']=done
            previous=action
            with torch.no_grad():belief.observe(model.encode(*tensors([next_obs])),torch.tensor([action]),t+1)
            if done:break
    return rows
