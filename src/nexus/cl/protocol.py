"""Reserved evaluation seeds. Curriculum may see VAL only, never INDEPENDENT."""

TRAIN_FEEDBACK_SEED = 70_000  # unused by curriculum; training uses controller seed
VAL_SEED = 71_000
INDEPENDENT_SEED = 72_000
HOLDOUT_EVAL_SEED = 73_000
