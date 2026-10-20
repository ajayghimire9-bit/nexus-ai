# Frozen prediction-vector recovery — no new scientific test

The completed d4e6ff3 study saved per-state ranking metrics and true outcomes,
but omitted nine predicted reward vectors. Preserve its original JSON unchanged.
Recover those vectors once by deterministic inference from the18 hash-verified
saved checkpoints and64 recorded cold-start states. No world.step, fitting,
hyperparameter selection, new state selection or independent evidence.

Use exact Belief/source-bank contract and check every saved metric agrees within
1e-7 before declaring recovery complete. Save a separate child artifact with
parent result hash,18×64 raw predicted rewards/next states, and accounting.
Cap60s,10368 imagined candidate states plus1152 observation-prior transitions,
zero real steps. Commit this protocol/runner before replay. Count its runtime
against the carried ledger after the main27.0816-second run. It is audit work,
not a second experimental confirmation. Do not alter original results on failure.
