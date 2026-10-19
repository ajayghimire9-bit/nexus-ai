"""Versioned nonredundant feature map; no learner or feature search."""
import numpy as np

VERSION='compact_observation_support_v1'


def build(z,c):
    z=np.asarray(z,dtype=float);c=np.asarray(c,dtype=float)
    if z.shape!=(6,) or c.shape!=(2,) or not np.isfinite(z).all() or not np.isfinite(c).all():raise ValueError('compact_feature_schema')
    additive=np.r_[1.,z,c]
    return additive,np.r_[additive,np.outer(z,c).ravel()]


def augment(paired):
    out=[]
    for row in paired:
        matrix=np.asarray(row[192:]).reshape(12,16);arm=matrix[0]
        active=np.flatnonzero(np.abs(arm)>1e-12)
        if not len(active):raise ValueError('missing_fixed_descriptor')
        task=matrix[:,active[0]]/arm[active[0]]
        if not np.allclose(np.outer(task,arm),matrix,atol=1e-12,rtol=1e-12):raise ValueError('nonfactorizable_feature_layout')
        additive,interaction=build(task[1:7],task[7:9])
        out.append(list(row)+additive.tolist()+interaction.tolist())
    return out
