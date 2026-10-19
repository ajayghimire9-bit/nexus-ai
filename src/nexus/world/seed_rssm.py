"""Compact Seed RSSM extension; existing factory/MPC are reused by its adapters.

One shared multimodal GRU, deterministic h plus Gaussian z, learned world heads,
prototype keys, concept proposal head and local trace decoder. Authored domain.
"""
import hashlib
import json
import math
from pathlib import Path
import torch
from torch import nn
from nexus.nn.factory import build_mlp

ACTION_NAMES=('left','right','up','down','ask','store','retrieve','right_down','left_up')
TRACE_WORDS=('<pad>','<bos>','<eos>','moved','left','right','up','down','asked','question',
             'stored','concept','retrieved','used','program','reached','goal','blocked')


class SeedRSSM(nn.Module):
    def __init__(self, trunk_width=32, activation='tanh'):
        super().__init__()
        if trunk_width not in (16,32) or activation not in ('tanh','relu'):raise ValueError('registered_seed_architecture')
        self.trunk_width=trunk_width;self.activation=activation
        self.work=dict(encoder_batches=0,encoder_rows=0,transition_batches=0,transition_rows=0,
            head_batches=0,head_rows=0,language_training_batches=0,language_token_forwards=0,proposal_calls=0)
        self.text=nn.Embedding(128,16,padding_idx=0)
        self.pixels=nn.Linear(27,16);self.proprio=nn.Linear(12,16)
        self.modality=nn.Parameter(torch.zeros(3,16))
        self.encoder=nn.GRU(16,32,batch_first=True)
        self.key=nn.Linear(32,16);self.query=nn.Linear(32,16)
        self.recurrent=nn.GRUCell(8+9+16,32)
        self.prior=nn.Linear(32,16);self.posterior=nn.Linear(64,16)
        trunk,_=build_mlp(40,(trunk_width,),activation)
        self.trunk=trunk;self.state_head=nn.Linear(trunk_width,12)
        self.next_latent=nn.Linear(trunk_width,32);self.reward=nn.Linear(trunk_width,1)
        self.done=nn.Linear(trunk_width,1);self.value=nn.Linear(trunk_width,1)
        self.proposal=nn.Sequential(nn.Linear(64,32),nn.Tanh(),nn.Linear(32,37))
        self.language_initial=nn.Linear(56,32)
        self.language_embedding=nn.Embedding(len(TRACE_WORDS),16)
        self.language=nn.GRU(16,32,batch_first=True)
        self.language_head=nn.Linear(32,len(TRACE_WORDS))

    def encode(self, text, pixels, proprio, mask=None):
        """Separate projections, ONE shared encoder/latent for all modalities."""
        self.work['encoder_batches']+=1;self.work['encoder_rows']+=len(text)
        streams=[self.text(text)+self.modality[0],
                 self.pixels(pixels)+self.modality[1],
                 self.proprio(proprio).unsqueeze(1)+self.modality[2]]
        if mask is not None:
            streams=[s for i,s in enumerate(streams) if mask[i]]
        if not streams:raise ValueError('at_least_one_modality')
        _,h=self.encoder(torch.cat(streams,dim=1))
        return h[-1]

    def initial(self, batch=1):
        device=next(self.parameters()).device
        return torch.zeros(batch,32,device=device),torch.zeros(batch,8,device=device)

    @staticmethod
    def distribution(raw):
        mean,scale=raw.chunk(2,-1)
        return mean,torch.nn.functional.softplus(scale)+.1

    def transition(self, h, z, action, memory=None, sample=False):
        self.work['transition_batches']+=1;self.work['transition_rows']+=len(h)
        if memory is None:memory=torch.zeros(len(h),16,device=h.device)
        a=torch.nn.functional.one_hot(action.long(),9).float()
        h=self.recurrent(torch.cat((z,a,memory),-1),h)
        mean,std=self.distribution(self.prior(h))
        z=mean+std*torch.randn_like(mean) if sample else mean
        return h,z,mean,std

    def observe(self,h,z,action,encoded,memory=None,sample=False):
        h,_,prior_mean,prior_std=self.transition(h,z,action,memory,sample=False)
        mean,std=self.distribution(self.posterior(torch.cat((h,encoded),-1)))
        z=mean+std*torch.randn_like(mean) if sample else mean
        return h,z,(mean,std,prior_mean,prior_std)

    def heads(self,h,z):
        self.work['head_batches']+=1;self.work['head_rows']+=len(h)
        f=self.trunk(torch.cat((h,z),-1))
        return dict(state=self.state_head(f),latent=self.next_latent(f),
                    reward=self.reward(f).squeeze(-1),done=self.done(f).squeeze(-1),
                    value=self.value(f).squeeze(-1))

    def retrieve(self, encoded, prototypes):
        if prototypes.numel()==0:
            return torch.zeros(len(encoded),16,device=encoded.device),torch.zeros(len(encoded),0,device=encoded.device)
        keys=self.key(prototypes);scores=self.query(encoded)@keys.T/4
        weights=scores.softmax(-1)
        return weights@keys,weights

    def propose(self, positives, negatives):
        self.work['proposal_calls']+=1
        return self.proposal(torch.cat((positives.mean(0),negatives.mean(0)),-1))

    def language_logits(self,h,z,memory,tokens):
        self.work['language_training_batches']+=1
        initial=torch.tanh(self.language_initial(torch.cat((h,z,memory),-1))).unsqueeze(0)
        out,_=self.language(self.language_embedding(tokens),initial)
        return self.language_head(out)

    def generate(self,h,z,memory,max_words=6):
        initial=torch.tanh(self.language_initial(torch.cat((h,z,memory),-1))).unsqueeze(0)
        token=torch.tensor([[1]],device=h.device);words=[]
        for _ in range(max_words):
            self.work['language_token_forwards']+=1
            out,initial=self.language(self.language_embedding(token),initial)
            i=int(self.language_head(out[:,-1]).argmax(-1));token=torch.tensor([[i]],device=h.device)
            if i==2:break
            if i>2:words.append(TRACE_WORDS[i])
        return ' '.join(words)

    def export(self,path,provenance):
        data=dict(schema='seed_rssm_v1',architecture=dict(h=32,z=8,encoder=32,actions=list(ACTION_NAMES),trunk_width=self.trunk_width,activation=self.activation),
                  provenance=provenance,weights={k:v.detach().cpu().tolist() for k,v in self.state_dict().items()})
        path=Path(path)
        with path.open('x') as f:json.dump(data,f,allow_nan=False)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def load(cls,path,expected_hash):
        path=Path(path)
        if path.stat().st_size>2_000_000:raise ValueError('seed_model_size_cap')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError('seed_model_hash')
        data=json.loads(raw)
        a=data.get('architecture',{})
        if set(data)!={'schema','architecture','provenance','weights'} or data['schema']!='seed_rssm_v1' or a!=dict(h=32,z=8,encoder=32,actions=list(ACTION_NAMES),trunk_width=a.get('trunk_width'),activation=a.get('activation')):
            raise ValueError('seed_rssm_schema')
        model=cls(a['trunk_width'],a['activation']);expected=model.state_dict()
        if set(data['weights'])!=set(expected):raise ValueError('seed_weight_names')
        def numeric(v):
            return all(numeric(x) for x in v) if type(v) is list else type(v) in (int,float) and math.isfinite(v)
        if not all(numeric(v) for v in data['weights'].values()):raise ValueError('seed_numeric_weights')
        state={k:torch.tensor(v,dtype=expected[k].dtype) for k,v in data['weights'].items()}
        if any(v.shape!=expected[k].shape or not torch.isfinite(v).all() for k,v in state.items()):raise ValueError('seed_weight_shapes_or_finiteness')
        model.load_state_dict(state);model.eval()
        for p in model.parameters():p.requires_grad_(False)
        return model,data['provenance']
