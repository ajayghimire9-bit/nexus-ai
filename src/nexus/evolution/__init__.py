"""Shared mutation vocabulary without eager historical training imports."""
from importlib import import_module
__all__=['mutate_spec','random_spec','run_evolution']


def __getattr__(name):
    if name not in __all__:raise AttributeError(name)
    return getattr(import_module('nexus.evolution.'+('loop' if name=='run_evolution' else 'mutate')),name)
