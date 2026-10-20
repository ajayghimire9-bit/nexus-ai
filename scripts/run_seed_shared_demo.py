"""Deterministic authored integration demo; NOT a scientific experiment."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.core import Session,examples
from nexus.seed.shared_brain import SharedBrain


def demo():
    start=time.perf_counter();s=Session();b=SharedBrain(s);trace=[]
    def call(p):
        r=b.request(p);trace.append(dict(request=p,response=r['result'],resources=r['resources']));return r['result']
    def teach(lab,name,schema,rows,mode='adaptive'):
        return call(dict(op='lab_teach',lab=lab,name=name,schema=schema,examples=rows,mode=mode,supersedes=None))
    def check(name,attempt,rows):return call(dict(op='lab_check',name=name,attempt=attempt,checks=rows))
    row=lambda x,y:dict(input=x,output=y)
    t=teach('coding','flip','list',[row([3,1,2,1],[1,2,1,3])])
    t=teach('coding','flip','list',[row([0,2,1,1],[1,1,2,0])])
    check('flip',t['attempt'],[row([4,0,4,2],[2,4,0,4])])
    reused=call(dict(op='lab_run',lab='reasoning',name='flip',input=[5,2,3]));assert reused['output']==[3,2,5]
    objects=examples();t=teach('language','glim','predicate',[row(objects[i],i in (0,4)) for i in (0,4,1,6,15)])
    check('glim',t['attempt'],[row(objects[2],True),row(objects[12],False)])
    moved=call(dict(op='lab_command',text='move glim right'));assert moved['status']=='acted'
    goal=call(dict(op='lab_goal',reference='glim',x=1,y=1));assert goal['status']=='acted'
    t=teach('world','nudge','motion',[row(dict(x=1,y=1),dict(x=2,y=1)),row(dict(x=2,y=2),dict(x=3,y=2))])
    check('nudge',t['attempt'],[row(dict(x=0,y=3),dict(x=1,y=3))])
    moved=call(dict(op='lab_world_skill',name='nudge',reference='glim'));assert moved['status']=='acted'
    pair=lambda a,c:dict(first=objects[a],second=objects[c])
    t=teach('reasoning','lefter','relation',[row(pair(0,3),True),row(pair(6,2),True)])
    check('lefter',t['attempt'],[row(pair(1,4),True),row(pair(4,1),False)])
    relation=call(dict(op='lab_run',lab='language',name='lefter',input=pair(2,5)));assert relation['output'] is True
    snapshot=s.snapshot();restored=Session.restore(snapshot);assert restored.snapshot()==snapshot
    return dict(kind='authored_engineering_demo_not_scientific_evidence',scientific=False,wall_s=time.perf_counter()-start,
        trace=trace,state=b.inspect(),snapshot=snapshot,restore_exact=True,authored_actions=s.counts['sandbox_actions'],
        new_scientific_environment_interactions=0,scientific_training_runs=0,ledger_unchanged=dict(used_s=1943.6321034559958,remaining_s=1656.3678965440042))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Refuse to overwrite a previous demo.')
    r=demo();a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(json.dumps({k:r[k] for k in ('kind','scientific','wall_s','restore_exact','authored_actions','new_scientific_environment_interactions')}))
