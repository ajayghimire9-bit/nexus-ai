"""One registered learning-rule study through the existing EXPERIMENTAL host."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.experimental import Sandbox, read, write_new


def main():
    destination=ROOT/'artifacts/seed_nonlinear_learning.json'
    if destination.exists():raise ValueError('study_closed_artifact_exists')
    cfg=ROOT/'configs/seed_nonlinear_learning.json';c=read(cfg)
    host=Sandbox(ROOT)
    grant='seed-learning-6401-6403'
    with host.locked():
        if not (host.directory/'grants'/f'{grant}.json').exists():
            host.grant(grant,'human standing grant 2026-10-16 plus explicit current user request',
                'One locked CPU learning-to-learn study; no resource increase',
                dict(wall_s=180,cpu_s=180,memory_mb=2048,real_steps=12000,imagined_transitions=100000,updates=384),
                session_limit_s=3600,carried_used_s=c['carried_used_s'],memory_policy='sampled_rss')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        spec=dict(id='seed-nonlinear-learning-1',mode='exploration',recipe=dict(adapter='seed_nonlinear_learning_v1',
            config_path=str(cfg.relative_to(ROOT)),config_sha256=sha(cfg),
            protocol_path='docs/NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md',protocol_sha256=sha(ROOT/'docs/NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md')),
            train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
        result=host.execute(spec,grant)
    worker=result.get('worker') or {};raw=worker.get('study')
    if raw is None:
        progress=host.directory/'attempts'/spec['id']/'progress.json'
        raw=read(progress) if progress.exists() else dict(declared_complete=False,config=c)
    raw['host_receipt']={k:v for k,v in result.items() if k!='worker'}
    raw['host_result_path']=str(host.directory/'attempts'/spec['id']/'result.json')
    raw['host_result_sha256']=sha(Path(raw['host_result_path']))
    raw['execution_sha']=result['revision'];raw['config_file_sha256']=sha(cfg)
    raw['execution_debit_s']=int(result['wall_s'])+2
    raw['session_used_s']=c['carried_used_s']+raw['execution_debit_s']
    raw['session_remaining_s']=c['carried_remaining_s']-raw['execution_debit_s']
    raw['declared_complete']=result['status']=='complete_development' and raw.get('declared_complete') is True
    write_new(destination,raw)
    print(json.dumps({k:raw.get(k) for k in ('declared_complete','failure','wall_s','costs','analysis','session_remaining_s')},indent=2))
    if not raw['declared_complete']:raise SystemExit(1)


if __name__=='__main__':main()
