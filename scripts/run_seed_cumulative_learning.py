"""Run one locked task-blocked learning comparison via the existing host."""
from run_seed_update_diagnosis import execute_study


if __name__=='__main__':
    execute_study('seed_cumulative_learning.json','NEXUS_SEED_CUMULATIVE_LEARNING_PROTOCOL.md',
        'seed_cumulative_learning.json','seed_cumulative_learning_v1','seed-cumulative-learning-1')
