"""Bounded fixture integration over existing generator, stream and E1 gate.

Not a real-world evaluator or arbitrary self-modifying program. Utilities and
cost units are authored fixtures, never environmental returns or CPU seconds.
"""
from copy import deepcopy
from dataclasses import asdict
import math
import random
from nexus.core.episode_context import EpisodeContext
from nexus.evolution1.catalogue import digest
from nexus.evolution1.fixtures import FixtureCost,Journal
from nexus.evolution1.toy_loop import VARIANTS,CONTEXT,TEST_KEY
from nexus.evolution1.promotion import FixtureSnapshot,FixtureAuditor,FixturePromotionHarness
from nexus.evolution2.continual_state import TaskStream
from nexus.evolution2.generated_strategies import leaf,compose
from nexus.meta.controller import EpsilonGreedyController

RULES=('mean','recent','conservative')
METHODS=('unified','generation_only','random_generation','fixed_generation','reset_memory','shuffled_memory',
         'random_schedule','fixed_schedule','fixed_update','random_update','shuffled_feedback')


def finite(v):
    if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('finite_fixture_number')
    return float(v)


class FixtureHost:
    """Trusted, finite authored utility table; no worlds/model calls/file writes.

    Does NOT execute a strategy in a simulator. Planner executability has
    separate adapter tests; these utilities are functional learning examples.
    """
    def __init__(self,seed,max_calls=256):
        if type(seed) is not int or not 0<=seed<10000 or type(max_calls) is not int or not 1<=max_calls<=1024:raise ValueError('fixture_host_limits')
        self.seed=seed;self.max_calls=max_calls;self.calls=0;self.failures=0

    def evaluate(self,strategy,task,phase):
        if self.calls>=self.max_calls:raise ValueError('fixture_evaluation_cap')
        self.calls+=1  # Failed/invalid evaluations are not refunded.
        if phase not in ('training','development','audit','query') or task not in ('A','B','C','D','E','F'):raise ValueError('fixture_task_phase')
        strategy.bound([.4,0.,0.],3)
        family=random.Random(int(digest([self.seed,task])[:12],16))
        base=family.uniform(-.5,.5);switch=family.uniform(-1.,1.);blend=family.uniform(-1.,1.)
        # Independent phase perturbations allow development/audit reversals.
        noise=random.Random(int(digest([self.seed,task,phase,strategy.fingerprint])[:12],16)).uniform(-.15,.15)
        value=base+.05*strategy.left.horizon/16
        if strategy.kind=='switch':value+=switch+.05*strategy.right.horizon/16
        elif strategy.kind=='rank_blend':value+=blend+.05*strategy.right.horizon/16
        return finite(value+noise)


class LearningCycle:
    """One bounded policy with retained feedback; public API cannot reveal queries.

    This is an adapter, not a second learner or memory database. Independent
    assessment stays in the trusted host and never updates proposal statistics.
    """
    def __init__(self,seed=7,method='unified',max_choices=16,*,objective='historical_pair_gain'):
        if method not in METHODS or type(max_choices) is not int or not 1<=max_choices<=32:raise ValueError('bounded_cycle_settings')
        if objective not in ('historical_pair_gain','training_incumbent_progress_v1'):raise ValueError('versioned_fixture_objective')
        self.objective=objective;self.training_incumbents={};self.discovery_seen=set()
        self.seed=seed;self.method=method;self.rng=random.Random(seed)
        self.stream=TaskStream(seed,max_choices=max_choices,control={'reset_memory':'reset','shuffled_memory':'shuffled'}.get(method,'persistent'),schedule={'random_schedule':'random','fixed_schedule':'fixed','generation_only':'fixed','random_generation':'fixed','fixed_generation':'fixed'}.get(method,'adaptive'))
        self.stream.generator.adaptive=method!='random_generation'
        self.rules=EpsilonGreedyController(epsilon=0.);self.journal=Journal();self.trace=[]
        self.rule_frozen=False;self.charged=FixtureCost(0,0,0);self.cap=FixtureCost(0,0,2*max_choices)
        self.incumbent=leaf(VARIANTS[2]);self.training_parent=self.incumbent;self.archive={};self.rule_history=[]
        if objective=='training_incumbent_progress_v1':self.cap=FixtureCost(0,0,3*max_choices)
        initial=self.snapshot(self.incumbent);self.gate=FixturePromotionHarness(initial,TEST_KEY);self.archive[initial.fingerprint]=self.incumbent

    def snapshot(self,strategy):
        return FixtureSnapshot(strategy.left.fingerprint,digest(self.rng.getstate()),strategy.fingerprint,
            digest(dict(mutation=self.stream.generator.mutation_stats,rates=self.stream.rates)))

    def select_rule(self):
        if self.rule_frozen:return self.selected_rule
        if self.method in ('fixed_update','generation_only','random_generation','fixed_generation'):return 'mean'
        if self.method=='random_update':return self.rng.choice(RULES)
        unseen=[r for r in RULES if not self.rules.kind_n.get(r)]
        return unseen[0] if unseen else max(RULES,key=lambda r:self.rules.kind_sum[r]/self.rules.kind_n[r])

    def begin_task(self,task):
        self.stream.begin_task(task,EpisodeContext(3,3));self.stream.generator.adaptive=self.method!='random_generation'
        if self.method=='reset_memory' and not self.rule_frozen:self.rules=EpsilonGreedyController(epsilon=0.)
        rule=self.select_rule();self.stream.generator.mutation_rule=rule
        self.stream.generator.mutation_exploration=.1 if rule=='recent' else 0.
        self.rule_history.append(rule);self.journal.append('task_started',dict(task=task,rule=rule));return rule

    def freeze_rule(self):
        tried=[r for r in RULES if self.rules.kind_n.get(r)]
        self.selected_rule=max(tried,key=lambda r:self.rules.kind_sum[r]/self.rules.kind_n[r]) if tried else 'mean'
        if self.method in ('fixed_update','generation_only','random_generation','fixed_generation'):self.selected_rule='mean'
        if self.method=='random_update':self.selected_rule=self.rng.choice(RULES)
        self.rule_frozen=True;return self.selected_rule

    def transfer_copy(self):
        clone=deepcopy(self);clone.freeze_rule();clone.stream.remaining=12;clone.stream.choices=0
        clone.trace=[];clone.rule_history=[];clone.charged=FixtureCost(0,0,0);clone.cap=FixtureCost(0,0,36 if self.objective=='training_incumbent_progress_v1' else 24)
        return clone

    def accept_training_pair(self,parent,child,p,c):
        """Public feedback boundary: no dev/query labels accepted."""
        return self.stream.generator.observe_mutation(parent,child,p,c,return_scale=1.,domain='synthetic_fixture')

    def assess(self,child,host,task):
        # A separate development gate chooses deployed incumbent; values never
        # enter the generator/rule-controller update paths.
        old=host.evaluate(self.incumbent,task,'development');new=host.evaluate(child,task,'development')
        before=self.gate.incumbent
        if new-old<.05:return dict(promoted=False,rolled_back=False)
        candidate=self.snapshot(child);self.archive[candidate.fingerprint]=child
        head=self.journal.snapshot()[-1].fingerprint
        audit=FixtureAuditor(TEST_KEY).attest(candidate,head,'pass')
        self.gate.promote_for_test(candidate,head,audit);self.incumbent=child
        # An independent audit can undo a development promotion.
        prior_strategy=self.archive[before.fingerprint]
        if host.evaluate(child,task,'audit')<host.evaluate(prior_strategy,task,'audit'):
            previous=self.gate.rollback_for_test();self.incumbent=self.archive[previous.fingerprint]
            return dict(promoted=True,rolled_back=True)
        return dict(promoted=True,rolled_back=False)

    def step(self,host,task):
        action=self.stream.choose_experiment()
        if action=='stop':return None
        cost_units=3 if self.objective=='training_incumbent_progress_v1' else 2
        cost=FixtureCost(0,0,cost_units)
        if not self.charged.plus(cost).fits(self.cap):raise ValueError('fixture_cost_cap')
        self.charged=self.charged.plus(cost)
        # Failed attempts consume choices too; resume must not replay their IDs.
        event=f'{self.stream.choices-1}:{task}';g=self.stream.generator
        before=dict(g.mutation_probabilities())
        try:
            if action=='gather_evidence':
                parent=leaf(VARIANTS[2]);child=self.training_parent
            elif self.method=='fixed_generation':
                parent=leaf(VARIANTS[2]);child=compose('switch',VARIANTS[2],VARIANTS[8],.25)
            elif action=='refine_strategy':
                parent=leaf(self.training_parent.left);kind=self.rng.choices(tuple(g.mutation_stats),weights=tuple(g.mutation_probabilities().values()))[0]
                other=self.rng.choice(tuple(v for v in VARIANTS if v!=parent.left));child=compose(kind,parent.left,other,.25)
            else:
                child=g.propose(CONTEXT);parent=leaf(child.left)
            parent_value=host.evaluate(parent,task,'training');child_value=host.evaluate(child,task,'training')
            gain=child_value-parent_value
            progress=None
            if self.objective=='training_incumbent_progress_v1':
                # Training incumbent is separate from independently gated deployment.
                # No development/audit values OR gate outcomes enter this objective.
                accepted=self.training_incumbents.get(task,leaf(VARIANTS[2]))
                accepted_value=(parent_value if accepted==parent else child_value if accepted==child
                    else host.evaluate(accepted,task,'training'))
                key=(task,child.fingerprint);novel=key not in self.discovery_seen
                improved=action!='gather_evidence' and child_value>accepted_value
                self.discovery_seen.add(key)
                if improved:self.training_incumbents[task]=child
                progress=dict(previous=accepted.fingerprint,accepted=(child if improved else accepted).fingerprint,
                    previous_training_utility=accepted_value,accepted_training_utility=max(accepted_value,child_value) if improved else accepted_value,
                    novel=novel,discovery_gain=child_value-accepted_value if improved and novel else 0.)
            if action!='gather_evidence' and gain>0:self.training_parent=child
            if action!='gather_evidence':
                common=dict(kind='synthetic_fixture_utility',phase='training',pair_id=event,context_hash=digest(task),reset_seed=self.seed,planner_seed=self.seed+len(self.trace),horizon=1,planning_cap=1536,cpu_s=1.)
                p={**common,'strategy':parent.fingerprint,'return':parent_value,'event':'p'+event}
                c={**common,'strategy':child.fingerprint,'return':child_value,'event':'c'+event}
                if self.method=='shuffled_feedback':p['return'],c['return']=c['return'],p['return']
                self.accept_training_pair(parent,child,p,c)
            # Evidence measures incumbent-vs-anchor utility, never invents a
            # counterfactual strategy improvement for a passive measurement.
            effective_gain=gain if action!='gather_evidence' else 0.
            if progress is not None:effective_gain=progress['discovery_gain']
            self.stream.reveal(event=event,observed_return_gain=effective_gain,cpu_s=float(cost_units),domain='synthetic_fixture')
            if not self.rule_frozen:self.rules.update((),g.mutation_rule,effective_gain/cost_units)
            self.journal.append('training_attempt',dict(task=task,action=action,parent=parent.payload(),child=child.payload(),
                parent_utility=parent_value,child_utility=child_value,domain='synthetic_fixture',cost_units=cost_units))
            proposal_after=dict(g.mutation_probabilities())
            gate=self.assess(child,host,task) if action!='gather_evidence' else dict(promoted=False,rolled_back=False)
            row=dict(event=event,task=task,action=action,rule=g.mutation_rule,gain=gain,effective_gain=effective_gain,
                parent=parent.fingerprint,child=child.fingerprint,before=before,after=proposal_after,**gate)
            if progress is not None:row['training_progress']=progress;row['objective']=self.objective
            self.trace.append(row);return row
        except BaseException:
            if self.stream.pending is not None:self.stream.reveal(event=event,observed_return_gain=0.,cpu_s=float(cost_units),failed=True,domain='synthetic_fixture')
            self.journal.append('failed_attempt',dict(event=event,charged_units=cost_units));raise

    def probe(self,host,task,count=8):
        """Frozen proposal assessment; even RNG changes stay outside learner."""
        g=deepcopy(self.stream.generator);values=[]
        for _ in range(count):
            child=compose('switch',VARIANTS[2],VARIANTS[8],.25) if self.method=='fixed_generation' else g.propose(CONTEXT)
            values.append(host.evaluate(child,task,'query'))
        return sum(values)/count

    def run(self,host,tasks=('A','B','A','C'),steps_per_task=4):
        if tuple(tasks) not in (('A','B','A','C'),('D','E','F')) or type(steps_per_task) is not int or not 1<=steps_per_task<=4:raise ValueError('registered_fixture_stream')
        probes=[];journal_start=len(self.journal.snapshot())
        for task in tasks:
            self.begin_task(task);before=self.probe(host,task)
            for _ in range(steps_per_task):
                if self.step(host,task) is None:break
            deployed=host.evaluate(self.incumbent,task,'query')-host.evaluate(leaf(VARIANTS[2]),task,'query')
            probes.append(dict(task=task,before=before,after=self.probe(host,task),retained_A=self.probe(host,'A'),deployed_gain=deployed))
        return dict(kind='authored_fixture_not_environment_evidence',method=self.method,seed=self.seed,trace=deepcopy(self.trace),
            probes=probes,fixture_calls=host.calls,declared_training_cost_units=self.charged.cpu_units,
            gain=sum(r['effective_gain'] for r in self.trace),policy=self.stream.generator.mutation_probabilities(),
            rule_history=self.rule_history[:],journal=[asdict(e) for e in self.journal.snapshot()],
            journal_start_event=journal_start,
            gate_events=self.gate.events,incumbent=self.incumbent.payload(),new_real_steps=0,model_inference=0)
