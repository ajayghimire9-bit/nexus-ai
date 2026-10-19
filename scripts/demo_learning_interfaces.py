"""Deterministic authored illustrations, not scientific environment evidence."""
import json
from dataclasses import asdict
from nexus.core.episode_context import EpisodeContext
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2.generated_strategies import StrategyGenerator,leaf,compose
from nexus.evolution2.continual_state import TaskStream
from nexus.evolution2.full_policy_source import ROOT


def examples():
    generator=StrategyGenerator(7,mutation_credit=True);parent=leaf(VARIANTS[0]);child=compose('switch',VARIANTS[0],VARIANTS[-1],.25)
    common=dict(kind='observed_full_policy_return',phase='training',pair_id='AUTHORED_FIXTURE',context_hash=digest('fixture'),reset_seed=1,planner_seed=2,horizon=200,planning_cap=1536,cpu_s=.1)
    before=generator.mutation_probabilities()
    generator.observe_mutation(parent,child,{**common,'strategy':parent.fingerprint,'return':0.,'event':'fixture_parent'},
                               {**common,'strategy':child.fingerprint,'return':100.,'event':'fixture_child'})
    events=[dict(kind='synthetic_mutation_illustration',probabilities_before=before,probabilities_after=generator.mutation_probabilities(),
                 lineage=[asdict(e) for e in generator.journal.snapshot()])]
    rewards={'A':{'test_challenger':1.,'gather_evidence':0.,'refine_strategy':2.},
             'B':{'test_challenger':0.,'gather_evidence':0.,'refine_strategy':2.},
             'C':{'test_challenger':0.,'gather_evidence':2.,'refine_strategy':-3.}}
    for control in ('persistent','reset','shuffled'):
        for schedule in ('adaptive','random','fixed'):
            stream=TaskStream(7,max_choices=8,control=control,schedule=schedule);trace=[]
            for i,task in enumerate(('A','B','A','C')):
                stream.begin_task(task,EpisodeContext(1,3))
                for j in range(2):
                    action=stream.choose_experiment()
                    if action=='stop':trace.append(dict(task=task,action=action));continue
                    gain=rewards[task][action];stream.reveal(event=f'{i}:{j}',observed_return_gain=gain,cpu_s=.1)
                    trace.append(dict(task=task,action=action,authored_gain=gain,authored_cost=.1))
            events.append(dict(kind='synthetic_task_stream',control=control,schedule=schedule,trace=trace,
                               authored_gain_sum=sum(r.get('authored_gain',0) for r in trace)))
    return dict(kind='synthetic_contract',scientific=False,new_environment_steps=0,neural_inference=0,
                note='Returns and costs are authored fixtures, not measured environment performance or actual CPU cost.',events=events)


if __name__=='__main__':
    path=ROOT/'artifacts/e3_8_interface_examples.json'
    with path.open('x') as out:json.dump(examples(),out,allow_nan=False,indent=2);out.write('\n')
    print(path)
