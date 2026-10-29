# Erratum to `docs/NEXUS_PHASE6_NINE_PARADIGM_HYBRID_REPORT.md` (Phase 6, `e97a4c7`)

Written at the start of Phase 7 (2026-10-29) after a source audit. The Phase 6 report and its artifacts are frozen and are
**not** edited. This erratum corrects counts and interpretations. Every item was re-verified against the raw artifacts
(`artifacts/agi6_eval/*.jsonl`, `artifacts/agi6_src/*.json`) and the source.

1. **Rows.** There are 1,109 main evaluation rows and 36 panel rows: 1,145 in total. The report's "1,145 target rows"
   mislabelled the total as target rows.

2. **Wrong submissions.** The 29 accepted wrong submissions concern only **3 distinct P7 projects** (seeds 66051, 66053,
   66055), repeated across arms. They are not 29 independent failures.

3. **Admitted skills.** **Two** distinct patterns were admitted, each in **three** cohort endpoints (Full_r2,
   SolvedOnly_r2, Fixed_r2):
   - `exclude_value` with the literal `'D'`;
   - `default_fill` with the literal `0`.

   The report said one. Both are automatically abstracted **specializations of authored operators**, not new executable
   structures. Neither was discovered in all three Full repetitions.

4. **The library ablation was inert.** Every Full (A3) target invocation used `search(whole, skills off)`, the
   automatically composed procedure. So A5 "procedure only", which removed the library, could not measure library
   utility. A2 (learned memory + F0) did run with skills on, and still showed no completion benefit.

5. **Search pruning.** `pipeline6.search` kept a child only if its immediate score improved or the current checks
   passed (`pipeline6.py:513`). It recorded unchanged-feature attempts as refutations (`:518`), which received negative
   policy weight. Necessary neutral or temporarily worse intermediate steps could therefore be discarded.

6. **An unexercised improver edit.** SolvedOnly_r0 adopted `proc_cycles = 5` on a 13 % cost difference over one common
   completed project. Its comparison never ran procedure composition (the rollout clones were scored with F0), so the
   comparison cannot establish any effect of that edit.

7. **No closed learning loop.** Source training used the fixed `EXPLORE` procedure throughout. The learned procedure was
   composed only afterwards, so it never affected later source experience.

8. **Scope of the arena.** It uses restricted generated pipeline subsets:
   - P7's timestamp comparison is a row filter, not a general ASOF join;
   - P4 does not demonstrate SCD2 interval reconciliation;
   - the Scala and Jinja support are restricted adapters (a lexical Scala rewrite; `ref` / `config` macros only).

9. **Causes are hypotheses.** The report's "why it failed" list — short training, admission coverage, pruning, the gate
   gap — offered hypotheses, not four proven exclusive causes. Phase 7 tests them with a reachability diagnostic.

Phase 6 remains a negative result for its learning claims.

## Additions from the Phase 7 Stage 1 reachability diagnostic (development projects only)

10. **An unrepairable mechanism.** `de_phase4.ops.candidates` excludes the identity column `id` from every parameter list.
    So `dedup_first` can never deduplicate exact re-deliveries of a row identity, yet that is the generator's intended
    repair of the duplicate-id (P1) and fan-out (P4) mechanisms (`world6.build_stage`: dedup key `id`). Phase 6 projects
    where the legacy pipeline lacked that step had no reachable repair in the operator language.
    - Development evidence: witnesses existed for 9 / 16 projects in the Phase 6 language and for 13 / 16 once the
      parameterisation is added.

11. **A false gate rejection.** `de_accept_v3`'s `corruption` invariant appends stress rows that keep the visible rows'
    group-key values. In every pipeline that aggregates by a non-identity key, those rows legitimately change existing
    totals, so the gate rejected the legacy pipeline and every repair. This included a hidden-verified dedup-on-id repair
    (dev check `a7-s1-dbg5`). `pipeline6.closure` uses the same check to discard competitors.

Items 10–11 are defects of the Phase 6 system, shared by every Phase 6 arm. They are additional explanations for its
"no repair candidate" failures. Their share of the Phase 6 target failures was not measured: the frozen Phase 6 targets
are not reopened.
