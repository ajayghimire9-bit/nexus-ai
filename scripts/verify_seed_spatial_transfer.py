"""Saved-data arithmetic/provenance only; no neural libraries or simulation."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexus.seed.spatial_transfer import validate,summarize,closed_initials


def verify(root=ROOT):
    root=Path(root);p=root/'artifacts/seed_spatial_transfer.json';r=json.loads(p.read_text());cfg=root/'configs/seed_spatial_transfer.json';c=json.loads(cfg.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if r['declared_complete'] is not True or sha(cfg)!=r['config_sha256']:raise ValueError('complete_bound_result_required')
    for name in ('parent_results','parent_manifest','parent_model'):
        if sha(root/c[name])!=c['parent_sha256' if name=='parent_model' else name+'_sha256']:raise ValueError('parent_provenance')
    parent=json.loads((root/c['parent_results']).read_text())
    if set(map(tuple,r['closed_initials']))!=closed_initials(parent):raise ValueError('closed_state_exclusion_set')
    manifest=json.loads((root/c['parent_manifest']).read_text())
    if manifest!=r['checkpoint_manifest']:raise ValueError('checkpoint_manifest_substitution')
    for h in manifest['heads']:
        if sha(root/h['checkpoint'])!=h['sha256']:raise ValueError('frozen_readout_hash')
    validate(r,c);a=summarize(r)
    if a!=r['analysis']:raise ValueError('summary_arithmetic')
    if r['model_work']['head_rows']!=r['imagined_transitions']:raise ValueError('imagined_head_accounting')
    return dict(schema='seed_spatial_transfer_verification_v1',raw_sha256=sha(p),execution_sha=r['execution_sha'],valid=True,analysis=a,
        resources=dict(authored_steps=r['authored_steps'],imagined_transitions=r['imagined_transitions'],posterior_prior_rows=r['model_work']['transition_rows']-r['imagined_transitions'],wall_s=r['wall_s'],session_used_s=r['session_used_s'],session_remaining_s=r['session_remaining_s']))


if __name__=='__main__':print(json.dumps(verify(),indent=2,allow_nan=False))
