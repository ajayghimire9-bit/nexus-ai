"""Private append-only JSON revisions using existing canonical hashes/journals.

Hash chains detect accidental corruption, not an attacker rewriting all files.
No client-controlled paths, classes or executable serialization.
"""
import json
from pathlib import Path
import re
from nexus.evolution1.catalogue import canonical, digest
from .core import Session

ID = re.compile(r'[a-f0-9]{32}\Z')


def history(root, session_id):
    if type(session_id) is not str or not ID.fullmatch(session_id):
        raise ValueError('session_id_schema')
    directory = Path(root)/session_id
    if directory.is_symlink():
        raise ValueError('session_symlink')
    records = []
    previous = None
    for i, path in enumerate(sorted(directory.glob('revision-*.json'))):
        if path.is_symlink() or path.name != f'revision-{i:04d}.json' or path.stat().st_size > 2_000_000:
            raise ValueError('revision_schema')
        wire = json.loads(path.read_text())
        if set(wire) != {'previous','revision','snapshot','hash'}:
            raise ValueError('revision_fields')
        if wire['previous'] != previous or wire['revision'] != i or digest({k:v for k,v in wire.items() if k != 'hash'}) != wire['hash']:
            raise ValueError('revision_chain')
        if records:
            old = records[-1]['snapshot']['data']['events']
            if wire['snapshot']['data']['events'][:len(old)] != old:
                raise ValueError('evidence_history_rewritten')
        Session.restore(wire['snapshot'])
        records.append(wire); previous = wire['hash']
    return records


def save(root, session_id, session):
    records = history(root, session_id)
    directory = Path(root)/session_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if len(records) >= 100:
        raise ValueError('saved_revision_cap')
    snapshot = session.snapshot()
    if records:
        old = records[-1]['snapshot']['data']['events']
        if snapshot['data']['events'][:len(old)] != old:
            raise ValueError('cannot_replace_saved_history')
    row = dict(previous=records[-1]['hash'] if records else None,
               revision=len(records), snapshot=snapshot)
    row['hash'] = digest(row)
    path = directory/f'revision-{len(records):04d}.json'
    with path.open('x') as f:
        f.write(canonical(row))
    path.chmod(0o600)
    return dict(session_id=session_id, revision=row['revision'], hash=row['hash'])


def load(root, session_id, expected_hash=None):
    records = history(root, session_id)
    if not records:
        raise ValueError('saved_session_not_found')
    if expected_hash is not None and expected_hash != records[-1]['hash']:
        raise ValueError('saved_head_mismatch')
    return Session.restore(records[-1]['snapshot'])
