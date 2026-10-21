"""Execute the single registered task-conditioned program ranking replication study."""
from run_seed_update_diagnosis import execute_study

if __name__ == "__main__":
    execute_study(
        "seed_task_conditioned_replication.json",
        "NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md",
        "seed_task_conditioned_replication.json",
        "seed_task_conditioned_replication_v1",
        "seed-task-conditioned-replication-1",
    )
