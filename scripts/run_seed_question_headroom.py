"""One bounded evaluator-only source question-pool audit."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_question_headroom.json','NEXUS_SEED_QUESTION_HEADROOM_PROTOCOL.md',
        'seed_question_headroom.json','seed_question_headroom_v1','seed-question-headroom-1')
