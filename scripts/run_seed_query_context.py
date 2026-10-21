"""One source-only saved-data audit using the existing bounded host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_query_context.json','NEXUS_SEED_QUERY_CONTEXT_PROTOCOL.md',
        'seed_query_context.json','seed_query_context_v1','seed-query-context-1')
