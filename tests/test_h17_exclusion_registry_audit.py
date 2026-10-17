"""Configuration/AST tests only; no simulation, training or inference."""
import pytest

from nexus import h17_exclusion_registry_audit as m


def test_explicit_mcc_config_and_seed_bases():
    cfg = m.parse_config('target_family: mountaincar_continuous\ntarget_physics: [[0.0025,0.0015,0.07]]\nreset_base: 78000000')
    out = m.config_metadata('configs/toy.yaml',cfg)
    assert out['physics'][0]['classification'] == 'explicit_mcc'
    assert out['seed_bases'] == [dict(field='reset_base',base=78000000)]


def test_ambiguous_discrete_family_not_silently_called_mcc():
    cfg = dict(target_family='mountaincar',target_physics=[[0.0025,0.0015,0.07]])
    assert m.config_metadata('configs/toy.yaml',cfg)['physics'][0]['classification'] == 'ambiguous_conservative'
    assert not m.config_metadata('configs/toy.yaml',dict(target_physics=[[9.8,1.,1.]]))['physics']


@pytest.mark.parametrize('text', ['seed: 1\nseed: 2', '{"seed":1,"seed":2}', '- not\n- mapping'])
def test_duplicate_or_malformed_mapping_rejected(text):
    with pytest.raises(ValueError):
        m.parse_config(text)


def test_legacy_on_off_keys_preserved_without_mutating_yaml_global_loader():
    import yaml
    text = 'modes:\n  on:\n    reset_base: 100\n  off:\n    reset_base: 200\nflag: false'
    data = m.parse_config(text)
    assert set(data['modes']) == {'on','off'}
    assert data['flag'] is False
    assert len(m.config_metadata('toy.yaml',data)['seed_bases']) == 2
    assert set(yaml.safe_load(text)['modes']) == {True,False}


def test_numeric_horizon_keys_preserved_and_nested_metadata_still_visited():
    data = m.parse_config('candidates: {1: 48, 3: 16, 6: 8}\nother:\n  12:\n    reset_base: 300')
    assert data['candidates'] == {1:48,3:16,6:8}
    assert m.config_metadata('old.yaml',data)['seed_bases'] == [dict(field='other.[integer:12].reset_base',base=300)]


@pytest.mark.parametrize('row', [[True,0.001,0.07], [float('nan'),0.001,0.07], ['0.002',0.001,0.07], [0.,0.001,0.07], [0.002,0.001]])
def test_invalid_explicit_physics_rejected(row):
    with pytest.raises(ValueError):
        m.config_metadata('configs/mcc_toy.yaml',dict(target_physics=[row]))


def test_source_literals_without_executing_task_function():
    text = '''
raise RuntimeError('must not execute')
def source():
 return _mcc('toy','source','',gravity=0.0025,power=0.0015,max_speed=0.07)
def suite():
 rows=((0.0038,0.0019,0.085),(0.0024,0.0019,0.09))
 return [_mcc('t','d','',gravity=row[0],power=row[1],max_speed=row[2]) for row in rows]
'''
    assert len(m.family_metadata(text)) == 3


def test_merged_seed_windows_and_holes():
    assert m.merge_ranges([(10,20),(0,4),(5,9),(30,40)]) == [[0,20],[30,40]]
    with pytest.raises(ValueError):
        m.merge_ranges([(True,4)])


def test_no_target_selector_or_scientific_imports():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(m.__file__).read_text())
    names = {n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    assert not names & {'holdout_from_rule','execute','train','make_env'}
    imports = {n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    imports |= {a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
    assert not any(x.startswith(('torch','numpy','gym','nexus.world','nexus.tasks')) for x in imports)


@pytest.mark.parametrize('bad_branch', [False,True])
def test_inventory_unions_divergent_refs_and_retains_parsing_failures(tmp_path,monkeypatch,bad_branch):
    (tmp_path/'artifacts').mkdir()
    (tmp_path/'artifacts/h16_same_state_library_feasibility.json').write_text('{"closed_mcc_physics":[[0.002,0.001,0.08]]}')
    monkeypatch.setattr(m,'verify_provenance',lambda root:dict(ledger_used_s=305.842,ledger_remaining_s=3294.158))
    blobs = {'blobA':b'target_family: mountaincar_continuous\ntarget_physics: [[0.0025,0.0015,0.07]]\nreset_base: 100',
             'blobB':b'target_family: mountaincar_continuous\ntarget_physics: [[0.0038,0.0019,0.085]]'}
    if bad_branch:
        blobs['blobB'] = b'target_family: mountaincar_continuous\ntarget_physics: [[true,0.0019,0.085]]'
    def git(args,cwd):
        if args[1] == 'for-each-ref':
            return b'refs/heads/current commitA\nrefs/remotes/other/topic commitB\n'
        if args[1] == 'ls-tree':
            blob = 'blobA' if args[3] == 'commitA' else 'blobB'
            return f'100644 blob {blob}\tconfigs/mcc_toy.yaml\n'.encode()
        if args[1] == 'cat-file':
            return blobs[args[3]]
        if args[1] == 'rev-parse':
            return b'commitA\n'
        if args[1] == 'status':
            return b''
        if args[1] == 'show':
            return (tmp_path/'artifacts/h16_same_state_library_feasibility.json').read_bytes()
        raise AssertionError(args)
    monkeypatch.setattr(m.subprocess,'check_output',git)
    out = m.inventory(tmp_path)
    assert len(out['excluded_physics']) == (2 if bad_branch else 3)
    assert out['unique_commits'] == 2
    assert out['snapshot_parsed_without_issues'] is not bad_branch
    assert len(out['parsing_issues']) == int(bad_branch)
    assert out['globally_complete_closed_registry'] is False
    assert out['target_selected'] is False
