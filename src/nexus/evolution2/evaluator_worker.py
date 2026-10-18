"""Process-separated synthetic fixture worker. Not a planner or sandbox.

Reads one public JSON request on stdin and writes one JSON response on stdout.
Hidden Evolution-2 family scores and host ledgers are not imported.
"""
from __future__ import annotations
import json
import os
import sys
import time

from nexus.evolution1.catalogue import ContractError, Rule, catalogue, digest
from nexus.evolution2.bindings import FAMILIES, MODE, reviewed_binding


SCHEMA = 'nexus.evolution2.evaluator_response.v1'
REQUEST_SCHEMA = 'nexus.evolution2.evaluator_request.v1'
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


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ContractError('duplicate_field')
        out[key] = value
    return out


def _nonfinite(_):
    raise ContractError('nonfinite_json')


def stub_score(variant):
    successor = 1.0 if variant.rule is Rule.SUCCESSOR else 0.0
    return max(0.0, min(1.0, 0.25 + 0.5 * (variant.horizon / 16.0) + 0.1 * successor))


def parse_request(raw):
    if type(raw) is not bytes or not raw or len(raw) > MAX_MESSAGE:
        raise ContractError('invalid_or_oversized_request')
    try:
        text = raw.decode('utf-8')
        data = json.loads(text, object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (ValueError, TypeError, RecursionError, UnicodeDecodeError) as exc:
        raise ContractError('invalid_json') from exc
    if type(data) is not dict or set(data) != REQUEST_KEYS:
        raise ContractError('unexpected_request_fields')
    if data['schema'] != REQUEST_SCHEMA or data['mode'] != MODE:
        raise ContractError('invalid_request_schema')
    if data['family'] not in FAMILIES:
        raise ContractError('unknown_family')
    _hex64(data['request_id'])
    _hex64(data['variant_id'])
    _hex64(data['binding_fingerprint'])
    _hex64(data['checkpoint_id'])
    if data['variant_id'] not in BY_ID:
        raise ContractError('unknown_variant')
    binding = reviewed_binding(data['family'])
    if data['binding_fingerprint'] != binding.fingerprint:
        raise ContractError('family_semantics_mismatch')
    if data['checkpoint_id'] != binding.checkpoint_id:
        raise ContractError('incompatible_checkpoint')
    if data['world_model_id'] != binding.world_model_id:
        raise ContractError('incompatible_checkpoint')
    context = data['context']
    if type(context) is not dict or set(context) != {
        'n_actions', 'obs_dim', 'episode_steps', 'imagined_cap',
    }:
        raise ContractError('invalid_context')
    if (context['n_actions'], context['obs_dim']) != (binding.n_actions, binding.obs_dim):
        raise ContractError('model_interface_mismatch')
    return data


def build_response(request):
    variant = BY_ID[request['variant_id']]
    score = stub_score(variant)
    event_id = digest({
        'request_id': request['request_id'], 'variant_id': request['variant_id'],
        'mode': MODE, 'schema': SCHEMA,
    })
    return {
        'schema': SCHEMA,
        'request_id': request['request_id'],
        'variant_id': request['variant_id'],
        'score': score,
        'failed': False,
        'event_id': event_id,
    }


def main(argv=None):
    behavior = os.environ.get('NEXUS_E2_STUB_BEHAVIOR', 'ok')
    if behavior == 'crash':
        os._exit(2)
    if behavior == 'hang':
        time.sleep(30)
        return 1
    raw = sys.stdin.buffer.read(MAX_MESSAGE + 1)
    if behavior == 'empty':
        return 0
    if behavior == 'invalid':
        sys.stdout.buffer.write(b'not-json')
        return 0
    if behavior == 'oversized':
        sys.stdout.buffer.write(b'x' * (MAX_MESSAGE + 8))
        return 0
    try:
        request = parse_request(raw)
        payload = build_response(request)
        if behavior == 'nonfinite':
            payload['score'] = float('inf')
        if behavior == 'extra':
            payload['hidden'] = 1
        blob = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        sys.stdout.buffer.write(blob)
        return 0
    except ContractError:
        return 3


if __name__ == '__main__':
    sys.exit(main())
