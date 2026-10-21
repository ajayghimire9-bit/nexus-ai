"""One bounded, committed acquisition study through the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_source_acquisition.json','NEXUS_SEED_SOURCE_ACQUISITION_PROTOCOL.md',
        'seed_source_acquisition.json','seed_source_acquisition_v1','seed-source-acquisition-1')
