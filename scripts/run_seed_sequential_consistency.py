"""One locked frozen-selector sequential comparison through the existing host."""
from run_seed_update_diagnosis import execute_study


if __name__=='__main__':
    execute_study('seed_sequential_consistency.json','NEXUS_SEED_SEQUENTIAL_CONSISTENCY_PROTOCOL.md',
        'seed_sequential_consistency.json','seed_sequential_consistency_v1','seed-sequential-consistency-1')
