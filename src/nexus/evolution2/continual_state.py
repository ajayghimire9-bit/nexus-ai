"""Bounded state machine using the existing generator, proposer and journal.

This does not execute experiments or replace ContextualStrategyMemory.
"""
import math
import random
from dataclasses import asdict
from nexus.evolution2.generated_strategies import StrategyGenerator
from nexus.evolution1.fixtures import Journal
from nexus.meta.controller import EpsilonGreedyController


class TaskStream:
    ACTIONS=('test_challenger','gather_evidence','refine_strategy')
    def __init__(self,seed=7,*,max_choices=12,control='persistent',schedule='adaptive',mutation_rule='mean',mutation_exploration=0.):
        if type(max_choices) is not int or max_choices<1 or control not in ('persistent','reset','shuffled') or schedule not in ('adaptive','random','fixed'):raise ValueError('bounded_stream')
        self.schedule=schedule;self.choices=0
        self.seed=seed;self.control=control;self.remaining=max_choices;self.rng=random.Random(seed)
        self.generator=StrategyGenerator(seed,mutation_credit=True,mutation_rule=mutation_rule,mutation_exploration=mutation_exploration)
        self.journal=Journal()
        self.controller=EpsilonGreedyController(epsilon=0.)
        self.rates={a:[0.,0] for a in self.ACTIONS};self.pending=None;self.task=None;self.events=set()

    @property
    def rates(self):
        return {a:[self.controller.kind_sum.get(a,0.),self.controller.kind_n.get(a,0)] for a in self.ACTIONS}

    @rates.setter
    def rates(self,values):
        for action,(total,count) in values.items():
            self.controller.kind_sum[action]=total;self.controller.kind_n[action]=count

    def begin_task(self,task,episode_context):
        if self.pending is not None:raise ValueError('settle_previous_choice')
        if self.control=='reset':
            self.journal.append('generator_archived',dict(events=[asdict(e) for e in self.generator.journal.snapshot()]))
            self.generator=StrategyGenerator(self.seed,mutation_credit=True,mutation_rule=self.generator.mutation_rule,mutation_exploration=self.generator.mutation_exploration);self.rates={a:[0.,0] for a in self.ACTIONS}
        elif self.control=='shuffled':
            values=list(self.rates.values());self.rng.shuffle(values);self.rates=dict(zip(self.ACTIONS,values))
            values=list(self.generator.mutation_stats.values());self.rng.shuffle(values)
            self.generator.mutation_stats=dict(zip(self.generator.mutation_stats,values))
        episode_context.reset_episode(task);self.task=task
        self.journal.append('task_started',dict(task=task,control=self.control,remaining=self.remaining))

    def choose_experiment(self):
        if self.pending is not None:raise ValueError('one_pending_choice')
        if self.task is None or self.remaining<=0:return 'stop'
        unseen=[a for a in self.ACTIONS if self.rates[a][1]==0]
        action=unseen[0] if unseen else max(self.ACTIONS,key=lambda a:self.rates[a][0]/self.rates[a][1])
        if self.schedule=='random':action=self.rng.choice(self.ACTIONS)
        elif self.schedule=='fixed':action=self.ACTIONS[self.choices%len(self.ACTIONS)]
        elif not unseen and self.rates[action][0]/self.rates[action][1]<=0:return 'stop'
        self.pending=action;self.remaining-=1;self.choices+=1;return action

    def reveal(self,*,event,observed_return_gain,cpu_s,phase='training',failed=False,domain='real_environment'):
        if domain not in ('real_environment','synthetic_fixture'):raise ValueError('feedback_domain')
        if self.pending is None or event in self.events or phase!='training':raise ValueError('unique_pending_training_feedback')
        if type(event) is not str or not event or type(failed) is not bool or type(observed_return_gain) not in (int,float) or not math.isfinite(observed_return_gain) or type(cpu_s) not in (int,float) or not math.isfinite(cpu_s) or cpu_s<=0:raise ValueError('measured_return_per_cost')
        action=self.pending;rate=0. if failed else observed_return_gain/cpu_s
        if not math.isfinite(rate):raise ValueError('finite_return_rate')
        self.controller.update((),action,rate);self.events.add(event);self.pending=None
        self.journal.append('experiment_feedback',dict(task=self.task,action=action,event=event,
            observed_return_gain=observed_return_gain,cpu_s=cpu_s,failed=failed,phase=phase,domain=domain))
