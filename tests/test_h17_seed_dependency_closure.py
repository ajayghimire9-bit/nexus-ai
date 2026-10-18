"""Historical source is data. No models, task modules or simulators imported."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

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


def test_dictionary_comprehension_and_bounded_while_with_keyword_default():
    source='''
CAP=3
def helper(base,n,*,cap=CAP):
    seeds=set()
    remaining=n
    episode=0
    while remaining>0:
        seeds.add(base+episode)
        remaining-=min(cap,remaining)
        episode+=1
    return seeds
def seed_groups(cfg):
    return {k:helper(cfg[k],7) for k in ('a','b')}
'''
    assert values(source,{'a':100,'b':200})=={100,101,102,200,201,202}


def test_metadata_loader_reads_same_history_yaml_but_never_runs_validation():
    source='''
CONFIG=Path('configs/past.yaml')
def load_config():
    raise RuntimeError('historical loader never runs')
def seed_groups(cfg):
    prior=load_config()
    return [{prior['base']+i for i in range(3)}]
'''
    raw=b'base: 900\n'
    h=history(source,{'configs/past.yaml':raw})
    assert m.flatten(h.module('src/nexus/world/own.py').own('seed_groups',{}))=={900,901,902}
    assert dict((r['path'],r['sha256']) for r in h.dependencies())['configs/past.yaml']==hashlib.sha256(raw).hexdigest()
    # Changing the committed dependency changes both the certificate and hash.
    other=history(source,{'configs/past.yaml':b'base: 1900\n'})
    assert m.flatten(other.module('src/nexus/world/own.py').own('seed_groups',{}))=={1900,1901,1902}


def test_metadata_loader_rejects_non_config_path():
    source="def load_config(): pass\ndef seed_groups(cfg): return load_config('/etc/passwd')"
    with pytest.raises(m.Unsupported,match='unbound'):
        values(source)


def test_design_path_is_bound_from_loader_literal_only():
    source="def load_design_config():\n return (ROOT/'configs/old_design.yaml').read_text()"
    assert m.config_path(history(source).module('src/nexus/world/own.py'))=='configs/old_design.yaml'
    with pytest.raises(m.Unsupported):m.config_path(history(source.replace("'configs/old_design.yaml'","runtime_name")).module('src/nexus/world/own.py'))


def test_local_import_is_scoped_source_reference_and_not_runtime_import():
    source='''
def seed_groups(cfg):
    from nexus.world.previous import old_seeds as imported
    groups={}
    for name in ('a','b'):
        groups[f'prior_{name}']=imported(cfg)
    return groups
'''
    old=b"raise RuntimeError('must never execute')\ndef old_seeds(cfg): return {cfg['base'],cfg['base']+1}"
    h=history(source,{'src/nexus/world/previous.py':old})
    assert m.flatten(h.module('src/nexus/world/own.py').own('seed_groups',{'base':75}))=={75,76}
    with pytest.raises(m.Unsupported,match='unknown'):
        h.module('src/nexus/world/own.py').call('imported',[{}])


def test_pure_dictionary_and_set_updates():
    source='''
def seed_groups(cfg):
    groups={'a':{1,2}}
    groups.update({'b':{3,4}})
    groups['b'].update({5})
    return groups
'''
    assert values(source)=={1,2,3,4,5}


@pytest.mark.parametrize('path',['src/nexus/world/control_replication.py','src/nexus/world/prediction_control_gap.py'])
def test_old_composite_registries_resolve_without_historical_imports(path):
    root=Path(__file__).resolve().parents[1]
    capture=json.loads((root/'artifacts/h17_seed_dependency_closure_validated.json').read_text())
    row=next(r for r in capture['unresolved'] if r['path']==path)
    h=m.History(lambda p:subprocess.check_output(['git','show',row['commit']+':'+p],cwd=root))
    raw=subprocess.check_output(['git','show',row['commit']+':'+row['config_path']],cwd=root)
    registry=json.loads((root/m.REGISTRY).read_text())
    result=m.certificate(h,path,m.parse_config(raw.decode()),row['function'],registry['conservative_seed_reservations'])
    assert result['count']>0
    assert not result['outside_reservations']
    assert len(result['dependencies'])>3


def test_explicit_registration_metadata_separates_seed_bases_from_counts():
    data={'registered_audit_seeds':{'support_env0':100,'query_base':200,'query_episodes':4},
          'registered_seed_block':[1000,2000], 'positive_seeds':6, 'original_seeds':[0,1,2]}
    rows=m.registration_fields(data,[[0,999],[1000,1000]])
    points=[p for r in rows for p in r.get('points',[])]
    assert {p['value'] for p in points}=={100,200,1000,2000}
    assert [p['value'] for p in points if not p['inside_existing_window']]==[2000]
    assert rows[0]['nonseed_fields']==['query_episodes']
    assert 'interval' not in rows[1]  # Two base labels must not become a range.


@pytest.mark.parametrize('data',[
    {'registered_seeds':{'unexplained':100}}, {'future_seed_register':[100]},
    {'registered_seed_block':['100',200]}, {'registered_audit_seeds':{'support_env0':True}},
])
def test_unknown_or_malformed_registration_metadata_fails_closed(data):
    with pytest.raises(m.Unsupported):m.registration_fields(data,[[0,999]])


def test_rng_callsite_inventory_does_not_certify_dataflow_or_run_calls():
    source='''
def run(cfg):
    rng=np.random.default_rng(cfg['action_base']+3)
    torch.manual_seed(7)
    env.reset(seed=cfg['reset_base'])
    collect(seed_base=cfg['source_base'],env_seed_base=cfg['source_env0'])
'''
    rows=m.rng_call_sites(source)
    assert len(rows)==4 and all(r['function']=='run' for r in rows)
    assert rows[2]['seed_expressions']==["seed=cfg['reset_base']"]
    assert not any('certified' in r for r in rows)


def test_metric_and_replication_count_fields_are_not_registration_bases():
    rows=m.registration_fields({'per_seed_metrics':{'never':'inspect performance'},'n_seeds_exploratory':3},[[0,100]])
    assert len(rows)==2
    assert all(r['classification']=='descriptive_count_statistic_or_status_values_not_inspected' for r in rows)
    assert not any('points' in r for r in rows)


def test_every_previously_listed_registry_function_now_has_a_certificate():
    root=Path(__file__).resolve().parents[1]
    old=json.loads((root/'artifacts/h17_reservation_closure_validated.json').read_text())
    new=json.loads((root/'artifacts/h17_seed_dependency_coverage.json').read_text())
    key=lambda r:(r['path'],r['git_blob'],r['function'])
    expected={key(r) for r in old['historical_seed_certificates']+old['unsupported_seed_functions']}
    certified={key(r) for r in new['certificates']}
    assert len(expected)==67 and expected<=certified
    assert not new['unresolved']
    assert not any(r['outside_reservations'] for r in new['certificates'])


def test_final_grid_comes_from_locked_source_inventory_not_produced_rows():
    root=Path(__file__).resolve().parents[1]
    parent=json.loads((root/m.PARENT).read_text())
    result=json.loads((root/'artifacts/h17_seed_dependency_coverage_validated.json').read_text())
    expected=set()
    for row in parent['all_reachable_inputs']:
        if row['path'].endswith('.py'):
            raw=subprocess.check_output(['git','cat-file','blob',row['git_blob']],cwd=root)
            for node in ast.parse(raw.decode()).body:
                if isinstance(node,ast.FunctionDef) and node.name in m.OWN_FUNCTIONS:
                    expected.add((row['path'],row['git_blob'],node.name))
    key=lambda r:(r['path'],r['git_blob'],r['function'])
    actual=[key(r) for r in result['certificates']]
    assert len(actual)==len(set(actual)) and set(actual)==expected
    assert not result['unresolved']
    artifacts={(r['path'],r['git_blob']) for r in parent['all_reachable_inputs']
               if r['path'].startswith('artifacts/') and r['path'].endswith('.json')}
    assert {(r['path'],r['git_blob']) for r in result['artifact_seed_metadata']}==artifacts
    assert not result['unclassified_artifact_seed_metadata']
    checked=set()
    for row in result['certificates']:
        for dependency in row['dependencies']+[{'path':row['config_path'],'sha256':row['config_sha256']}]:
            label=(row['commit'],dependency['path'],dependency['sha256'])
            if label in checked:continue
            raw=subprocess.check_output(['git','show',row['commit']+':'+dependency['path']],cwd=root)
            assert hashlib.sha256(raw).hexdigest()==dependency['sha256']
            checked.add(label)
