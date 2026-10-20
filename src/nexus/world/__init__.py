"""Shared learned-model APIs with lazy historical implementations."""
from importlib import import_module
__all__=['WorldModel','RandomShootingMPC']


def __getattr__(name):
    modules={'WorldModel':'dynamics','RandomShootingMPC':'planning'}
    if name not in modules:raise AttributeError(name)
    return getattr(import_module('nexus.world.'+modules[name]),name)
