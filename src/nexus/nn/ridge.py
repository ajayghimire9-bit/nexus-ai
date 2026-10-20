"""Existing small CPU ridge primitive, extracted from planner quality diagnostics.

Antisymmetric augmentation and training-only RMS scaling are unchanged.
This pure numeric module imports no environments, memories or experiment runner.
"""
import numpy as np


def fit_ridge(x,y,*,ridge=1.0):
    x,y=np.asarray(x,float),np.asarray(y,float)
    if x.ndim!=2 or len(x)==0 or y.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('finite_training_matrix_required')
    if type(ridge) not in (int,float) or not np.isfinite(ridge) or ridge<=0:raise ValueError('positive_ridge')
    x,y=np.r_[x,-x],np.r_[y,-y]
    scale=np.sqrt(np.mean(x*x,axis=0));scale=np.where(scale<1e-8,1.,scale);z=x/scale
    if z.shape[1]>len(z):beta=z.T@np.linalg.solve(z@z.T+ridge*np.eye(len(z)),y)
    else:beta=np.linalg.solve(z.T@z+ridge*np.eye(z.shape[1]),z.T@y)
    return scale,beta


def predict_ridge(model,x):
    scale,beta=model
    return float((np.asarray(x)/scale)@beta)
