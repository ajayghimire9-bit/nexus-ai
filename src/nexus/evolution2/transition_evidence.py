"""Locked source-support preprocessing, not a learner or collection pipeline."""
import numpy as np

from nexus.core.strategy_memory import SupportBatch,describe_support,support_from_arrays
from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution1.catalogue import digest
from nexus.evolution2.fit_clock import LOCKED_ARRAYS
from nexus.evolution2.full_policy_source import ROOT,verify_file
from nexus.evolution2 import feature_informativeness as audit

SOURCES=tuple(r for r in LOCKED_ARRAYS if r['split']=='train' and r['bundle'] in (0,1))


def summaries(support,context,mean,std):
    """One existing linear-support diagnostic; never fit to return/query labels."""
    mean=np.asarray(mean,dtype=float);std=np.asarray(std,dtype=float)
    if mean.shape!=(context.obs_dim,) or std.shape!=mean.shape or not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std<=0):
        raise ValueError('frozen_source_normalization')
    if support.obs.shape!=(32,context.obs_dim) or support.next_obs.shape!=support.obs.shape or support.action.shape!=(32,):raise ValueError('exact_support_prefix')
    if not np.isfinite(support.obs).all() or not np.isfinite(support.next_obs).all() or support.action.dtype.kind not in 'iu' or np.any(support.action<0) or np.any(support.action>=context.n_actions):raise ValueError('finite_support')
    normalized=SupportBatch((support.obs-mean)/std,support.action,(support.next_obs-mean)/std,support.reward)
    desc=describe_support(normalized,context,require_fit=True)
    result=np.array([np.mean(np.abs(normalized.next_obs-normalized.obs)),desc[7],len(np.unique(support.action))/context.n_actions],dtype=float)
    if not np.isfinite(result).all():raise ValueError('finite_transition_statistics')
    return result


def augment(bank,features,stats):
    """Change ONLY three task coordinates; every fitted vector stays192-d."""
    audit.validate_bank(bank,features)
    if set(stats)!={f'{f}:{b}' for f,b in audit.MODELS}:raise ValueError('complete_support_grid')
    out=[]
    for row,phi in zip(bank,features):
        f,b,_=audit.base.identity(row);values=stats[f'{f}:{b}']
        if len(values)!=3 or not all(audit.base.number(v) for v in values):raise ValueError('finite_statistics')
        matrix=np.asarray(phi).reshape(12,16).copy();matrix[7:10]=np.outer(values,matrix[0])
        out.append(list(phi)+matrix.ravel().tolist())
    audit.validate_bank(bank,out,'e3_7')
    return out


def prepare(saved,bank,features,on_descriptor=None):
    """Only four pinned original TRAIN arrays; never source val or control data."""
    records={};stats={}
    for spec in SOURCES:
        path=ROOT/spec['path'];verify_file(path,spec['sha256'])
        with np.load(path,allow_pickle=False) as arrays:
            if len(arrays['obs'])!=1024:raise ValueError('source_training_size')
            raw={k:arrays[k][:32].copy() for k in ('obs','action','next_obs')}
        support=support_from_arrays(raw['obs'],raw['action'],raw['next_obs'],n=32)
        key=f'{spec["family"]}:{spec["bundle"]}'
        receipt=digest(dict(obs=support.obs.tolist(),action=support.action.tolist(),next_obs=support.next_obs.tolist()))
        if receipt!=saved['support_sha256'][key]:raise ValueError('original_support_receipt')
        norm=saved['normalizers'][spec['family']];context=family_context(spec['family'])
        if on_descriptor:on_descriptor()
        values=summaries(support,context,norm['mean'],norm['std']).tolist();stats[key]=values
        records[key]=dict(source=spec,support_start=0,support_rows=32,original_support_sha256=receipt,
            typed_prefix_sha256=digest({k:dict(shape=list(v.shape),dtype=str(v.dtype),data=v.tolist()) for k,v in raw.items()}),
            normalizer=norm,statistics=values,descriptor_lstsq_calls=1)
        verify_file(path,spec['sha256'])
    return augment(bank,features,stats),records
