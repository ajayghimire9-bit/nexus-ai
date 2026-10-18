"""Arithmetic-only regression tests: never load experiments or environments."""
import ast
from pathlib import Path

import pytest

from nexus import h17_reservation_closure as m


def test_generated_offsets_not_just_base_are_checked():
    source = '''
N_SEEDS=3
def check_seeds(cfg):
    used={cfg['base']+100*s+i for s in range(N_SEEDS) for i in range(2)}
    used|={cfg['other']+i for i in range(2)}
'''
    result = m.certify(source,dict(base=1000,other=4000),[[1000,1101],[4000,4001]],'check_seeds')
    assert result['count']==8
    assert result['minimum']==1000 and result['maximum']==4001
    assert result['outside_reservations']==[1200,1201]


def test_arithmetic_helpers_and_endpoint_counts():
    source = '''
def sid(cfg,s,t): return cfg['base']+100*s+t
def seed_groups(cfg):
    resets={sid(cfg,s,t) for s in range(3) for t in range(4)}
    return resets,
'''
    out=m.certify(source,dict(base=500),[[500,703]],'seed_groups')
    assert (out['count'],out['minimum'],out['maximum'])==(12,500,703)
    assert not out['outside_reservations']


def test_stream_dictionary_does_not_execute_collision_guard():
    source = '''
raise RuntimeError('not executed')
def seed_streams(cfg):
    streams={'a':{cfg['base']+i for i in range(3)}}
    used=set()
    for group in streams.values():
        raise RuntimeError('not executed')
    return streams,used
'''
    assert m.certify(source,dict(base=100),[[100,102]],'seed_streams')['count']==3


@pytest.mark.parametrize('expression',[
    "__import__('os').system('false')",'unknown(cfg)',
    '{i for i in range(3) if i>0}','{i for i in range(100000000)}',
    '{True for i in range(1)}',
])
def test_unsupported_expressions_fail_closed(expression):
    source=f'def check_seeds(cfg):\n used={expression}'
    with pytest.raises(m.Unsupported):
        m.certify(source,{},[[0,100]],'check_seeds')


def test_missing_config_and_constants_are_not_invented():
    with pytest.raises(KeyError):
        m.certify("def check_seeds(cfg):\n used={cfg['missing']+i for i in range(2)}",{},[[0,100]],'check_seeds')
    with pytest.raises(m.Unsupported):
        m.certify('def check_seeds(cfg):\n used={i for i in range(IMPORTED)}',{},[[0,100]],'check_seeds')


def test_operation_budget_is_shared_not_reset_per_comprehension(monkeypatch):
    monkeypatch.setattr(m,'LIMIT',10)
    with pytest.raises(m.Unsupported,match='resource bound'):
        m.certify('def check_seeds(cfg):\n used={i+1 for i in range(20)}',{},[[0,100]],'check_seeds')


def test_config_binding_and_no_scientific_imports():
    assert m._config_path(ast.parse("CONFIG=Path('configs/old.yaml')"))=='configs/old.yaml'
    with pytest.raises(m.Unsupported): m._config_path(ast.parse('CONFIG=choose()'))
    tree=ast.parse(Path(m.__file__).read_text())
    imports={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports|={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert not any(v.startswith(('torch','numpy','gym','nexus.world','nexus.tasks')) for v in imports)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'eval','exec','compile'} for n in ast.walk(tree))
