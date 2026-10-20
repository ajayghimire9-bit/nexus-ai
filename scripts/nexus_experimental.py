"""EXPERIMENTAL: bounded typed development, explicit owner grants, no auto merge."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from nexus.seed.experimental import Sandbox, read


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=ROOT/'runs/experimental')
    sub = p.add_subparsers(dest='command', required=True)
    reg = sub.add_parser('register', help='owner attests new data provenance; no collection')
    reg.add_argument('id'); reg.add_argument('role', choices=('train','development','validation','confirmation'))
    reg.add_argument('data', type=Path); reg.add_argument('--owner', required=True)
    reg.add_argument('--provenance', required=True)
    grant = sub.add_parser('approve', help='local owner action; never called by workers or GUI')
    grant.add_argument('id'); grant.add_argument('budget', type=Path)
    grant.add_argument('--owner', required=True); grant.add_argument('--reason', required=True)
    run = sub.add_parser('run'); run.add_argument('manifest', type=Path); run.add_argument('--grant', required=True)
    fork = sub.add_parser('fork'); fork.add_argument('id')
    keep = sub.add_parser('retain'); keep.add_argument('validation_run')
    sub.add_parser('rollback'); sub.add_parser('status')
    a = p.parse_args(argv)
    try:
        host = Sandbox(ROOT, a.directory)
        with host.locked():
            if a.command=='register':
                result = host.register(a.id, a.role, a.data, a.owner, a.provenance)
            elif a.command=='approve':
                budget = read(a.budget)
                if set(budget) != {'caps','session_limit_s','carried_used_s','device','memory_policy'}:
                    raise ValueError('budget_schema')
                result = host.grant(a.id, a.owner, a.reason, **budget)
            elif a.command=='run':
                result = host.execute(read(a.manifest), a.grant)
            elif a.command=='fork':
                result = host.fork(a.id)
            elif a.command=='retain':
                result = {'accepted_in_sandbox_only':host.retain(a.validation_run)}
            elif a.command=='rollback':
                result = {'incumbent':host.rollback()}
            else:
                result = host.view()
        print(json.dumps(result, indent=2, allow_nan=False))
        if a.command=='run' and result['status'] in ('incomplete_execution','invalid_integrity'):
            return 1
        return 0
    except (ValueError, OSError, KeyError) as exc:
        p.exit(2, str(exc)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
