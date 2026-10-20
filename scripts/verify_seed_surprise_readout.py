"""Stdlib-only saved-data verification; never imports torch or worlds."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.readout_validation import validate,summarize,require_manifest,interval


def verify(root=ROOT):
    root=Path(root);p=root/'artifacts/seed_surprise_readout.json';r=json.loads(p.read_text());cfg=root/'configs/seed_surprise_readout.json';c=json.loads(cfg.read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if r['declared_complete'] is not True or sha(cfg)!=r['config_sha256'] or sha(root/c['parent_model'])!=c['parent_sha256']:raise ValueError('bound_result_config_core')
    validate(r,c);require_manifest(r,root)
    if hashlib.sha256(json.dumps(r['source'],sort_keys=True).encode()).hexdigest()!=r['source_hash']:raise ValueError('source_data_hash')
    expected=sum(c[k]['states'] for k in ('source','development','audit'))*9
    for cells in r['control'].values():
        for name,eps in cells.items():expected+=sum(len(e['steps']) for e in eps)*(48 if name=='latent_mpc' else 9 if name=='frozen' or name.startswith('readout_') else 0)
    if expected!=r['imagined_transitions'] or r['model_work']['head_rows']!=expected:raise ValueError('independent_imagined_accounting')
    analysis=summarize(r)
    if analysis!=r['analysis']:raise ValueError('saved_summary_changed')
    meta=r['edit_credit']['policies'];contrasts={}
    for name in ('random','fixed','historical_best'):
        contrasts[name]=interval([a['reward']-b['reward'] for a,b in zip(meta['adaptive']['rows'][32:],meta[name]['rows'][32:])])
    return dict(schema='seed_readout_verification_v1',raw_sha256=sha(p),execution_sha=r['execution_sha'],analysis=analysis,meta_contrasts=contrasts,verified_ranking_cells=len(r['audit'])*4,authored_steps=r['authored_steps'],imagined_transitions=expected,posterior_prior_rows=r['model_work']['transition_rows']-expected,model_work=r['model_work'],body_wall_s=r['wall_s'],session_used_s=r['session_used_s'],session_remaining_s=r['session_remaining_s'],frozen_hash=c['parent_sha256'])


if __name__=='__main__':print(json.dumps(verify(),indent=2,allow_nan=False))
