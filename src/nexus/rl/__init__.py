"""Historical RL APIs load only when explicitly used."""
from importlib import import_module
__all__=['ActorCritic','PPOTrainer','compute_gae']


def __getattr__(name):
    modules={'ActorCritic':'actor_critic','PPOTrainer':'ppo','compute_gae':'gae'}
    if name not in modules:raise AttributeError(name)
    return getattr(import_module('nexus.rl.'+modules[name]),name)
