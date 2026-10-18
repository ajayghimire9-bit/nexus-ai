"""Deterministic synthetic task families. Scores are authored, not H12–H17 returns."""
from __future__ import annotations
from dataclasses import dataclass
from nexus.evolution1.catalogue import ContractError, Variant, catalogue, digest
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import VARIANTS, features

MODE = 'synthetic_only'
SCIENTIFIC = False
LEVEL_TESTED = 2
CLAIMS = dict(self_improvement=False, level3_operator_discovery=False,
              level4_meta_meta=False, real_environment=False)
PROPOSALS = 4
SHARED_PROBES = 2
HOLDOUT_FAMILY = 'holdout_horizon'
TRAIN_FAMILIES = ('successor_scale', 'horizon_scale', 'balanced_scale')
DEV_FAMILY = 'successor_dev'
SHIFTED_FAMILY = 'inverted_successor'


def _clip(value):
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class SyntheticTask:
    """One authored lookup table plus public context. Hidden weights stay private."""
    family: str
    instance: int
    role: str
    context: PublicFixtureContext
    mode: str = MODE
    scientific: bool = SCIENTIFIC

    def __post_init__(self):
        if self.family not in FAMILY_SPEC:
            raise ContractError('unknown_synthetic_family')
        if type(self.instance) is not int or not 0 <= self.instance <= 99:
            raise ContractError('invalid_task_instance')
        if self.role not in ('train', 'development', 'shifted', 'holdout'):
            raise ContractError('invalid_task_role')
        if self.mode != MODE or self.scientific is not False:
            raise ContractError('synthetic_tasks_only')

    @property
    def task_id(self):
        return f'{self.family}:{self.instance}'

    def public_view(self):
        return dict(task_id=self.task_id, role=self.role, mode=MODE, scientific=False,
                    context=self.context.payload())


# Hidden family weights on (bias, S, B, h). Independent of proposer weights and
# of closed H12–H16 numerical returns. Instance 1 adds a tiny authored offset
# so two instances are distinct without changing the ranking family.
FAMILY_SPEC = {
    'successor_scale': dict(role='train', context=(16, 2, 1, 1536),
                            hidden=(0.20, 0.36, 0.06, 0.10), offset=0.01),
    'horizon_scale': dict(role='train', context=(4, 8, 1, 1536),
                          hidden=(0.18, 0.06, 0.05, 0.38), offset=0.012),
    'balanced_scale': dict(role='train', context=(8, 4, 1, 1536),
                           hidden=(0.22, -0.06, 0.34, 0.08), offset=0.008),
    'successor_dev': dict(role='development', context=(12, 3, 1, 1536),
                          hidden=(0.21, 0.33, 0.07, 0.11), offset=0.009),
    'inverted_successor': dict(role='shifted', context=(16, 2, 1, 1536),
                               hidden=(0.40, 0.05, -0.40, -0.35), offset=0.01),
    HOLDOUT_FAMILY: dict(role='holdout', context=(4, 8, 1, 1536),
                         hidden=(0.17, 0.04, 0.06, 0.40), offset=0.011),
}


def make_task(family, instance=0):
    spec = FAMILY_SPEC[family]
    ctx = PublicFixtureContext(*spec['context'])
    return SyntheticTask(family, int(instance), spec['role'], ctx)


def hidden_score(task, variant):
    """Evaluator-only oracle. Must not be passed into a proposer."""
    if type(task) is not SyntheticTask or type(variant) is not Variant:
        raise ContractError('invalid_oracle_args')
    spec = FAMILY_SPEC[task.family]
    s = float(variant.rule.value == 'successor')
    b = float(variant.generator.value == 'balanced_first_action')
    h = variant.horizon / 16.0
    w0, ws, wb, wh = spec['hidden']
    raw = w0 + ws * s + wb * b + wh * h + spec['offset'] * (task.instance + 1)
    return _clip(raw)


def oracle_table(task):
    return {v.fingerprint: hidden_score(task, v) for v in VARIANTS}


def oracle_best(task):
    table = oracle_table(task)
    best_id = max(table, key=table.get)
    return best_id, table[best_id]


def default_split():
    """Training/dev/shifted only. Holdout exists but is not consumed here."""
    train = tuple(make_task(name, i) for name in TRAIN_FAMILIES for i in (0, 1))
    development = (make_task(DEV_FAMILY, 0), make_task(DEV_FAMILY, 1))
    shifted = (make_task(SHIFTED_FAMILY, 0), make_task(SHIFTED_FAMILY, 1))
    holdout = (make_task(HOLDOUT_FAMILY, 0),)
    return dict(train=train, development=development, shifted=shifted, holdout=holdout)


def split_digest(split):
    payload = {role: [t.public_view() for t in tasks] for role, tasks in split.items()}
    return digest(payload)


def public_feature_matrix(task):
    """Public features only. Hidden family weights are not included."""
    return {v.fingerprint: features(v, task.context) for v in catalogue()}
