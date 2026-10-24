# Wave 15 failed blind run — immutable evidence postmortem

**Closed Developmental / Invalid (Cost Domination & 0 OOG Piecewise Evals
Passed; Failed Full Accuracy 51/54 vs 54/54 Without Pruning).** Historical
freeze `4810ae6533ed970a330b09261b1ce4bf511b9a08` → results
`9db4dc9492bd23ec053e11ba6f67404c3ce52f12`. No old suite is run or changed.

Saved artifact SHA256:
`4158530927bfb789cff53b3cb2f27858e9ba5432e19ba5a91fc57b8c6f848992`.
The artifact, historical runtime and all closed assessment definitions remain
unchanged. This postmortem reads saved evidence and source only.

## Exact five-method saved table

| Method | Correct /54 | Solvable prediction /48 | Work | Primitive steps |
|---|---:|---:|---:|---:|
| equal_typed_scratch | 39 | 33 | 111852 | 313002 |
| ordinary_persistent_memoization | 39 | 33 | 112509 | 315417 |
| nexus_whole_macro_only | 51 | 45 | 68136 | 184017 |
| nexus_typed_without_pruning | 54 | 48 | 72456 | 200094 |
| nexus_typed_full | 51 | 45 | 60510 | 161604 |

All five methods have zero false unique locks and zero OOG piecewise
evaluations/opcodes. Full has three cold reactivations and three correct
ambiguous refusals. Correct outcomes include OOG/ambiguous refusals; these are
not prediction programs. Cost domination cannot override the accuracy failure.

## Exactly three missed cells and the search hole

All three seeds miss `w15f_even_two_init_distractor`, abstaining at work 1407.
The no-pruning learner's saved successful program is even parity guarded
`DROP_LAST(EvolvedMacro(seq_macro_4: DROP_LAST(x)))`. That macro remains active
and Tier1 applies a unary wrapper. Full's saved `pruned_operators` includes
`seq_macro_4`; its failed row has eight cold operators, no used operator and
both support gates false. No private outcome fed back into the frozen learner.

The old cold path tries bare archived transforms but does not give every cold
transform the active unary/affix beam. Atomic discovery cannot repair the
specific omission: its size3 list includes CONCAT and literal affixes but
omits unary-of-unary expressions; its generic loop begins at size4. It also
admits size6–7 affix wrappers using observed wrapper hints, while unary outer
wrappers are suppressed by a length-hint boolean. Therefore reachability can
depend on whether a reusable operator is active, cold or absent, despite the
nominally shared typed language.

These saved records plus static code identify the missing construction paths.
They are not a counterfactual rerun proving that one particular patch repairs
the closed case. New source fixtures test the construction invariant without
reopening w15f_*.

## Additional disclosed limitations

Wave15 scans all archived operators. Dictionary removal of an identified
operator is constant time, but candidate discovery and verification are not.
Wave15 also tries an existing cached piecewise certificate before full atomic
enumeration. That was disclosed before evaluation; it is not an isolated
support-abort ablation or unchanged exhaustive search order.

Wave16 will restore a shared structural atomic order and test active/cold
one-step composition equivalence. Reference signatures are candidate indexes,
not proof that arbitrary unseen inputs or constant-dependent guards match.
Lookup, signature construction, collisions and public verification must be
charged and reported separately. O(1) hash access is not O(1) total verification.

## Three historical regression assertions

The Wave8–15 regression invocation reproduced **54 passed, 3 failed** in 4.70 s.
The failures are Wave12/13/14 `test_synthetic_payload_matches_runner_and_verifier_schema`.
Each calls `verify_commit1_blindness(None)`, which intentionally checks the
current pre-freeze checkout. This later checkout correctly contains those old
assessment modules. The fix changes only the tests to resolve and verify their
original freeze commits. It neither skips checks nor changes historical
learners, verifiers, assessments or artifacts. The earlier failed results stay
recorded; making phase-correct tests pass does not rehabilitate those studies.

Waves 12 (`e940b82`→`6bdf9ae`), 13 (`460a04a`→`a48001e`),
14 (`53e5317`→`ea17608`) and 15 (`4810ae65`→`9db4dc94`) remain
**Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved Unamended)**.
Track B remains closed, with zero model calls and zero frozen-ledger debit.
