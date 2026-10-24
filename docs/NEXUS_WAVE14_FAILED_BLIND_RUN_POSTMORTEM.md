# Wave 14 closed failed blind run — saved-evidence postmortem

**Closed Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved
Unamended).** Freeze `53e5317` → result `ea176084de46ec428806ffd1064ff728a3128501`.
No old suite is rerun and no old code, artifact or commit is amended.
SHA-256 of `artifacts/seed_wave14_piecewise_archive_enumerator.json`:
`a68e1c552dc74a5d4a028c75929b95c45ad38e913dfb38ef7a676581c963f80f`.

## Exact five-method saved totals

| Method | Correct /54 | Work | Primitive steps | Cold reactivations |
|---|---:|---:|---:|---:|
| equal_typed_scratch | 45 | 276378 | 758274 | 0 |
| ordinary_persistent_memoization | 45 | 241527 | 662359 | 0 |
| nexus_whole_macro_only | 54 | 439930 | 1126232 | 3 |
| nexus_typed_without_pruning | 54 | 779380 | 1949381 | 0 |
| nexus_typed_full | 54 | 414925 | 1051271 | 3 |

Full has zero false unique locks, 3/3 correct ambiguous declarations and 3/3
cold archive reactivations. Subtree work 40125 beats whole-macro 56683;
overall 414925 beats whole-macro 439930. But full loses suite work and primitive
cost to scratch and memoization, which solve only 45/54. The registered suite
gate required all comparisons, so greater accuracy cannot upgrade the failure.

## Root cause and exact task/bucket distinction

The saved task ID is `w14f_oog_pair_swap` (not `w14f_oog_pairwise_swap`).
After single-branch search fails, `synthesize_wave14` unconditionally enters
`_synthesize_two_branch`, which builds `_transform_pool` and nested transform/
guard loops, even when cached strict-residual evidence cannot support branches.
Preferred macro-expanded transforms are admitted by the old pool regardless of
their residual support. There is no pre-piecewise two-transform cover check.
This explains the code-level opportunity; the saved logs do not themselves
contain every transform coverage mask, so zero useful coverage is a hypothesis
to test on new unit fixtures, not a newly measured property of the closed task.

The request's 260268 full /44400 scratch totals refer to the **entire OOG-plus-
ambiguous split**, six cells. The pair-swap task alone is 260187 versus 44319
(three seed cells); each method spends another 81 on the ambiguous task. Both
comparisons yield exactly **215868 excess work**. Per-seed full OOG work is
82930, 82930 and 94327.

Likewise full154657 /memo197127 /scratch231978 are the **other 16 tasks /48 cells**,
excluding both the OOG and ambiguous tasks. The other **17 tasks /51 cells**,
excluding only OOG, are full154738 /memo197208 /scratch232059. Full beats both
baselines in either descriptive subtotal. No task is removed from the registered
suite gate, and neither subtotal is an independent positive experiment.

## Wave 15 development intervention

Reuse the frozen typed AST/interpreter, macro library and label-blind environment
contract. Cache initial strict-residual masks while transforms are already
evaluated. Before spending additional probe/guard work, require supported
two-transform coverage. Then evaluate only covering transforms on new probes,
reuse bitmasks for guard matching and retain independent branch confirmation.
Apply identical search rules to all five methods. No learned task literals,
hidden labels, Track-B model calls or historical suite reuse.

Waves 12 (`e940b82`→`6bdf9ae`), 13 (`460a04a`→`a48001e`) and 14 remain
**Developmental / Invalid (Failed Single-Shot Blind Gates; Preserved Unamended)**.
