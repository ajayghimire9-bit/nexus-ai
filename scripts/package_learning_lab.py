"""Versioned local demo: verified replay + existing durable authored sessions.

No pip, network, models, simulator, deployment or experiment authorization.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='nexus-learning-lab-0.2.0'


def payload(root=ROOT):
    root=Path(root)
    files=subprocess.check_output(['git','ls-files','src/nexus'],cwd=root,text=True).splitlines()
    files=[p for p in files if p.endswith('.py')]
    files+=['scripts/nexus_lab.py','scripts/run_learning_lab.py','scripts/run_learning_lab_session.py','scripts/verify_demo.py','web/learning-lab/index.html','web/learning-lab/seed.html']
    files+=['artifacts/'+name+'.json' for name in (
        'e3_11b_forecast_calibration','e3_11b_forecast_calibration_validation',
        'e3_11d_horizon_calibration','e3_11d_horizon_validation',
        'e3_12b_operator_headroom','e3_12b_operator_validation','e3_12d_parent_retention','e3_12d_parent_validation',
        'e3_12e_training_stability','e3_12e_training_validation')]
    files+=['artifacts/e3_11b_forecast_predecision.jsonl','artifacts/e3_11d_horizon_predecision.jsonl']
    files+=['configs/e3_12b_operator_headroom.json','configs/e3_12d_parent_retention.json','configs/e3_12f_reset_blocked_runtime_v2.json']
    files+=['docs/NEXUS_LEARNING_LAB_LOCAL.md','docs/NEXUS_LEARNING_LAB_DEMO_RELEASE.md']
    result={p:(root/p).read_bytes() for p in sorted(set(files))}
    spec=importlib.util.spec_from_file_location('lab_offline_release',root/'scripts/build_learning_lab_app.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result['offline.html']=module.build(root).encode()
    result['README.md']=(root/'docs/NEXUS_LEARNING_LAB_DEMO_RELEASE.md').read_bytes()
    result['requirements-fixtures.txt']=b'numpy>=1.26\ntorch>=2.2\ngymnasium>=0.29\npyyaml>=6.0\n'
    if any(not p or p.startswith('/') or '..' in Path(p).parts or '\\' in p or p.endswith(('.pt','.npz','.pth')) for p in result):raise ValueError('release_allowlist')
    return result


def build(target,root=ROOT):
    root=Path(root);target=Path(target)
    if target.exists():raise FileExistsError(target)
    data=payload(root)
    manifest=dict(version=VERSION,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        tracked_tree_dirty=bool(subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=root,text=True).strip()),
        live_scientific_backend=False,fixture_mode='authored_only_optional_dependencies',
        files={p:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for p,raw in data.items()})
    data['DEMO_MANIFEST.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(data.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,raw,compresslevel=9)
    return dict(version=VERSION,path=str(target),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                source_revision=manifest['source_revision'],tracked_tree_dirty=manifest['tracked_tree_dirty'],files=len(manifest['files']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.output),indent=2))
