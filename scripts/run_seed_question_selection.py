"""One locked source-only question comparison through the existing host."""
from run_seed_update_diagnosis import execute_study

if __name__=='__main__':
    execute_study('seed_question_selection.json','NEXUS_SEED_QUESTION_SELECTION_PROTOCOL.md',
        'seed_question_selection.json','seed_question_selection_v1','seed-question-selection-1')
