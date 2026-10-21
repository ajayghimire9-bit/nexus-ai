"""One saved-data-only run through the existing metered EXPERIMENTAL host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_compiled_greedy.json','NEXUS_SEED_COMPILED_GREEDY_PROTOCOL.md',
                  'seed_compiled_greedy.json','seed_compiled_greedy_v1','seed-compiled-greedy-1')
