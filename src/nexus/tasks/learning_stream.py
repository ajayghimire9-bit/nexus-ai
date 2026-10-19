"""Family-aware context bridge into the EXISTING TaskStream, not new memory.

No environment opening, neural-state migration, allocation or experiment
dispatch. Real neural durable state remains PPO checkpoint-owned.
"""
from nexus.core.episode_context import EpisodeContext
from nexus.evolution2.continual_state import TaskStream
from nexus.tasks.benchmark import validate_spec


def stream_binding(*, control, schedule, seed, max_choices, update_rule="mean"):
    if (type(seed) is not int or seed < 0 or type(max_choices) is not int
            or not 1 <= max_choices <= 12 or update_rule not in ("mean", "recent", "conservative")):
        raise ValueError("bounded_registered_stream_recipe")
    return TaskStream(seed=seed, max_choices=max_choices, control=control,
                      schedule=schedule, mutation_rule=update_rule)


def begin_task(stream, spec):
    contract = validate_spec(spec)
    # New family means new correctly shaped episode context, not reinterpretation
    # of saved family-specific network weights or observation-memory vectors.
    context = EpisodeContext(contract.obs_dim, len(contract.action_values))
    stream.begin_task(spec.task_id, context)
    return context
