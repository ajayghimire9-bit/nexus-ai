"""Reserved evaluation seeds. Curriculum may see VAL only, never INDEPENDENT."""

TRAIN_FEEDBACK_SEED = 70_000  # unused by curriculum; training uses controller seed
VAL_SEED = 71_000
INDEPENDENT_SEED = 72_000
HOLDOUT_EVAL_SEED = 73_000
CONFIRM_EVAL_SEED = 74_000  # V0.6.4 confirmation suite; selector never sees this
CONFIRM_EVAL_SEED_V065 = 75_000  # V0.6.5 confirmation; selector never sees this
CONFIRM_EVAL_SEED_V066 = 76_000  # V0.6.6 confirmation; selector never sees this
