"""Matched-budget search methods wrapping the Evolution-1 proposers."""
from __future__ import annotations
import random
from nexus.evolution1.catalogue import ContractError, Rule, Generator, HORIZONS
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import (AdaptiveProposer, FixedProposer, RandomProposer,
                                       TrainingFeedback, VARIANTS)


class MethodError(ContractError):
    pass


class PersistentAdaptive:
    """Retains Evolution-1 linear weights across training tasks."""
    name = 'persistent_adaptive'
    resets = False

    def __init__(self, seed=7):
        self.inner = AdaptiveProposer(seed=seed)
        self.inner.name = self.name
        self._frozen = None

    def choose(self, available, context):
        return self.inner.choose(available, context)

    def update(self, feedback, context):
        self.inner.update(feedback, context)

    def learned_state(self):
        return self.inner.learned_state()

    def reset_task(self):
        return None

    def freeze(self):
        self._frozen = dict(weights=tuple(self.inner._weights),
                            updates=int(self.inner._updates),
                            tie_rank=dict(self.inner._tie_rank))
        return self._frozen

    def eval_clone(self, *, local_updates):
        if self._frozen is None:
            raise MethodError('persistent_not_frozen')
        clone = PersistentAdaptive()
        clone.inner._weights = tuple(self._frozen['weights'])
        clone.inner._updates = int(self._frozen['updates'])
        clone.inner._tie_rank = dict(self._frozen['tie_rank'])
        clone.inner._feedback_seen = set()
        clone._allow_local = bool(local_updates)
        return clone

    def update_eval(self, feedback, context):
        if getattr(self, '_allow_local', False):
            self.inner.update(feedback, context)


class ResetAdaptive:
    """Learns within a task, then discards weights before the next task."""
    name = 'reset_adaptive'
    resets = True

    def __init__(self, seed=7):
        self.seed = int(seed)
        self.inner = AdaptiveProposer(seed=self.seed)
        self.inner.name = self.name

    def choose(self, available, context):
        return self.inner.choose(available, context)

    def update(self, feedback, context):
        self.inner.update(feedback, context)

    def learned_state(self):
        return self.inner.learned_state()

    def reset_task(self):
        seen = set()
        tie = dict(self.inner._tie_rank)
        rng_state = self.inner._rng.getstate()
        self.inner = AdaptiveProposer(seed=self.seed)
        self.inner.name = self.name
        self.inner._tie_rank = tie
        self.inner._rng.setstate(rng_state)
        self.inner._feedback_seen = seen
        return self.inner.learned_state()

    def eval_clone(self, *, local_updates):
        clone = ResetAdaptive(seed=self.seed)
        clone.inner._tie_rank = dict(self.inner._tie_rank)
        clone._allow_local = bool(local_updates)
        return clone

    def update_eval(self, feedback, context):
        if getattr(self, '_allow_local', False):
            self.inner.update(feedback, context)


class StatelessWrapper:
    resets = False

    def __init__(self, inner):
        self.inner = inner

    @property
    def name(self):
        return self.inner.name

    def choose(self, available, context):
        return self.inner.choose(available, context)

    def update(self, feedback, context):
        self.inner.update(feedback, context)

    def learned_state(self):
        return self.inner.learned_state()

    def reset_task(self):
        return None

    def eval_clone(self, *, local_updates):
        return self

    def update_eval(self, feedback, context):
        return None


class EvolutionarySearch:
    """Equal-budget within-task mutation. Population 4, tournament 2.

    Does not persist fitness across tasks. Crossover is forbidden.
    """
    name = 'evolutionary'
    resets = True
    population_size = 4
    tournament_size = 2

    def __init__(self, seed=7):
        if type(seed) is not int or not 0 <= seed <= 10**9:
            raise MethodError('invalid_seed')
        self._rng = random.Random(seed)
        self._feedback_seen = set()
        self.parent = None
        self.best_score = -1.0
        self.population = []

    def learned_state(self):
        return {'parent': None if self.parent is None else self.parent.fingerprint,
                'best_score': self.best_score, 'updates': len(self._feedback_seen),
                'population': len(self.population)}

    def reset_task(self):
        self.parent = None
        self.best_score = -1.0
        self._feedback_seen = set()
        self.population = []
        return self.learned_state()

    def _mutate(self, variant):
        kind = self._rng.choice(('rule', 'generator', 'horizon'))
        if kind == 'rule':
            rule = Rule.SUCCESSOR if variant.rule is Rule.FLAT else Rule.FLAT
            return type(variant)(rule, variant.generator, variant.horizon)
        if kind == 'generator':
            gen = Generator.BALANCED if variant.generator is Generator.IID else Generator.IID
            return type(variant)(variant.rule, gen, variant.horizon)
        nxt = HORIZONS[(HORIZONS.index(variant.horizon) + 1) % len(HORIZONS)]
        return type(variant)(variant.rule, variant.generator, nxt)

    def _crossover(self, *_args, **_kwargs):
        raise MethodError('crossover_is_illegal')

    def _tournament_parent(self):
        if not self.population:
            return None
        k = min(self.tournament_size, len(self.population))
        if k == 1:
            return self.population[0][1]
        contenders = self._rng.sample(self.population, k)
        return max(contenders, key=lambda row: (row[0], row[1].fingerprint))[1]

    def choose(self, available, context):
        if type(context) is not PublicFixtureContext:
            raise MethodError('public_context_required')
        parent = self._tournament_parent()
        if parent is None:
            return available[0]
        for _ in range(16):
            mutant = self._mutate(parent)
            if mutant in available:
                return mutant
        return available[0]

    def update(self, feedback, context):
        if type(feedback) is not TrainingFeedback:
            raise MethodError('permitted_training_feedback_only')
        if feedback.event_id in self._feedback_seen:
            raise MethodError('replayed_training_feedback')
        self._feedback_seen.add(feedback.event_id)
        variant = next(v for v in VARIANTS if v.fingerprint == feedback.variant_id)
        score = 0.0 if feedback.failed else float(feedback.score)
        self.population.append((score, variant))
        self.population.sort(key=lambda row: (-row[0], row[1].fingerprint))
        self.population = self.population[: self.population_size]
        self.best_score = self.population[0][0]
        self.parent = self.population[0][1]

    def eval_clone(self, *, local_updates):
        clone = EvolutionarySearch()
        clone._rng.setstate(self._rng.getstate())
        clone.population = list(self.population)
        clone.parent = self.parent
        clone.best_score = self.best_score
        clone._allow_local = bool(local_updates)
        return clone

    def update_eval(self, feedback, context):
        if getattr(self, '_allow_local', False):
            self.update(feedback, context)


def make_methods(seed=7):
    return {
        'random': StatelessWrapper(RandomProposer(seed=seed)),
        'fixed': StatelessWrapper(FixedProposer(seed=seed)),
        'reset_adaptive': ResetAdaptive(seed=seed),
        'persistent_adaptive': PersistentAdaptive(seed=seed),
        'evolutionary': EvolutionarySearch(seed=seed),
    }
