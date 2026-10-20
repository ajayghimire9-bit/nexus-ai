"""Authored multimodal world adapter. Not perception from a real camera."""
import random
import numpy as np
import torch
from .core import examples
from .planning import movement_reward
from nexus.world.seed_rssm import ACTION_NAMES,TRACE_WORDS

COLORS={'red':(1.,0.,0.),'blue':(0.,0.,1.),'green':(0.,1.,0.)}
SHAPES={'square':np.ones((3,3)), 'circle':np.array([[0,1,0],[1,1,1],[0,1,0]]),
        'triangle':np.array([[0,1,0],[0,1,0],[1,1,1]])}


def observation(obj,goal=(3,3),flags=(0,0,0)):
    image=np.zeros((18,18,3),np.float32)
    pattern=SHAPES[obj['shape']] * (1. if obj['size']=='large' else .6)
    image[obj['y']*3:obj['y']*3+3,obj['x']*3:obj['x']*3+3]=pattern[:,:,None]*np.array(COLORS[obj['color']])
    patches=image.reshape(6,3,6,3,3).transpose(0,2,1,3,4).reshape(36,27)
    text=f"{obj['size']} {obj['color']} {obj['shape']}"
    chars=[ord(c) for c in text[:24]];chars += [0]*(24-len(chars))
    proprio=np.array([obj['x']/5,obj['y']/5,goal[0]/5,goal[1]/5,
        int(obj['color']=='red'),int(obj['color']=='blue'),int(obj['color']=='green'),
        int(obj['shape']=='circle'),int(obj['shape']=='square'),int(obj['shape']=='triangle'),
        int(obj['size']=='large'),sum(flags)/3],np.float32)
    return dict(text=chars,pixels=patches,proprio=proprio)


def tensors(observations):
    return (torch.tensor([o['text'] for o in observations],dtype=torch.long),
            torch.tensor(np.stack([o['pixels'] for o in observations]),dtype=torch.float32),
            torch.tensor(np.stack([o['proprio'] for o in observations]),dtype=torch.float32))


def trace_for(action,done=False,blocked=False):
    if done:return 'reached goal'
    if blocked:return 'blocked'
    if action<4:return 'moved '+ACTION_NAMES[action]
    return ('asked question','stored concept','retrieved concept','used program','used program')[action-4]


def token_trace(text):
    ids=[TRACE_WORDS.index(w) for w in text.split()]+[2]
    ids += [0]*(4-len(ids))
    return ids[:4]


class AuthoredWorld:
    def __init__(self,seed):
        r=random.Random(seed);self.obj=dict(r.choice(examples()),id='o1',x=r.randrange(6),y=r.randrange(6))
        self.goal=(r.randrange(6),r.randrange(6));self.flags=[0,0,0];self.steps=0
        if self.goal==(self.obj['x'],self.obj['y']):self.goal=((self.goal[0]+1)%6,self.goal[1])

    def observe(self):return observation(self.obj,self.goal,self.flags)

    def step(self,action):
        if type(action) is not int or not 0<=action<9:raise ValueError('grounded_action')
        before=abs(self.obj['x']-self.goal[0])+abs(self.obj['y']-self.goal[1])
        blocked=False;info=0.;primitive=0
        moves={0:[(-1,0)],1:[(1,0)],2:[(0,-1)],3:[(0,1)],7:[(1,0),(0,1)],8:[(-1,0),(0,-1)]}
        for dx,dy in moves.get(action,[]):
            x,y=self.obj['x']+dx,self.obj['y']+dy
            if 0<=x<6 and 0<=y<6:self.obj['x'],self.obj['y']=x,y;primitive+=1
            else:blocked=True
        if 4<=action<=6:
            i=action-4
            if not self.flags[i]:
                self.flags[i]=1;info=.05 if action==4 and getattr(self,'information_reward',True) else 0.
        after=abs(self.obj['x']-self.goal[0])+abs(self.obj['y']-self.goal[1])
        done=after==0;self.steps+=1
        reward=movement_reward(before,after,done,info)
        return self.observe(),reward,done,dict(trace=trace_for(action,done,blocked),
            information_gain_proxy=info,primitive_actions=primitive,blocked=blocked)
