"""One fresh-task study, committed before dispatch to the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_conditioned_acquisition.json','NEXUS_SEED_CONDITIONED_ACQUISITION_PROTOCOL.md',
        'seed_conditioned_acquisition.json','seed_conditioned_acquisition_v1','seed-conditioned-acquisition-1')
