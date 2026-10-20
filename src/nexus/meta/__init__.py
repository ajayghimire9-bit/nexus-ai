"""Shared meta APIs; loading a Seed bandit must not load PPO experiment runners."""
from importlib import import_module

_EXPORTS={'ExperimentAction':'schema','LinUCBController':'controller',
          'make_controller':'controller','compare_controllers':'loop',
          'run_research_loop':'loop','propose_next_experiment':'select'}
__all__=list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:raise AttributeError(name)
    return getattr(import_module('nexus.meta.'+_EXPORTS[name]),name)
