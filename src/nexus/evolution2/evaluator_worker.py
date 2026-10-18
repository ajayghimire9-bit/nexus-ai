"""Process-separated synthetic fixture worker. Not a planner or sandbox.

Reads one public JSON request on stdin and writes one JSON response on stdout.
Hidden Evolution-2 family scores and host ledgers are not imported.
"""
from __future__ import annotations
import json
import os
import sys
import time

from nexus.evolution1.catalogue import ContractError, Rule
from nexus.evolution2.bindings import (
    MAX_MESSAGE, MODE, REQUEST_KEYS, REQUEST_SCHEMA, RESPONSE_SCHEMA,
    expected_event_id, validate_public_payload,
)


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
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (ValueError, TypeError, RecursionError, UnicodeDecodeError) as exc:
        raise ContractError('invalid_json') from exc
    if type(data) is not dict or set(data) != REQUEST_KEYS or data.get('schema') != REQUEST_SCHEMA:
        raise ContractError('unexpected_request_fields')
    variant, _binding = validate_public_payload(data)
    return data, variant


def build_response(request, variant):
    return {
        'schema': RESPONSE_SCHEMA,
        'request_id': request['request_id'],
        'variant_id': request['variant_id'],
        'score': stub_score(variant),
        'failed': False,
        'event_id': expected_event_id(request),
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
    if behavior == 'flood':
        sys.stdout.buffer.write(b'x' * 65536)
        return 0
    try:
        request, variant = parse_request(raw)
        payload = build_response(request, variant)
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
