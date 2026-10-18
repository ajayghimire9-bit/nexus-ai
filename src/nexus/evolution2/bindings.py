"""Explicit family bindings. Metadata and fixtures only; no env or model load.

Family is never inferred from observation size or action count.
"""
from dataclasses import asdict, dataclass
import math

from nexus.evolution1.catalogue import (
    ContractError, Generator, Rule, Variant, canonical, catalogue, digest, plan_bound,
    positive_int,
)
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.resources import Work


FAMILIES = ('pendulum', 'acrobot', 'mountaincar', 'mountaincar_continuous')
ACTION_KINDS = ('continuous_scalar', 'native_discrete_index')
SCIENTIFIC = False
MODE = 'synthetic_fixture'
REQUEST_SCHEMA = 'nexus.evolution2.evaluator_request.v1'
RESPONSE_SCHEMA = 'nexus.evolution2.evaluator_response.v1'
REQUEST_KEYS = frozenset({
    'schema', 'request_id', 'family', 'variant_id', 'binding_fingerprint',
    'checkpoint_id', 'world_model_id', 'context', 'mode',
})
RESPONSE_KEYS = frozenset({
    'schema', 'request_id', 'variant_id', 'score', 'failed', 'event_id',
})
MAX_MESSAGE = 4096
BY_ID = {v.fingerprint: v for v in catalogue()}


def _hex64(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ContractError('invalid_identity_hash')
    return value


def fixture_checkpoint(family):
    if type(family) is not str or family not in FAMILIES:
        raise ContractError('unknown_family')
    return digest({'family': family, 'kind': 'evolution2_fixture_checkpoint', 'rev': 1})


def fixture_world_model(family):
    if type(family) is not str or family not in FAMILIES:
        raise ContractError('unknown_family')
    return f'residual_mlp_2x64_{family}_fixture'


def operator_fingerprint(family, variant):
    if type(family) is not str or family not in FAMILIES:
        raise ContractError('unknown_family')
    if type(variant) is not Variant:
        raise ContractError('invalid_variant')
    if variant.generator is Generator.BALANCED:
        path = 'src/nexus/evolution2/planner_adapter.py'
        symbol = 'generate_candidates'
    elif family == 'pendulum':
        path = 'src/nexus/world/bellman_backup_control.py'
        symbol = 'lookahead_first_action' if variant.rule is Rule.SUCCESSOR else '_score_open_loop'
    elif variant.rule is Rule.SUCCESSOR:
        path = f'src/nexus/world/{family}_lookahead.py'
        symbol = 'lookahead_first_action'
    else:
        path = 'src/nexus/world/planning.py'
        symbol = 'RandomShootingMPC._score_batch'
    return digest({'path': path, 'symbol': symbol, 'variant': variant.fingerprint, 'family': family})


@dataclass(frozen=True)
class FamilyBinding:
    family: str
    observation_layout: tuple
    action_kind: str
    action_values: tuple
    reward_symbol: str
    reward_timing: str
    root_survival: str
    wrapper_chain: tuple
    world_model_id: str
    checkpoint_id: str
    truncation: str = 'time_limit'
    goal_termination: str = 'disabled'
    tail_survival: str = 'cumulative_before_reward'
    episode_steps: int = 200

    def __post_init__(self):
        if type(self.family) is not str or self.family not in FAMILIES:
            raise ContractError('unknown_family')
        if (type(self.observation_layout) is not tuple or not self.observation_layout
                or any(type(x) is not str or not x for x in self.observation_layout)):
            raise ContractError('invalid_observation_layout')
        if self.action_kind not in ACTION_KINDS:
            raise ContractError('unsupported_action_decoding')
        if type(self.action_values) is not tuple or not self.action_values:
            raise ContractError('invalid_action_values')
        if self.action_kind == 'native_discrete_index':
            if self.action_values != tuple(range(len(self.action_values))):
                raise ContractError('unsupported_action_decoding')
            if any(type(x) is not int for x in self.action_values):
                raise ContractError('unsupported_action_decoding')
        else:
            if any(type(x) is not float or not math.isfinite(x) or not -10 <= x <= 10
                   for x in self.action_values):
                raise ContractError('unsupported_action_decoding')
        if type(self.wrapper_chain) is not tuple or any(type(x) is not str for x in self.wrapper_chain):
            raise ContractError('invalid_wrapper_chain')
        for value in (self.reward_symbol, self.reward_timing, self.root_survival,
                      self.tail_survival, self.goal_termination, self.truncation,
                      self.world_model_id):
            if type(value) is not str or not value:
                raise ContractError('invalid_adapter_metadata')
        if self.goal_termination != 'disabled' or self.truncation != 'time_limit':
            raise ContractError('unsupported_termination_semantics')
        if self.world_model_id != fixture_world_model(self.family):
            raise ContractError('incompatible_checkpoint')
        _hex64(self.checkpoint_id)
        if self.checkpoint_id != fixture_checkpoint(self.family):
            raise ContractError('incompatible_checkpoint')
        positive_int(self.episode_steps, 200)

    @property
    def obs_dim(self):
        return len(self.observation_layout)

    @property
    def n_actions(self):
        return len(self.action_values)

    @property
    def fingerprint(self):
        return digest(asdict(self))


def reviewed_binding(family):
    if type(family) is not str or family not in FAMILIES:
        raise ContractError('unknown_family')
    ckpt = fixture_checkpoint(family)
    model = fixture_world_model(family)
    if family == 'pendulum':
        return FamilyBinding(
            family, ('cos_theta', 'sin_theta', 'angular_velocity'),
            'continuous_scalar', (-2.0, 0.0, 2.0), 'pendulum_step_reward', 'current',
            'ignore_root_probability', ('DiscreteTorqueWrapper',), model, ckpt)
    if family == 'acrobot':
        return FamilyBinding(
            family, ('cos_theta1', 'sin_theta1', 'cos_theta2', 'sin_theta2',
                     'angular_velocity1', 'angular_velocity2'),
            'native_discrete_index', (0, 1, 2), 'acrobot_step_reward', 'next',
            'multiply_root_survival', ('AcrobotDenseRewardWrapper',), model, ckpt)
    if family == 'mountaincar':
        return FamilyBinding(
            family, ('position', 'velocity'), 'native_discrete_index', (0, 1, 2),
            'mountaincar_step_reward', 'next', 'multiply_root_survival',
            ('MountainCarDenseRewardWrapper',), model, ckpt)
    return FamilyBinding(
        family, ('position', 'velocity'), 'continuous_scalar', (-1.0, 0.0, 1.0),
        'mountaincar_step_reward', 'next', 'multiply_root_survival',
        ('ContinuousMountainCarGravityPatch', 'DiscreteTorqueWrapper',
         'MountainCarDenseRewardWrapper'), model, ckpt)


@dataclass(frozen=True)
class BoundEvaluation:
    binding: FamilyBinding
    variant: Variant
    operator_fingerprint: str
    declared_work: Work
    context: PublicFixtureContext
    scientific: bool = SCIENTIFIC

    def __post_init__(self):
        if type(self.binding) is not FamilyBinding or type(self.variant) is not Variant:
            raise ContractError('invalid_adapter_or_variant')
        if self.scientific is not False:
            raise ContractError('scientific_dispatch_blocked')
        if self.operator_fingerprint != operator_fingerprint(self.binding.family, self.variant):
            raise ContractError('planner_operator_mismatch')
        if type(self.declared_work) is not Work:
            raise ContractError('invalid_work')
        expected = Work(imagined_transitions=plan_bound(
            self.variant, self.binding.n_actions, self.context.imagined_cap).imagined_per_decision)
        if self.declared_work != expected:
            raise ContractError('declared_work_mismatch')

    def require_scientific(self):
        raise ContractError('scientific_dispatch_blocked')


def bind_evaluation(family, variant, *, checkpoint_id, world_model_id,
                    model_obs_dim, model_n_actions, binding=None, imagined_cap=1536):
    if type(family) is not str or family not in FAMILIES:
        raise ContractError('unknown_family')
    if type(variant) is not Variant:
        raise ContractError('invalid_variant')
    expected = reviewed_binding(family)
    if binding is None:
        binding = expected
    elif type(binding) is not FamilyBinding or canonical(asdict(binding)) != canonical(asdict(expected)):
        raise ContractError('family_semantics_mismatch')
    positive_int(model_obs_dim, 4096)
    positive_int(model_n_actions, 16)
    if (model_obs_dim, model_n_actions) != (binding.obs_dim, binding.n_actions):
        raise ContractError('model_interface_mismatch')
    if checkpoint_id != binding.checkpoint_id or world_model_id != binding.world_model_id:
        raise ContractError('incompatible_checkpoint')
    context = PublicFixtureContext(binding.n_actions, binding.obs_dim, binding.episode_steps, imagined_cap)
    declared = Work(imagined_transitions=plan_bound(
        variant, binding.n_actions, imagined_cap).imagined_per_decision)
    return BoundEvaluation(binding, variant, operator_fingerprint(family, variant), declared, context)


def derived_request_id(family, variant_id, binding_fingerprint, checkpoint_id, world_model_id, context):
    return digest({
        'family': family, 'variant': variant_id, 'binding': binding_fingerprint,
        'checkpoint': checkpoint_id, 'world_model': world_model_id,
        'context': context, 'mode': MODE,
    })


def expected_event_id(request):
    return digest({
        'request_id': request['request_id'], 'variant_id': request['variant_id'],
        'mode': MODE, 'schema': RESPONSE_SCHEMA,
    })


def validate_public_context(context, binding):
    if type(context) is not dict or set(context) != {
        'n_actions', 'obs_dim', 'episode_steps', 'imagined_cap',
    }:
        raise ContractError('invalid_context')
    positive_int(context['n_actions'], 16)
    positive_int(context['obs_dim'], 4096)
    positive_int(context['episode_steps'], 200)
    positive_int(context['imagined_cap'], 1536)
    if (context['n_actions'], context['obs_dim'], context['episode_steps']) != (
            binding.n_actions, binding.obs_dim, binding.episode_steps):
        raise ContractError('model_interface_mismatch')


def validate_public_payload(data):
    """Shared host/worker check. Does not authorize scientific dispatch."""
    if type(data) is not dict or set(data) != REQUEST_KEYS:
        raise ContractError('unexpected_request_fields')
    if data['schema'] != REQUEST_SCHEMA or data['mode'] != MODE:
        raise ContractError('invalid_request_schema')
    if data['family'] not in FAMILIES:
        raise ContractError('unknown_family')
    for key in ('request_id', 'variant_id', 'binding_fingerprint', 'checkpoint_id'):
        _hex64(data[key])
    if type(data['world_model_id']) is not str or not data['world_model_id']:
        raise ContractError('incompatible_checkpoint')
    if data['variant_id'] not in BY_ID:
        raise ContractError('unknown_variant')
    variant = BY_ID[data['variant_id']]
    binding = reviewed_binding(data['family'])
    if data['binding_fingerprint'] != binding.fingerprint:
        raise ContractError('family_semantics_mismatch')
    if data['checkpoint_id'] != binding.checkpoint_id or data['world_model_id'] != binding.world_model_id:
        raise ContractError('incompatible_checkpoint')
    validate_public_context(data['context'], binding)
    expected = derived_request_id(
        data['family'], data['variant_id'], data['binding_fingerprint'],
        data['checkpoint_id'], data['world_model_id'], data['context'])
    if data['request_id'] != expected:
        raise ContractError('request_identity_mismatch')
    return variant, binding
