"""One locked fresh-query replication; refuses a consumed configuration."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_query_replication.json','NEXUS_SEED_QUERY_REPLICATION_PROTOCOL.md',
        'seed_query_replication.json','seed_query_replication_v1','seed-query-replication-1')
