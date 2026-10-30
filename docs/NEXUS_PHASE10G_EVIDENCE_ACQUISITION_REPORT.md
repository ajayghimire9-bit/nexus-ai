# NEXUS Phase 10G — learning what evidence to obtain next (NOT LOCKED)

## Revisions and scope

| Item | Revision |
|---|---|
| Start | `a3cad78` |
| Commit 1: protocol, 10F closure, 104529 fix, evidence channels, manifest | `4c0c7cc` |
| Training and freeze | `172d5fc` |
| `main` | `d7ac8c5`, untouched |

- **Protocol:** `docs/NEXUS_PHASE10G_PROTOCOL.md`.
- **Raw data:** `artifacts/agi10g_train/`, `artifacts/agi10g_eval/rows_c*.jsonl` and `artifacts/agi10g_eval/result.json`.
- **Logs:** `artifacts/mi_logs/a10g-*`.

**Question.** With the same atomic-dedup, learned-guidance solver in every arm, can experience teach NEXUS **which evidence to request**
when several repairs fit everything visible? Does that beat a strong fixed investigation rule on fresh withheld compositions and
ordinary tasks?

## Answer in one paragraph

**Yes on the pre-registered primary test, but for a narrow, designed reason.**
- On the 24 withheld compositions at one evidence request (B_ev = 1), the learned policy E3 verifies **24 / 24 in both streams**,
  against 18 / 24 for the fixed operator-type rule E2: **+6 in both streams, 0 wrong** (verdict *learned beats fixed*).
- E3's requests split the tie **100 %** of the time, against 74 % for E2 and 26–34 % for random.
- **The whole advantage is one mechanism.** Ties on the event-time dedup of the CDC relation need the boundary / late channel. E2's
  fixed rule sends every dedup tie to the replay channel, as disclosed in the protocol before any outcome.
- With **two** requests (B_ev = 2), E2 recovers and **matches E3 exactly**, at 117 more evaluation executions and no learning cost.
- E3's learning cost was about 1,875 exploration executions per stream. So the learned policy pays off only when evidence requests
  are scarce, and a fixed rule that also looked at relation roles would match it.

## 1. Phase 10F closure (Stage 1)

**Step-50 support.** Each stream had **1** verified project whose replay source kept `ckey` on the partition key (rep0 104028, rep1
104548), below k_min = 3. That is why no rule had the macro at step 50. k_min stayed 3.

**Attribution** on the 22 consumed 10F targets (owner-requested post-hoc diagnostic; frozen 10F code):

| Solver | Held-out of 22 | Executions | Macro used |
|---|---|---|---|
| Abs_subgroup rep0 / rep1 (re-run) | 22 / 22 | 2,805 / 2,526 | L7 / L6, identical to 10F row by row |
| **Abs_current** rep0 / rep1 | **21** / 22 | 6,015 / 2,526 | none / L6 |
| rep1 A4, **only L10 removed** | 22 | 2,526 | L6 |
| rep1 A4, **only L6 removed** | 22 | 2,403 | L10 |
| rep1 A4, both removed (10F A4f) | 4 | — | — |

So 10F's 18-target A4f drop needed **both** rep1 macros removed: L10 alone is not what A4 used. Abs_subgroup's final solver beats
Abs_current's by 1 target in rep0 and ties in rep1.

## 2. Task 104529 (Stage 1), mechanism confirmed

- **What happened:** the path partitioned `stg_orders` by a distractor (`tax_amount`) that collides once on visible batch A. It
  dropped an order no visible output reads, and enabled the post NOT NULL filter. 20 of the 25 accepted paths of that shape are
  hidden-wrong.
- **Fix, `dag10g.necessary_dedup`:** a dedup whose key is not a documented unique key must be **necessary**. The spec without it,
  post filters moved to pre, must fail a visible check.
- **Unit test:** 104529 rejected, truth accepted, rule uncharged.
- **Dev re-check:** 15 stored accepted paths → 0 accepted. Truth false rejects 0 / 10.
- **Training wrong submissions in Phase 10G: 0 / 240.**

## 3. Training (Stage 2)

| | rep0 | rep1 |
|---|---|---|
| Tasks | 120 | 120 |
| Verified / wrong | 114 / 0 | 117 / 0 |
| Training ties (all 5 channels explored) | 30, all resolved | 30, all resolved |
| Wake search executions | 10,279 | 8,327 |
| Exploration evidence executions | 1,880 | 1,870 |
| Wall time: wake / abstraction / dreams / evidence (s) | 97.7 / 34.8 / 45.1 / 7.7 | 84.7 / 25.6 / 43.5 / 7.1 |
| `pi_ev` | 30 records, 120 pairs, train pair accuracy 1.0, 0.0014 s | same |

**Training signal.** Gain(e | C) = 1 iff channel e eliminated ≥ 1 tied candidate and left a survivor that verifies on the hidden
batches. That is training feedback only; no evaluation target was used.

**Features:** the differing operator, DAG node, relation roles, the differing slot, the roles or literals of the tied values, and |C|.

## 4. Evaluation (Stage 3, fresh one-use 108000–108047)

- **Coverage:** **768 / 768 rows, 0 missing, 0 wrong.**
- **Shared work:** per stream, 35 of 48 targets reached a tie (33 designed + 2 incidental). The remaining 3 time-mechanism targets
  are searches that found no candidate.

**Verified completions at B_ev = 1, of 24**

| Arm | Withheld rep0 | Withheld rep1 | Ordinary rep0 | Ordinary rep1 | Hit rate | Ties resolved (of 35) | Eval executions |
|---|---|---|---|---|---|---|---|
| E0 no evidence | 4 | 4 | 6 | 6 | — | 0 | 5,584 / 5,619 |
| E1 random | 11 | 9 | 11 | 10 | 34.3 % / 25.7 % | 12 / 9 | 6,027 / 6,061 |
| E2 fixed rule | 18 | 18 | 18 | 18 | 74.3 % | 26 | 6,033 / 6,068 |
| **E3 learned** | **24** | **24** | **21** | **21** | **100 %** | **35** | 6,033 / 6,068 |

**By mechanism** (withheld + ordinary, of 12 each, B_ev = 1, both streams):

| Arm | seq | time | grain | none |
|---|---|---|---|---|
| E2 | 12 | **0** | 12 | 12 |
| E3 | 12 | **9** | 12 | 12 |

- The 3 time-mechanism misses are the ordinary T_tombstone+qualify_order targets, where the shared search used its whole 600
  executions without a candidate (every arm misses them).

**Pre-registered contrasts (withheld, B_ev = 1)**

| Contrast | rep0 | rep1 | Verdict |
|---|---|---|---|
| **H1 E3 − E2** | **+6** | **+6** | **learned beats fixed** |
| H2 E3 − E1 | +13 | +15 | positive |
| H3 E3 − E0 | +20 | +20 | positive |

- Ordinary (secondary), E3 − E2: +3 in both streams.

**Sensitivity, B_ev = 2:** E2 reaches 24 / 21, identical to E3 (E3 − E2 = 0), at 6,150 / 6,185 executions against E3's
6,033 / 6,068. E1 reaches 12 / 12 and 12 / 14.

**Total cost (executions):**
- Shared solver learning: about 10,279 / 8,327 wake search executions (178 / 154 s).
- E3's own learning: about 1,875 exploration executions per stream, plus 0.0014 s of `pi_ev` training.
- Evaluation:
  - at B_ev = 1, E3 = E2 in evaluation executions;
  - at B_ev = 2, E2 costs 117 more evaluation executions, but E3 carries about 1,875 executions of exploration;
  - at B_ev = 1, E3's extra cost buys +6 withheld and +3 ordinary completions.

## 5. What this establishes and what it does not

**Established (NOT LOCKED, 2 streams, one fresh draw):**
- With identical solvers, a policy trained only on self-discovered "did this evidence split the tie" outcomes learned to send
  CDC-relation dedup ties to the late-arrival channel and item-relation dedup ties to the replay channel.
- It then transferred to withheld cross-node compositions with 100 % hit rate and 0 wrong.
- The ambiguity guard worked: every unresolved tie abstained, so there were **0 wrong in 768 rows**.

**Not established, or limited:**
- **Narrow advantage:** it comes from one designed mechanism where the operator alone is uninformative. A fixed rule conditioning on
  relation roles, or E2 with a second request, matches it.
- **Decoy channels:** channels 4 and 5 were bland decoys by design, which inflates the gap to random.
- **World design:** the evidence world (mechanisms, channels, the relevance mapping) is human-designed.
- **Not learning-to-learn:** the policy is a learned lookup over tie signatures.
- **Incidental ties:** 2 of 12 no-mechanism withheld targets (W8) had incidental CDC dedup ties that the dev check did not show;
  channels 1 and 2 both resolve them.
- **Solver limit:** 3 ordinary T_tombstone+qualify_order targets are unsolved by the shared search in both streams.

## 6. Recommended next experiment

Make the fixed baseline as strong as possible, and make the mapping genuinely non-obvious.
- **Baseline:** pre-register an E2⁺ rule that conditions on operator **and** relation roles.
- **World:** add mechanisms where the relevant channel depends on data properties no simple rule reads. For example, the same dedup
  tie on the same relation needs the replay channel in one producer regime and the lineage contract in another, signalled only by
  visible statistics.
- **Tests:** whether learned evidence selection beats the best hand rule at B_ev = 1, and whether `pi_ev` adapts online to a new
  mechanism-to-channel mapping within a few tasks.

## 7. Budget, ledger, protection

- **Budget:** **685.2 of 1,300 s** (s1 160.8, s2 334.3, s3 172.5, s4 17.6, plus this commit's ledger export). Grant remaining about
  926 s.
- **Ledger:** `docs/NEXUS_COMPUTE_LEDGER.json` re-exported. `python scripts/agi10f_ledger.py verify` passes the chain, sums and the
  10C → 10G pool reconciliation.
- **Protection:** 0 violations (`artifacts/agi10g_protect_before.json` and `artifacts/agi10g_protect_after.json`). 2,775 frozen
  files unchanged; checkers v1–v5 match their pins; `main` is `d7ac8c5`.
- **Tests:** `tests/test_agi10g.py` (8), 10F (12), 10E (9) and the checker-kernel tests pass.
