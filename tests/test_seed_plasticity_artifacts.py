"""Repository-only evidence checks; no PyTorch, model calls or worlds."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest
ROOT=Path(__file__).resolve().parents[1]


def analysis():
    spec=importlib.util.spec_from_file_location('memory_summary',ROOT/'scripts/summarize_seed_memory_aware.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_saved_source_audit_is_complete_but_practical_screen_failed():
    m=analysis();r=m.analyze()
    assert not r['practical_screen_passed'] and r['independent_decoder_replicates']==1
    assert r['splits']['audit']['contrasts']['fixed_protected']['relative_reduction']<.1


@pytest.mark.parametrize('fault',['seed','episode','condition','metric','boolean','nan','checkpoint'])
def test_repository_only_validator_rejects_incomplete_evidence(tmp_path,fault):
    r=json.loads((ROOT/'artifacts/seed_memory_aware.json').read_text());c=r['config']
    names=['configs/seed_memory_aware.json',c['parent_model'],c['source_result']]+[s['checkpoint'] for s in r['seeds']]
    for name in names:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    if fault=='seed':r['seeds'].pop()
    elif fault=='episode':r['seeds'][0]['evaluation']['audit'].pop()
    elif fault=='checkpoint':(tmp_path/r['seeds'][0]['checkpoint']).write_text('{}')
    else:
        methods=r['seeds'][0]['evaluation']['audit'][0]['methods']
        if fault=='condition':methods.pop('learned')
        elif fault=='metric':methods['learned'].pop('forgetting')
        elif fault=='boolean':methods['learned']['query_auc']=True
        elif fault=='nan':methods['learned']['query_auc']=float('nan')
    (tmp_path/'artifacts/seed_memory_aware.json').write_text(json.dumps(r))
    with pytest.raises(ValueError):analysis().analyze(tmp_path)
