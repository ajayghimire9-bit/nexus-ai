"""Historical source is data. No models, task modules or simulators imported."""
import ast
import hashlib
from pathlib import Path

import pytest
from nexus import h17_seed_dependency_closure as m


def history(source, extras=None):
    files={'src/nexus/world/own.py':source.encode(),**(extras or {})}
    return m.History(files.__getitem__)


def values(source,cfg=None):
    return m.flatten(history(source).module('src/nexus/world/own.py').own('seed_groups',cfg or {}))


def test_product_tuple_binding_local_assignments_and_default_arguments():
    source='''
def helper(cfg,t,k,offset=3):
    base=cfg['base']+100*t+10*k
    return list(range(base,base+offset))
def seed_groups(cfg):
    return [{s for t,k in itertools.product(range(2),range(3)) for s in helper(cfg,t,k)}]
'''
    assert values(source,{'base':1000})=={1000+100*t+10*k+i for t in range(2) for k in range(3) for i in range(3)}


def test_loop_branches_and_string_configuration_keys():
    source='''
def helper(cfg,role):
    if role=='source':
        base=cfg['source'];n=3
    elif role=='target':
        base=cfg['target'];n=2
    else:
        raise ValueError('bad role')
    return list(range(base,base+n))
def seed_groups(cfg):
    groups=[]
    for role in ('source','target'):
        groups.extend([{s for s in helper(cfg,role)}])
    return groups
'''
    assert values(source,{'source':100,'target':200})=={100,101,102,200,201}
    with pytest.raises(m.Unsupported,match='guard'):
        history(source).module('src/nexus/world/own.py').call('helper',[{},'bad'])


def test_imported_constants_and_delegate_are_resolved_without_importing_modules():
    own='''
raise RuntimeError('module must not execute')
from nexus.world import old as parent
N_SEEDS=parent.N_SEEDS
def seed_groups(cfg):
    return parent.seed_groups(cfg)
'''
    old=b'''raise RuntimeError('module must not execute')
N_SEEDS=3
def seed_groups(cfg): return [{cfg['base']+i for i in range(N_SEEDS)}]
'''
    h=history(own,{'src/nexus/world/old.py':old})
    assert h.module('src/nexus/world/own.py').lookup('N_SEEDS',{})==3
    assert m.flatten(h.module('src/nexus/world/own.py').own('seed_groups',{'base':10}))=={10,11,12}
    assert {r['sha256'] for r in h.dependencies()}=={hashlib.sha256(v).hexdigest() for v in (own.encode(),old)}


def test_collision_guard_slice_does_not_execute_result_loaders():
    source='''
def helper(cfg,s): return cfg['base']+s
def check_seeds(cfg):
    never_imported.load_config()
    groups=[{helper(cfg,s) for s in range(4)}]
    if set().union(*groups):
        raise RuntimeError('do not execute collision guard')
'''
    h=history(source)
    assert m.flatten(h.module('src/nexus/world/own.py').own('check_seeds',{'base':100}))=={100,101,102,103}


def test_used_union_and_stream_tuple_wrapper():
    source='''
def seed_streams(cfg): return {'first':{cfg['base'],cfg['base']+1}}, {cfg['base'],cfg['base']+1}
def check_seeds(cfg):
    streams,used=seed_streams(cfg)
'''
    h=history(source)
    assert m.flatten(h.module('src/nexus/world/own.py').own('check_seeds',{'base':70}))=={70,71}


@pytest.mark.parametrize('body',[
    "return open('/tmp/no').read()", "return __import__('torch')",'import torch\n    return {1}',
    'while True: pass', 'return seed_groups(cfg)', 'return {True}',
])
def test_unsupported_or_non_integer_seeds_fail_closed(body):
    with pytest.raises(m.Unsupported):values('def seed_groups(cfg):\n    '+body)


def test_resource_limit_catches_loops_without_expression_work(monkeypatch):
    monkeypatch.setattr(m,'LIMIT',30)
    with pytest.raises(m.Unsupported,match='resource'):
        values('def seed_groups(cfg):\n    for i in range(500):\n        x=1\n    return {1}')


def test_out_of_window_values_and_dependency_hashes_are_not_hidden():
    source="def seed_groups(cfg): return [{cfg['base']+100*i for i in range(3)}]"
    h=history(source)
    out=m.certificate(h,'src/nexus/world/own.py',{'base':1000},'seed_groups',[[1000,1100]])
    assert out['outside_reservations']==[1200]
    assert out['count']==3
    assert out['dependencies'][0]['sha256']==hashlib.sha256(source.encode()).hexdigest()


def test_no_scientific_imports_no_eval_and_no_registration_entrypoint():
    tree=ast.parse(Path(m.__file__).read_text())
    modules={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    modules|={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert not any(v.startswith(('torch','numpy','gym','nexus.world','nexus.tasks')) for v in modules)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'eval','exec','compile','__import__'} for n in ast.walk(tree))
