# Wave 24 AZR–Ruler–CEGIS: pre-freeze report

Updated 2026-10-25. **Latest: v2 suite (protocol locked at `ccacbb3`), evaluated once on fresh
seeds 201–205 (274 s). Independent verifier: 21 / 25 gates pass, 0 false certificates
(v1 + v2 rows), verifier exit 1. Failed: V2-G4b (more solved on every seed — seed 202 tied
184 = 184), V2-G6a (≥ 15 layer-2 witnesses on every seed — seed 205 had 7), V2-G3b (useful-branch
ratio rise, p = 0.61), and the v1 regression gate G2b (source transfer 602 vs 607 solved). Nothing
was retuned after evaluation.**

## Latest: v2 suite — wake-sleep, deep hierarchy, skeletons, wild arena (seeds 201–205)

Linux cloud clone, CPU only, no LLM. Result `artifacts/wave24_agi_gap_suite_v2.json`
(`b6e2acec48b2529c42a91c1c9912a66d542a55f043d31a49754dafde8c5f0f72`), verification
`artifacts/wave24_agi_gap_suite_v2_verification.json`
(`58dc4f9a6af3420f1862e32e7c133871f332a5b63623c02802562134cd8b346f`). Dev seeds 1–5 only were
used for development; the declared world assumption (idiom streams with shared structure) and all
known dev risks are in the protocol.

### `a9ef200` (seeds 101–105) vs v2 (seeds 201–205)

| Gap | a9ef200 | v2 on seeds 201–205 | v2 gate |
| --- | --- | --- | --- |
| 4 self-evolution | FAIL: idle exploration cost 114k to save 4.6k, 0 helpers, 306 vs 307 solved | Wake-sleep, no blind rollouts. Promoted 20–24 helpers per seed, used in 36–64 certified answers per seed. Total work incl. ALL sleep/shadow/bridge/setup **lower on every seed**: 1.051M<1.066M, 0.955M<0.966M, 1.223M<1.243M, 1.184M<1.343M, 1.268M<1.326M. Solved **177>175, 184=184, 165>160, 172>158, 166>158**. | G4a pass, **G4b FAIL (seed 202 tie)**, G4c pass |
| 6 hierarchy | FAIL: 0 layer-2 witnesses | Certified layer≥2 witnesses **25 / 27 / 35 / 48 / 7**; layer-3 witnesses 0/0/4/5/1. Depth≥5 tasks: evolved 116 vs layer-1-cap 108 vs no-evolution 106 (pooled; ≥ on every seed). Parameterized guards / fitted-threshold FILTER and ITERATE loops are in the grammar. | **G6a FAIL (seed 205)**, G6b pass |
| 2 cross-family transfer | partial (law flags only) | Skeleton + policy + relevance transfer **302 vs 183** solved, 3.21M < 3.58M work vs law-only. **But the same learner with no source training solves 346 at 2.94M** — the transferred relevance model hurts; learned transfer is not demonstrated. | V2-G2 pass (as specified); negative vs no-source reported |
| 3 learning-to-learn | partial | Meta late-domain acquisition work < reset on **every** seed (71k<81k, 39k<50k, 68k<79k, 82k<91k, 72k<80k). Useful-branch ratio rises in only 9/15 (seed, order) pairs (p = 0.61). | G3a pass, **G3b FAIL** |
| 8a language | keyword overlap (205 vs 111 on planning) | Compositional clause parser with edge-case oracles + paraphrased wording: **80/80 vs 17/80** solved, 1.3k vs 13.9k work, per-task p = 2e-19 (parser and specs share an author — not held-out NL understanding). | pass |
| 8b intrinsic goals | 14 vs 19 tasks, p = 0.49 | Goal = own failure residuals, re-attacked in governed sleep: **164 vs 116 (undirected) vs 106 (none)** solved; per-task p = 1.7e-4 vs undirected, 2e-9 vs none. | pass (both) |
| Wild arena | — | QuixBugs 11 held-out programs × 5 test splits: learned (Ochiai FL) **16 vs 15 correct**, 26 vs 26 plausible, 3.04M < 3.50M line-events; repaired programs: bucketsort, find_in_sorted, next_permutation, rpn_eval (most failures need multi-edit or non-modelled edits). Law discovery **34/35 vs 6/35** (MDL vs linear). | W1, W2 pass |
| v1 regression | 14/16 | G1 every seed (167–184 vs 157–170 solved; 269k–381k vs 438k–495k total work), G2a, G3, G5, G7, G8a pass; **G2b FAIL**: source transfer 602 vs 607 solved (work 736k < 757k) — a regression introduced by v2 core changes. | 10/11 |

### Example certified layer-2 / layer-3 witnesses (unfold to primitives for verification)

```text
seed 201 LIST_INT      L2  ['macro[MAP(square)>sum]']
seed 203 INT           L3  ['double', 'macro[dec>macro[macro[inc>mod10]>square]]']        (primitive depth 5)
seed 203 STDLIB_BYTES  L3  ['macro[MAP(inc)>macro[MAP(double)>MAP(dec)]]']
seed 204 CELL_AUTOMATA L3  ['macro[macro[invert>MAP(inc)]>try[step30|live]]']               (recovery inside a macro)
seed 204 NUM_SERIES    L3  ['macro[macro[MAP(dec)>MAP(not1)]>normalize]']
```

Example real QuixBugs repairs (seed 201): `rpn_eval` swap_args line 4; `next_permutation`
negate_condition line 6; `bucketsort` name_replace line 7. Plausible-but-wrong patches (pass
public tests, fail held-out ones) occur: 26 plausible vs 16 correct.

### Cost accounting (gap 4, per seed; every unit on one meter)

| Seed | Evolved stream + setup | Sleep (shadow + bridges) | Evolved TOTAL | No-evolution TOTAL |
| --- | --- | --- | --- | --- |
| 201 | 958,005 | 93,307 | **1,051,312** | 1,066,128 |
| 202 | 881,676 | 73,483 | **955,159** | 966,189 |
| 203 | 1,110,614 | 111,891 | **1,222,505** | 1,243,057 |
| 204 | 1,066,243 | 117,326 | **1,183,569** | 1,343,425 |
| 205 | 1,135,045 | 132,893 | **1,267,938** | 1,326,045 |

### Tests

`pytest tests/ -k wave24 -v -W error::RuntimeWarning`: **214 passed, 1 skipped, 0 failed, 0
warnings** (the GGUF cross-family test skips with an explicit reason when the local weights are absent).

### v2 source SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_skeletons.py` | `0e4a8a6d8b875457105799fd8bc5c41bd7953b9421774e43c39cdd72a29d5c6d` |
| `src/nexus/wave24_wake_sleep.py` | `d66c440fcc5a076a957ea3932b5d4dbc3b25664744e2688a18c9c3df8fbf5b8c` |
| `src/nexus/wave24_semantic_spec.py` | `884462250b9a3d0d71a7c315ab2dcc517063e661d8fad00cfb933baca0bed1f2` |
| `src/nexus/wave24_code_repair.py` | `0db05a6f78df7e6f57f716472565837904a023d5150e6e89d83fc3123f360bf2` |
| `src/nexus/wave24_agi_benchmarks_v2.py` | `b26d5d5c06a69df722ebfba1fbdd1aa8a2aa3850fdf52b1a0675ee37bca89d7e` |
| `src/nexus/wave24_agi_suite.py` | `449f56ca498a324b3f8d46462201e73c6b5de02c0d794d2ec34129fb14db532b` |
| `scripts/run_wave24_agi_gap_suite.py` | `fabad0b86da3e5462f83ca3d3c2bb3940662a89b9ed88d076f62df37166620d2` |
| `scripts/verify_wave24_agi_gap_suite.py` | `8c7958aaa877afb5d1cab7415a62fdacb87ad1a22b95bd0bdf6426f9abaab7b3` |
| `docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md` | `d92eb8d85ce8fdc0500bc76a6efc14eb8541bc65292ff1e6b6f8441d7b92f0c8` |
| `tests/test_wave24_v2_mechanisms.py` | `329b48ad2afb82c12950d57e81965bed3b6562cfb924378cd0d6dc9c252524cb` |
| `fixtures/quixbugs/split.json` | `07b6270ee8badcaf18e72ca89c4c4680ad1e156be09cb2fb1552ced9b5aa9b68` |

### What the evidence does and does not establish

Established on this suite: profitable shadow-gated self-evolution under full cost accounting on
streams with recurring structure; certified layer-2/3 abstractions that unlock deeper tasks;
compositional spec parsing with edge oracles; failure-driven goal setting that beats undirected
self-training per task; real third-party program repair and law discovery. Not established:
learned cross-family transfer beyond a generic skeleton library (negative), a rising useful-branch
ratio, more-solves on every seed, ≥ 15 layer-2 witnesses on every seed, open-ended or general
intelligence. The idiom-stream world assumption is what makes self-evolution pay; uniform random
streams (v1) do not reward it.

**Next experiment:** fix the v1 G2b regression and the harmful transferred relevance model (gate
relevance transfer by leave-one-domain-out validation, as the force policy already is), then test on
fresh seeds.

## Historical: eight-gap capability suite (a9ef200) (protocol `docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md`)

Environment: Linux cloud clone, Python 3.13.17, CPU only, no LLM (grounding is
symbolic TF-IDF over the tools' own docstrings — the local Qwen GGUF is absent).
Standing development grant: one evaluation launch, wall **63.7 s**, CPU 63.4 s
(< 900 s cap); ledger `runs/experimental/wave24-agi/ledger.jsonl`.
Development used seeds 1–3 only; all design choices (including raising G2's
stream length and the meta-decision rules) were made on dev data before the
evaluation seeds were run. Result: `artifacts/wave24_agi_gap_suite.json`,
verification: `artifacts/wave24_agi_gap_suite_verification.json`.

**What this is:** a procedural suite of 8 families (3 seen, 5 structurally
disjoint targets) with unwrapped tools whose faults are real exceptions, a
uniform cost meter that charges every tool application, probe, prediction,
training row, projection, law check, self-task proposal, meta-learning step
and counterfactual, and a strong exhaustive quotiented baseline. **What this is
not:** general intelligence, open-world competence, or learning-to-learn
beyond these authored domains.

### Gate results (eval seeds 101–105, α = 0.05, exact sign tests)

| Gap | Before (v12) | After: measured on eval seeds | Gate |
| --- | --- | --- | --- |
| G0 integrity | arena-only recount | **0 false certificates** over 6,980 solver rows; wrong-unique answers ~2% for learned AND fixed alike (minimal-depth convention), 0 for the grounded planner | **pass** |
| 1 full-cost improvement | single dev seed, arena only | Every seed: learned **176/173/181/174/180** vs fixed **152/162/163/157/160** solved; learned TOTAL work (incl. all overhead) **322k/361k/329k/314k/305k** vs fixed **492k/482k/438k/498k/469k**. Arena 16 > 11, 3,267 < 4,163. | **pass** (G1a, G1b) |
| 2 zero-shot transfer, 5 targets | 3 reported bindings, no effect measured | Transfer vs fixed per target (solved, work incl. target probing, p): CELL 86=86, 243k<281k, p=1.6e-4; GRAPH 109>105, 66k<176k, p=3e-16; NESTED 134>106, 164k<474k, p=2e-28; SERIES 142>133, 160k<267k, p=8e-10; STDLIB 117>65, 138k<434k, p=2e-36. Max solved depth ↑ in 3/5 targets. Source-transferred vs untransferred learner: 588 vs 587 solved, **771k < 829k** work, 470 vs 83 tasks, p=1e-66. | **pass** (G2a, G2b) |
| 3 learning-to-learn | none | Meta ρ(position, acquisition work) **−0.85/−0.44/−0.23/−0.62/−0.75** vs reset **−0.26/+0.36/+0.42/0.00/+0.04**; meta late-domain work 45–65% of its early-domain work. Mechanism: retiring a force policy that fails LODO validation, gating forward-model pruning by measured payoff, skipping exploration that does not pay, skipping law validation once evidence suffices. Caveats: meta late-domain cost is NOT below the reset control in 3/5 seeds; stepping-stone precision does not rise with position. | **pass** (G3) |
| 4 self-evolution, closed loop | 0 graduations in v11, disconnected | Idle exploration (fault-boundary memory, model transitions) makes the evaluated stream cheaper on 96 vs 7 tasks (p=4e-21; 378.7k vs 383.3k) but solved **306 vs 307**; idle cost 114k ≫ 4.6k saved; **0** helpers met the ≥3-gain promotion criterion; 16 helpers retired under shift. | **G4a FAIL**, G4b pass (vacuous: no promotions), G4c pass |
| 5 open-world robustness | wrappers swallowed faults (fixed in v12) | Messy tasks 62 vs 56 solved; **33** certified witnesses whose try/except actually caught an exception; bounded projector 1.05 ms at 10⁴ vs 1.06 ms at 10³ (exact: 51.8 ms); 12 raw stdlib callables ingested. Approximate-law slack test non-discriminative (8/8 both). | **pass** (G5a–c) |
| 6 hierarchy | playground-only layers | Certified eval witnesses by max layer: **796 layer-0, 88 layer-1, 0 layer-2** (layer 2 appeared once on dev seed 1 only). Parameterized guards not implemented. | **G6 FAIL** |
| 7 predictive world model | none | 449 vs 410 solved, **795k < 1,192k** work (356 vs 148 tasks, p=8e-21); type-prediction containment 1.00; retention of fixed-solved tasks 0.993. | **pass** |
| 8 grounding / planning / goals | none | Degraded-text grounded planner, depth 4–6: **205 vs 111** solved, 363k < 927k work, p=6e-18. Intrinsic goals: directed 117 = undirected 117 solved, 173.6k < 181.7k work — gate passes, but per task 14 vs 19 favour **undirected** (p=0.49): **no significant benefit**. | pass (G8a); G8b pass but not significant |

### Full cost accounting (gap 1, per seed; all units on one meter)

| Seed | Learned eval | Learned overhead (laws, probes, model, policy, meta, exploration + counterfactuals) | Learned TOTAL | Fixed TOTAL | Solved L / F |
| --- | --- | --- | --- | --- | --- |
| 101 | 279,633 | 42,477 | **322,110** | 492,044 | 176 / 152 |
| 102 | 318,440 | 42,739 | **361,179** | 482,407 | 173 / 162 |
| 103 | 291,663 | 37,794 | **329,457** | 438,291 | 181 / 163 |
| 104 | 270,070 | 43,912 | **313,982** | 498,189 | 174 / 157 |
| 105 | 256,878 | 48,237 | **305,115** | 468,946 | 180 / 160 |

Each seed: 208 tasks (8 domains × depths 2–4 × 8, plus messy recovery tasks).
Learned wins come mostly from the forward world model and law pruning; the
transferred force policy was retired by its own LODO validation in every run.

### Reproducibility

Result `artifacts/wave24_agi_gap_suite.json`
`d80c15995000352cb54dd5b0a8a54a1cd8dcfd33938468be7dc7f31c224cf7a0`;
verification `artifacts/wave24_agi_gap_suite_verification.json`
`f0a1fbc207dc93c5200694a9d9ff454973bb3c896a5d991d17fdede5075b9353`.
Reproduce: `python3 scripts/run_wave24_agi_gap_suite.py --out <new path>` then
`python3 scripts/verify_wave24_agi_gap_suite.py <new path>`.

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_domains.py` | `0fd77ea52ff586f1b93b20a423b80342aef36ad2f2f483b8a950f32d8bfc7af0` |
| `src/nexus/wave24_agi_suite.py` | `13565a658b067eefafc1bbc488bfb7f8eacb47e4ac336259d36e260a0cd18c90` |
| `src/nexus/wave24_agi_benchmarks.py` | `5efc652c26e41ce0847ac656714eaf99b4ea88efe14464babf60889e333b5c45` |
| `src/nexus/wave24_auto_laws.py` | `b63f3a25fe860d5035beb3b0e85416fed4245c2ae4b3374cc23b7c45aa514491` |
| `scripts/run_wave24_agi_gap_suite.py` | `29f85a8d4f86bb7e21be23debe152d7c4be2899f0593cbd12cecfadad706ead5` |
| `scripts/verify_wave24_agi_gap_suite.py` | `965505d1393efc511c07a85527de4b99bfda1fb1f9270b3598a119f15b95ee62` |
| `docs/NEXUS_WAVE24_AGI_GAP_PROTOCOL.md` | `a1341a5b8f0aad4c01366e127262c8da599517309d0b2adce5edadd67597ee0c` |
| `tests/test_wave24_agi_suite.py` | `e9ca39663749c0457f34c566aafff7d79a66ca8db53ac908763aff330c87a023` |

Tests: `pytest tests/ -k wave24 -W error::RuntimeWarning` → **204 passed, 0
warnings, 1 failed** (cross-family test needs the local GGUF model).

### Negative findings worth keeping

- Force-level stepping-stone pruning rates learned on source families do NOT
  hold on targets (LODO recall 0.70–0.95 < 0.95 floor); the learner retires it.
  Transfer that works here is meta-knowledge about which algebraic law families
  are reliable, plus the general machinery.
- Exploration that adds macros pollutes the toolbox; only knowledge-type
  discoveries (fault boundaries, transitions) transfer safely, and their value
  does not repay idle cost within ~25-task streams.
- Goal-directed exploration has no measurable advantage over undirected
  exploration with this explorer.

**Next experiment:** make composite discovery generalize (gaps 4/6): promote a
composite only when it lowers work on held-out *stream* tasks via shadow
evaluation, and test on a task distribution with genuinely recurring
sub-pipelines, on fresh seeds.

## Historical: guidance v12 — atomic forces, force-pruned 2-hop, raising playground primitives

### Execution environment and ledger

Same fresh Claude Code cloud clone as v11 (Linux, Python 3.13.17, torch
2.14.1+cpu, CPU only, no MPS, no LLM), **not** the owner's M4 Mac. Branch
`codex/wave24-azr-ruler-cegis`; implementation committed as `4bec9de` before
launch. The v11 receipt is present in this clone's
`runs/experimental/wave24-azr`; v6–v10 receipts remain only on the Mac. v12
used the owner-authorized `session_refresh_s=60.0` path. Treat v12 as
consumed everywhere; do not relaunch.

### What changed

1. **`AtomicFieldProjector` / `AtomicForceClassifier`** (`wave24_auto_laws.py`).
   One O(N) pass maps any value to atoms (str/list/tuple: index→element;
   dict: key→(key, value); set: element; int: bit atoms + sign, mass = bit
   width) and an `AtomicSignature(mass, locus_mask, quantum_multiset_hash,
   quantum_bloom_64, bond_bitmap, binding_hash)` using blake2b-seeded
   `splitmix64`. **Deviation from the brief:** a sixth field `binding_hash`
   (XOR over (locus, quantum)) is required, because XOR over coordinates alone
   is permutation-invariant and cannot detect `F_TRANSLATE`. Container→scalar
   transitions are `F_CONDENSE` (incomparable masses). A callable showing
   different non-identity forces on different probes is `F_BRANCH`. Roles are
   empirical probe priors, never soundness proofs.
2. **`UniversalForceFunctor`** (`wave24_self_evolving_loop.py`): lifts a
   promoted 2-step skill to `(outer_force, inner_force)` and instantiates it
   on any force-fingerprinted grammar. Source preparation lifted 10 functors
   and bound **3** onto World 5 (`[F_TRANSLATE, F_TRANSLATE]`,
   `[F_TRANSLATE, F_TRANSMUTE]` ×2) with zero target tasks. These bindings are
   **reported, not installed**, so the registered fifth-world matrix library is
   unchanged; the 3 installed transfers remain the existing role-functor ones.
   The playground persists force functors to `universal_meta_recipes.json`;
   the arena learns them online and uses them to order 2-hop search.
3. **Open-world arena** (`wave24_open_world_arena.py`), default
   `force_two_hop=True`. After guided hop-1 returns `NO_PROGRAM`:
   (a) `PromotedChainLibrary` — previously solved 2-hop chains; certified
   only if all fitting promoted chains agree (space = hop-1 ∪ library);
   (b) `ForcePrunedResidualTwoHop` — stepping stones restricted to the public
   mass-deficit force direction and required to move every public mass
   strictly toward its target (a **declared heuristic restriction**), then an
   O(1) b_rem==1 law prune (mass-preserving / contractive / multiset-preserving)
   before evaluating op_2 — sound, and uncharged exactly like the engine's
   existing Noether skip; certified only if every fitting chain in the declared
   space agrees; (c) the honest piecewise synthesizer from v11. A per-task
   evaluation cache charges each op(x) once.
4. **v10/v11 accounting bug fixed.** When guided hop-1 failed, an unguided
   hop-1 fallback ran and its work was added only if it solved the task. In the
   v11 code it never solved one (same bounded space) yet consumed ~2,200 units
   that were not attributed to the evolving method. v11's piecewise-solved
   task alone omitted 214 units: **v11's honest work/solved was 141.25, not
   123.42** (still < 149.36). v12 runs the fallback only after a guided budget
   exhaustion and always counts its work.
5. **Playground primitives raise.** The int wrapper no longer returns `x`
   on a domain fault; it raises `ValueError` (search grammar sees `EXEC_ERR`).
   Compiled `_apply` raises on non-integer results. A fault-recovery phase
   synthesizes `try/except` skills from `ok[op]` guards; compiled-vs-plan
   checks compare outcomes including raised exception classes. A toolbox
   compiled under the old swallowing `_apply` is archived to `legacy_*/`
   (v11 sandbox brain → `legacy_d44bcb8f/`). Graduated skills keep receiving
   counterfactual utility; cumulative < 0 evicts.
6. Verifier: recomputes and gates matched-subset work from saved cells.

### v12 confirmation gates

| Gate | v12 measured outcome |
| --- | --- |
| Parent CLI exit | **0 on Pass 1.** `integrity_valid`, `scientific_gates_passed`, `ready_for_freeze`, `replayed` all true; `errors=[]`. |
| False certificates | **0** — matrix (100/100 cells), streams, arena (re-executed and recounted). |
| Identical-library guidance | **Cleared.** 517 < 545. |
| Streams / lifelong | **Cleared.** 12/12 > 11/12; training-inclusive 7,027 < cache 8,749 (< fixed 13,649); `lifelong_learning_demonstrated=true`. |
| World 5 (`BIT_CELLULAR_AUTOMATA`) | **Cleared.** 0 self-play tasks, 0 training rows, 3 installed zero-shot role transfers + 3 reported force-functor bindings; deep target (teacher cost 4) solved zero-shot: doctor 561, unguided 577, source-free 881 work. |
| Open-world solved | **16 > 11** static/unpruned, > 4 LLM baseline. |
| Open-world work/solved | **137.875 < 149.36.** Brief's stretch target `< 135.0` **not met**. |
| Matched subset (11 tasks both solve) | **1,293 < 1,643.** Total work 3,267 < 4,163. |
| 2-hop cost | Force-pruned 2-hop residual 38 and 82 work (v11 unpruned engine: 653 / 913). Promoted-chain siblings 8 work each (brief asked 2–5). Task totals include the failed guided hop-1 (102–200) that must precede them. |
| Lyapunov / ATP | `[1,2,3,4,5]`; ATP 100.0, entropy 0.9536, freeze 0, drift 0, 10 distractors quarantined. |
| Session remaining | **52.95 s** — > 50 gate, **below the > 55.0 target**. |
| Runtime | Worker 7.005 s (internal 5.62 s), replay 0.046 s, peak RSS 237.0 MiB, cap 15 s. |

Payload `COMPLETE`, `source_manifest_version=11`, embedded payload SHA-256
`143d19bd2db42691845523e330c1447c79f2e68ff540be29b5dde367f6f23df8`.
Receipt bytes: `worker.json`
`90c2990cd5c449b321889bfeac802bd257aeacb5eb153a7aba8651c3a257785a`,
`receipt.json` `4a08939ab99c44e02d6efdb2a886e5b47c25df10e09800d2c1fd1c1ea524b3cd`,
`complete-receipt.json` `67768e081d874ef18fc7adcc2ec3dd57725765ef5c4300e51cca191e91f50096`,
`verifier.json` `affa86564a9dc8d7b66f30d806d11b756c1a162f2588ee2f8d55bf35acc4ad28`.

**Dev-set caveat.** The arena's 24 tasks are authored development tasks that
were inspected while designing v12 (residual-before-piecewise ordering, cache,
fallback rule). The 16 > 11 result is source development evidence on seen
tasks, not held-out validation. Capability flags 6/7; arbitrary depth stays
false; not general intelligence.

### Tests

`pytest tests/ -k wave24 -W error::RuntimeWarning`: **191 passed, 0
warnings, 1 failed** — the failure is
`test_seed_wave24_cross_family_experiment.py`, which needs the local GGUF
model `qwen2.5-0.5b-instruct-q4_k_m.gguf` (absent in the cloud clone; it
should pass on the Mac). New `tests/test_wave24_atomic_forces.py` covers
splitmix64, projector conservation exactness, the five force roles, functor
lift/bind, force-pruned 2-hop certification, promoted-chain reuse and the v12
arena gates; playground tests cover raising primitives, a `try/except` that
genuinely fires, legacy-toolbox archiving and post-graduation utility.

### Playground (`--epochs 4 --dev-sandbox`)

Exit 0 in 0.346 s; ATP 100.0, entropy 0.739, 0 false certificates; 13
skills, `max_hierarchy_layer=9`, max primitive cost 20, constructs
`chain`/`if`/`try`; 1 graduated (`skill_0_chain_45d55644`), 12 in the cold
nursery. Persisted force functors: `[F_BRANCH,F_BRANCH]`,
`[F_BRANCH,F_TRANSMUTE]`, `[F_SELECT,F_TRANSMUTE]`, `[F_TRANSMUTE,F_BRANCH]`,
`[F_TRANSMUTE,F_SELECT]`.

```python
def skill_0_recover_17ff9193(x):        # layer 3; except fires on 8 check inputs
    if not isinstance(x, int):
        return x
    try:
        v_1 = _apply(math.cbrt, x)       # raises on non-cubes
        return v_1
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
        v_2 = skill_0_branch_d220ad09(x)  # layer-2 if/else skill
        return v_2
```

Only 1 of the 3 compiled `try` skills has a reachable `except` on the check
inputs; the other two bodies never raise there (recorded as
`except_fired_on=[]`).

### Current SHA-256 (v12)

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_auto_laws.py` | `9b1b89d4d3986dbc74bb09dfd0f85eeb5cf9db6c6574175c938d7a45b37442c5` |
| `src/nexus/wave24_self_evolving_loop.py` | `cf79658f9c233c19b8a01c7404dbff7b203603cada91fd87b7f90a0ba730f9b0` |
| `src/nexus/wave24_open_world_arena.py` | `3fa9fc663b11f0f245e94da03a2e2717a74b1afcc46ba1be23c61469f0be901b` |
| `src/nexus/wave24_unlimited_playground.py` | `0079676ef24b2ee886a5406e0cd8c8aa3819a8a59c9fc4064ba135846ad9b0ca` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `7365f787e393bcad6992539963296a233db16016882fc324ee22fa66ff8b5073` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `7a7e620bd732dab5d74536442f99be44b036b03ea2ddbd8bc4b4b5a2f2b20690` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `0b7879c05fb6e95e37042e99072023732e6acbb855924f90909c3d46611a2864` |
| `tests/test_wave24_atomic_forces.py` | `d6dbec378e4570f14f7cfdb0235a508e7803e2e631d2dd614376bfd1452b6028` |
| `tests/test_wave24_unlimited_playground.py` | `70617cc72948c6276f230e7fb103c6619e49405da7ace7172b46e3dff7369996` |
| `artifacts/wave24_living_brain_sandbox/evolved_toolbox.py` | `069581d3fcde6456e3830d2d29e7d3d75f113720dd7b16e0d34faea2e2bb9247` |
| `artifacts/wave24_living_brain_sandbox/skill_lineage.json` | `1ff00d6fda371e41ff6cd21f793e7757dfc8dd86098463a5c8e8440f8da72c61` |
| `artifacts/wave24_living_brain_sandbox/universal_meta_recipes.json` | `6a19e043c02d72d4d732e0cf8f3d983c700982966eaea593c4a76354ac481005` |

Unchanged since v11: `wave24_quotient_core.py`, playground CLI, and the other
tests. **Do not retry v7–v12.** Next scientific step: validate the force-pruned
2-hop policy on a fresh, never-inspected open-world task set before any freeze.

## Historical: guidance v11 — honest piecewise repair, unfold-before-validate, layered AST toolbox

**v12 note:** v11's arena work under-counted the unguided fallback; honest
v11 work/solved was 141.25 (see v12 item 4).

### Execution environment and ledger caveat

Executed in a **fresh Claude Code cloud clone** of
`codex/wave24-azr-ruler-cegis` at HEAD `cc837fa` plus the uncommitted v11
sources below. Linux, Python 3.13.17, torch 2.14.1+cpu (CPU only, no MPS,
no LLM). The v6–v10 `runs/experimental/wave24-azr` receipts live on the
owner's Mac and are **not present in this clone**; only the tracked v1–v5
receipts were importable. The run therefore used the owner-authorized
`session_refresh_s=60.0` path, exactly like v10. The v11 receipt was written
to this container's `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v11`
(gitignored, ephemeral). **Treat v11 as consumed on every machine**; the
receipt digests are recorded below. Do not relaunch v11.

### Integrity findings fixed before launch

1. **Open-world label leak (v10).** `ConditionalPatchCombinator.propose`
   returned a patch that memorized the failing public pairs and otherwise
   returned the base op's output; `run_open_world_arena` then looped over
   operators until `patch(query) == task["expected"]`. That is selection by
   the hidden answer. It produced the only v10 task beyond static
   (`OPEN_CODE_AND_SCHEMA_REPAIR #5`). Replaced by
   `ConditionalPatchCombinator.synthesize`: a declared finite
   `(guard, then_op, else_op)` space over a fixed task-agnostic guard family
   (`is_negative`, `is_zero`, `is_float`, `is_empty`, public-input
   `has_key[k]`, exception-safe `ok[op]`). A candidate must reproduce every
   public pair; the query is certified only if all fitting candidates agree
   (else `AMBIGUOUS_WITNESS_FOUND`). The expected label is used only for
   grading after the choice is locked. Escalation runs only when hop-1 found
   no unique program and some op fits some public pair.
2. **Arena false-certificate count was hardcoded `0`.** Every claimed
   arena certificate is now unfolded (`unfold_to_primitives`) and re-executed
   on public IO and the query; the verifier independently recounts failed
   certificates, requires `certificate_valid is True` on every solved
   non-LLM cell, and recomputes `method_summary` from the cells.
3. **Arena fuzz was a no-op** (it classified `expected` against itself).
   `OpenWorldTwinFuzzer.probe` now runs the certified program on boundary
   inputs and records `exec_err` / `raised` counts.
4. **Unfold before validation.** New `unfold_to_primitives(expr, input_sort)`
   (and `ParametricSkillMacro.unfold_to_primitives`) fully expands skill
   calls, islands and open holes. `DualMemoryLearner._direct_ok` and the
   verifier's `verify_direct_witness` now validate only the pure primitive
   AST (the verifier rejects any residual skill/island/hole node).
5. `NO_PROGRAM_IN_BOUNDED_GRAMMAR` baseline cells were already labeled as
   valid negative certificates in the committed v10 code; unchanged.

### Open-world arena: honest configurations measured before launch

| Configuration | evolving solved | static solved | evolving work/solved | static work/solved |
| --- | --- | --- | --- | --- |
| v10 code (label-leaking repair) | 12 | 11 | 110.92 | 149.36 |
| v11 default (hop-1 + declared piecewise) — **launched** | **12** | 11 | **123.42** | 149.36 |
| v11 `residual_multihop=True` (hops=3 on hop-1 `NO_PROGRAM`) | 14 | 11 | 217.64 | 149.36 |

The two deep solves need hop 2 and cost 653 and 913 work units, so with
this engine `>= 13 solved` and `work/solved < 149.36` cannot both hold (13
solves would average at least ~164). The flag defaults to off (v10
protocol); the configuration was fixed before launch, not after seeing v11.
Three authored arena labels appear wrong (`_teacher` checks the
`strip().lower()` branch before the `#`-comment branch, so e.g.
`OPEN_LOG_FORENSICS #5` expects `"#only\nkeep=3"`); evaluator labels were
**not** changed.

### v11 confirmation gates

| Gate | v11 measured outcome |
| --- | --- |
| Parent CLI exit | **0 on Pass 1.** `integrity_valid=true`, `scientific_gates_passed=true`, `ready_for_freeze=true`, `replayed=true`, `errors=[]`. Worker in-process verify also integrity-valid. |
| False certificates | **0** across 100/100 matrix cells, streams and arena (arena now directly re-executed and recounted). |
| Identical-library guidance | **Cleared.** Learned 517 < fixed 545, same 3-skill library, 1 hop each. |
| Adaptive vs fixed streams | **Cleared.** 12/12 > 11/12. |
| Lifelong learning | **Cleared.** Adaptive training-inclusive 7,027 < cache 8,749 (< fixed 13,649); `lifelong_learning_demonstrated=true`. |
| Unseen World 5 (`BIT_CELLULAR_AUTOMATA`) | **Cleared.** `unseen_world_selfplay_tasks=0`, `unseen_world_training_rows=0`, `unseen_world_zero_shot_transferred_skills_count=3`; deep (teacher primitive cost 4) target solved zero-shot: transferred doctor 561 work, unguided 577, source-free 881. |
| Open-world arena | **Partially cleared.** Evolving 12 > 11 static/unpruned and > 4 LLM baseline; work/solved 123.42 < 149.36. **Requested `>= 13` not met** (see table above). |
| Arena Lyapunov depths | **Cleared.** `[1, 2, 3, 4, 5]`, max 5. `arbitrary_depth_demonstrated=false`. |
| ATP homeostasis | **Cleared.** ATP 100.0, entropy 0.9536 in [0.25, 0.98], freeze 0, drift 0, 10 Shift-4 distractors quarantined, band respected. |
| Session remaining | `session_remaining_s=53.49` — **> 50.0 (gate list) but below the > 55.0 target** stated in the v11 brief. |
| Runtime | Worker wall 6.470 s (supervised child incl. imports; internal wall 5.32 s), independent replay 0.038 s, peak RSS 236.6 MiB, cap 15 s. Slower than v10's 3.125 s on the owner's Mac; different machine. |

Payload `execution_status=COMPLETE`, `source_manifest_version=11`,
`direct_certificate_verification=true`, payload SHA-256 (embedded canonical)
`cb8c7ac9619c41354e0d1ac214150d6f94384e999547794710d34327cb15086a`.
Receipt file byte SHA-256s: `worker.json`
`d65ecbd4a00357438eafaac3afeebb42c2a0ab5d89955a329cf595b112d2dfea`,
`receipt.json` `77ced3c4c2463972b78c2d9a8970ffa0cec2abf7ee634617d687c00bb239fab6`,
`complete-receipt.json` `12458e554f06683d1ece7826a752c0f8c5ce8fa12a895458b50293bf0dd64e17`,
`verifier.json` `affa86564a9dc8d7b66f30d806d11b756c1a162f2588ee2f8d55bf35acc4ad28`.
Capability flags: 6/7 (arbitrary depth honestly false;
`all_seven_general_capabilities_demonstrated=false`). This is finite inspected
source development on seed 24001, not general intelligence.

### Tests

- `pytest tests/test_wave24_*.py -W error::RuntimeWarning`: **180 passed, 0
  warnings** (7.6 s), including new tests for piecewise synthesis (certifies
  only on agreement, never reads a label, reports ambiguity), verifier
  recounting of tampered arena cells, real fuzz, opt-in residual multi-hop,
  `unfold_to_primitives`, `_direct_ok` on open/island witnesses, and the AST
  compiler (multi-statement chain, if/else + try/except, layer-2 calling
  layer-1, rejection on expansion disagreement, nursery/graduation).
- Full unfiltered `pytest -v -W error::RuntimeWarning` was **not completed**:
  after installing the `research` extras it ran >10 min at <1% of 421 files
  (legacy RL studies; `tests/test_action_conditioned_q_resume.py` alone
  exceeds 300 s and showed 2 early failures in untouched code). Stopped.
- `tests/test_seed_wave24_cross_family_experiment.py` needs the local GGUF
  model `qwen2.5-0.5b-instruct-q4_k_m.gguf`, absent in the cloud clone.

### Playground and `evolved_toolbox.py` (dev sandbox)

`python3 scripts/run_nexus_unlimited_playground.py --epochs 3 --dev-sandbox`
exited 0 in 0.193 s: ATP 100.0, entropy 0.9536, 0 false certificates,
`max_hierarchy_layer=2`, constructs `chain`/`if`/`try`, max primitive cost 7.
New mechanics:

- `UnlimitedPythonGround` scans all 11 SAFE_MODULES (math 43, statistics 36,
  operator 13, itertools 10, re 6, collections 5, difflib 5, json 4, string 2,
  fractions 2, datetime 0 unary candidates), drops int-identity and
  behavioral duplicates, and fills the 24-op budget round-robin. Only `math`
  and `operator` yield non-identity int→int behaviors under the int wrapper.
- `compile_verified_skill_ast` builds real Python ASTs (`ast` nodes →
  `ast.unparse` → `ast.parse` → `compile` → restricted `exec`), with
  `v_i` stepping-stone locals, `if x < 0:` / `else:` phase splits and a
  `try/except (ValueError, KeyError, ZeroDivisionError, TypeError,
  OverflowError)` guard. Every function is checked against its fully unfolded
  primitive plan on check inputs, public IO, the query and integer fuzz cases.
- Three phases per epoch: explore (self-proposed novel depth-2 task, ≤3
  proposals), compound (library-level search over skill singles/pairs, unique
  query value required), phase-boundary probing (sign-flip divergence between
  the top skill and a primitive → piecewise synthesis → conditional skill).
- `skill_lineage.json` stores layer, callees, plan and pure primitive plan;
  `PersistentNexusBrain.unfold_to_primitives(name)` reconstructs it.
- Cold nursery: new skills hold no ATP; they graduate only after ≥2 verified
  uses with measured ΔW > 0 (library-search work vs a primitive-only
  counterfactual run, capped at 4,000 — so ΔW is a lower bound).

Dev-sandbox toolbox after 3 epochs (epochs 0–1 were honestly
`AMBIGUOUS_WITNESS_FOUND`; nothing graduated yet):

```python
def skill_2_chain_e63f679a(x):          # layer 1, 2 primitive steps
    if not isinstance(x, int):
        return x
    v_1 = _apply(operator.inv, x)
    v_2 = _apply(math.acos, v_1)
    return v_2

def skill_2_branch_1ce1fd2c(x):         # layer 2, calls layer 1
    if not isinstance(x, int):
        return x
    try:
        if x < 0:
            v_1 = _apply(math.acos, x)
            return v_1
        else:
            v_2 = skill_2_chain_e63f679a(x)
            return v_2
    except (ValueError, KeyError, ZeroDivisionError, TypeError, OverflowError):
        v_3 = skill_2_chain_e63f679a(x)
        return v_3
```

Honest caveats: `_apply` maps out-of-domain results back to the input, so
several stdlib "skills" are behaviorally simple (e.g. `acos` on negatives is
identity); the `except` branch is defensive and unreachable on int inputs
because every step is already exception-safe. An informational 8-epoch run
(not a gate) reached layer 6, max primitive cost 51, 4 graduated skills.
Sections 2/4/5 of the v11 brief (new `AtomicFieldProjector` /
`AtomicForceRole` classes, a local Qwen proposer in the playground,
`UniversalForceFunctor` rename) were **not implemented**; the existing
`atomic_signature` / `NoetherConservationGate` / role functors were reused.

### Current working-tree SHA-256 (v11 sources)

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_quotient_core.py` | `46336746ae130db673fcaa0b19b2e5cfd2f75b126f59cd2e5bf7ae3d745a839b` |
| `src/nexus/wave24_self_evolving_loop.py` | `137825b0ac58ef4505cb06e27a4806bc6ef76b8dfd031aaad6bc6c3990ecc334` |
| `src/nexus/wave24_open_world_arena.py` | `ff20dafc4a9d3d5d66bf87e28c0c356dd9e62698d567ad7d59d42a16d8ef8ef5` |
| `src/nexus/wave24_unlimited_playground.py` | `834e18afbac3a9f808bbf65b23f93a6209b033246e10cc1fde4a2084f75fd6c1` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `19f1d1f18f688d4b6b4eb9ebe91bf5250011041dddd8044f193b444c6f190b82` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `c7beba118061d528bb20a89491458b37a4d8703234f9a7420e7a1e5dd7120d62` |
| `scripts/run_nexus_unlimited_playground.py` | `ce7d078204eb7af5dc73a4f211421db753392583f270b374173c5ebea5523f9f` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `5ac41d3a29d068b112d4c7c3f07c46ea19e382067fa0cdd65cc9295f1871101d` |
| `tests/test_wave24_open_world_arena.py` | `11ec66fb6345990bb88feec6aa8efdd3d97cea4934eb9bda44e05bcdfa419edb` |
| `tests/test_wave24_unlimited_playground.py` | `c7416be72e284e6026e14f59c5e4b65a88d8f8785be9579e06df08dbecedc8da` |
| `tests/test_wave24_quotient_soundness.py` | `d6cd413c0a94c5e49161633c9124e7e70b7b12d0223e4a3ca8918dda1e170ea4` |
| `tests/test_wave24_lifelong.py` | `7f17a3fd95f72cb87335c4fc89064faa18e94298cbf6631847fc005c919ac3e9` |
| `artifacts/wave24_living_brain_sandbox/evolved_toolbox.py` | `725c6d3248d51f16873a8f6547c4a4bbd9cb2442bbb98167b64e015661f00b05` |
| `artifacts/wave24_living_brain_sandbox/skill_lineage.json` | `d54f428fefdd729c2d32d0c10d6def9793f243f553d6e1d1e7f545367e2eb8af` |

Other Wave24 sources are unchanged from the v10 table below.
**Stop for inspection. Do not commit or push. Do not retry v7–v11.**
Remaining before any freeze: the `>= 13` open-world target needs a cheaper
hop-2 mechanism, not a looser gate; session remaining was 53.49 s (< 55);
Commit-1 still requires a pushed freeze SHA and an explicit final allocation.

## Historical: guidance v10 — live experience transfer, hop-1 compounding

**v11 note:** v10's open-world `12 > 11` relied on label-selected piecewise
repair (see v11 findings); its other gates are unaffected.

Executed exactly once on `codex/wave24-azr-ruler-cegis` at committed
HEAD `3616059f5595127fef9680ae4601107bd078f488` plus the uncommitted
v10 sources below. Allocation `dev-24001-guidance-v10` (`carried_used_s`
3564.568, wall 15s, owner-authorized incremental `session_refresh_s`
60.0 above consumed v1–v9). Frozen contract remaining without refresh
was −1.90s (sandbox leftover 37.332s on the 3564.568/3600 ledger).
Refresh held `session_remaining_s=56.857 > 55`. v1–v9 grants stay
consumed. This is inspected SOURCE DEVELOPMENT on seed 24001, not
untouched confirmation or an AGI proof.

Focused Wave24 tests after the v10 upgrades: **167 passed, 0
RuntimeWarnings** in 3.56s (`-W error::RuntimeWarning`), including
`tests/test_wave24_unlimited_playground.py`. Full unfiltered `pytest -v`
was not run because it includes closed scientific/GPU studies with
consumed grants.

Playground daemon
`python3 scripts/run_nexus_unlimited_playground.py --epochs 3 --dev-sandbox`
finished in **0.021s** (`< 0.5s`), `atp_total_sum=100.0`,
`normalized_atp_entropy=0.78505` in `[0.25, 0.98]`, all three epochs
solved. White-box brain at
`artifacts/wave24_living_brain_sandbox/`:
`evolved_toolbox.py` with three compiled `skill_*` functions (real
stdlib `math.acos` apply-trees plus one identity),
`universal_meta_recipes.json` (atomic forces
`CLEANER_IDEMPOTENT` / `FILTER_CONTRACTIVE` / `FLIPPER_INVOLUTION` /
`STEPPER_ADVANCE` / `GUARD_STABILIZER` plus Noether laws, 3 recipes),
`symptom_doctor_state.json` (3 live doctor rows, ATP 100).

v10 worker wall **3.125s**, parent first-pass verify **0.018s**
(integrity false on the `NO_PROGRAM` label), independent direct
replay **0.021s**. Worker + independent verify **3.146s** (slightly
over the 3.0s confirmation target; not a verifier gate). Worker
payload `execution_status=COMPLETE`, `source_manifest_version=11`,
`direct_certificate_verification=true`, `false_certificate_count=0`,
100/100 matrix cells. Payload SHA-256
`be27b5894139627fb0af07fedcbbbf25589a791028ee4545e5c56a4cf64d0e3b`.
Retained at `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v10`.
Worker process exited `2` because its in-process `verify_payload(replay=False)`
used the old stream-certificate label. No
`docs/evidence/wave24_azr_dev_guidance_v10.json` (dev grant, not a freeze).

### v10 confirmation gates

| Gate | v10 measured outcome |
| --- | --- |
| Identical-library guidance | **Cleared.** Learned Noether 517 vs fixed canonical 545 on the same 3-skill library, 1 hop each. |
| Adaptive vs fixed streams | **Cleared.** Adaptive **12/12 > 11/12** fixed. |
| Lifelong learning | **Cleared.** `lifelong_learning_demonstrated=true`: adaptive training-inclusive work **7123 < 8723** cache (and < 13606 fixed). First acquisition 4995 vs reuse 258. Promoted 4 intra-domain skills. Live `learn_live_trajectory` replaced the ~215k ExactEnumerator sweep. |
| Arena Lyapunov depths | **Cleared.** Depths `[1, 2, 3, 4, 5]`, `dynamic_lyapunov_max_hops_reached=5`. Stream depths `[2,1,1,3,1,1,2,1,1,2,1,1]` (max 3). Safety cap remains 16. `arbitrary_depth_demonstrated` stays false. |
| ATP homeostasis | **Cleared.** `atp_total_sum=100.0`, `normalized_atp_entropy=0.9536466051859067` in `[0.25, 0.98]`, freeze 0, drift 0, 10 Shift-4 distractors quarantined, `band_respected=true`. |
| False certificates | **Cleared.** Matrix, streams, and arena all `false_certificate_count=0`. |
| Direct certificate verification | **Cleared on independent replay.** Parent first pass raised `unverified stream certificate` because STR_PARSE event 1 fixed/cache `NO_PROGRAM` cells stored `certificate_valid=false`. Independent verify unfolds skill-reuse / island witnesses, treats completed `NO_PROGRAM` as a certified negative, and passes in **0.021s**. |
| Open-world dominance | **Cleared.** Evolving **12 > 11** static/unpruned and **12 > 4** standalone. Work/solved **110.92 < 149.36** static/unpruned. Hop-1 + promoted spines first; piecewise only on miss. |
| Cross-domain transfer | **Cleared.** `unseen_world_selfplay_tasks=0`, `unseen_world_training_rows=0`, `unseen_world_zero_shot_transferred_skills_count=3`. |
| Parent session remaining | **Cleared.** `session_remaining_s=56.857 > 55`. |
| Total runtime | Worker 3.125s + independent verify 0.021s = **3.146s**. Slightly over the requested `< 3.0s` confirmation target. |
| Parent CLI exit | **First pass exited 1.** Independent verify of the saved COMPLETE payload is `ready_for_freeze=true`. Do not relaunch v10. |

### 7-capability + Open-World status (v10 worker arithmetic, independent verify)

| Capability | Flag / measurement |
| --- | --- |
| Arbitrary depth | false (finite hops/cap9; ladder reached depth 5 in the arena) |
| Lifelong learning | **true** (`12>11` and adaptive work 7123 < cache 8723) |
| Cross-domain transfer | true (3 zero-shot transferred skills; frozen fifth-world) |
| Symptom-doctor meta-learning | true (identical-library learned 517 < fixed 545) |
| Closed-loop self-audit | **true** (3 poisons quarantined; post-quarantine work 304 < pre 555; adjustments logged on negative source-net-utility) |
| Tool invention | true (promoted helpers on the open-toolbox stream) |
| Open Python synthesis | true (open-toolbox cells unique + certificate-valid) |
| Open-World Arena | evolving 12/24 vs 11/11/4 baselines; work/solved 110.92 < 149.36 |
| Metabolic homeostasis | ATP 100, entropy 0.9536, 10 poisons evicted |
| Persistent playground | 3 epochs, ATP 100, 3 compiled `skill_*` functions and 3 meta-recipes persist on disk |

100 matrix cells completed, zero false certificates. Demonstrated
capability count **6/7** (arbitrary depth remains an honest false).
`all_seven_general_capabilities_demonstrated` stays false because
arbitrary depth cannot be claimed. This is still finite inspected
source development, not general intelligence.

### Current working-tree SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_quotient_core.py` | `b6a92ce46a40a83a3d275031134b7c9de619f7e809ea28ce76a0d52e404da2a8` |
| `src/nexus/wave24_self_evolving_loop.py` | `9318fb056b9f8b0b267ba266682a291b2e5df0f1d1db046af21c063c4c497705` |
| `src/nexus/wave24_resource_host.py` | `c9d6afedcce5ff8fe41c4ef9ca377a1bd513eb1a0af9494dd05f77734ef4e74b` |
| `src/nexus/wave24_helper_spawn.py` | `644c05babfb9ca759874359e3fde0490e54c384b4c3ac557095930f915e69ad2` |
| `src/nexus/wave24_pytest_guard.py` | `cf9f931914125839f8f7906d1ed3a3c3c1a8ac867aceef7257e845078c0e8224` |
| `src/nexus/wave24_lifelong_streams.py` | `b6f850771184cc9a87fc11461dace3b21d493fdaab5631f86a1882880daa7927` |
| `src/nexus/wave24_auto_laws.py` | `46ad4aba7e59c82d2d4c1152b284be0a6a2459a7e42b741ef1390f713d23ccc3` |
| `src/nexus/wave24_open_world_arena.py` | `9501e4f1e723e67e8c1eab9a067d79c9ce1e6df1c609c7f4cf1c6d292a4a9787` |
| `src/nexus/wave24_unlimited_playground.py` | `c1aeeafe6c57be21c1672c240d9a56e33a60213349ace3b0187f333c18809138` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `a54f46126e37d0f806175dc9300566a8fc6df07517751724ff31c42e0ff353de` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `2b7c2f3f210c9e7f42513cec820eb6d18b10905755ed8b309da8ae1ff97025e3` |
| `scripts/run_nexus_unlimited_playground.py` | `afd08e7e73a5212fa44a57e36ec5e0ad7cd096478e1e154c98c6996f2f97a1fe` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `91c9fd55bd01e9737d1946d7b9b8b6c6dbbd201050511011606ee0914c3d1e24` |
| `configs/wave24_azr_ruler_cegis.json` | `580839f82c31e7b8105a4786cb92ddcbc487aa2291921953c7568e5c46cc4814` |
| `tests/test_wave24_unlimited_playground.py` | `68f0f7bd00f48a2b9f3258d37b584f7b1ba5780d16f92549e7326ff793ec3b2a` |
| `tests/test_wave24_lifelong.py` | `e130e20263dd19cf23e105d10915b5312e48b189b8ce8f55e86fae872df380ab` |
| `tests/test_wave24_lifelong_streams.py` | `07ccb4223bfe152eec472c7628f28998f62aa5a56907c1ac363be51149d83e86` |
| `tests/test_wave24_open_world_arena.py` | `17f214d690575272f53503c88ec148094053502f0eae2d72afcf98d512d86a06` |
| `tests/test_wave24_quotient_soundness.py` | `f460c78ebb3ff3120e2c629e22983c070b6f8bcf8c6d088213643c5de0c46690` |
| `tests/test_wave24_resource_host_and_runner.py` | `196e31805d2d4dbbd9dee63041fa2bae81dea0531d050b421781d630aab806da` |

v10 attempt: `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v10`.
**Stop for inspection. Do not commit or push. Do not retry v7, v8, v9,
or v10.** Remaining items if authorized later: parent first-pass exit
was 1 (now independently green); worker wall 3.125s is 0.125s over the
3.0s confirmation target; Commit-1 freeze still requires a pushed freeze
SHA and an explicit final allocation.

## Historical: guidance v9 — persistent playground, 12/12, direct certificates

Executed exactly once on `codex/wave24-azr-ruler-cegis` at committed HEAD
`5074f3212ff88aaabcc5ad7b3efef1debca334eb` plus the uncommitted v9
sources below. Allocation `dev-24001-guidance-v9` (`carried_used_s`
3564.568, wall 15s, owner-authorized `session_refresh_s` 60.0). v1–v8
grants stay consumed. This is inspected SOURCE DEVELOPMENT on seed
24001, not untouched confirmation or an AGI proof.

Focused Wave24 tests after the v9 upgrades: **167 passed, 0
RuntimeWarnings** in 4.24s (`-W error::RuntimeWarning`), including
`tests/test_wave24_unlimited_playground.py`. Full unfiltered `pytest -v`
was not run because it includes closed scientific/GPU studies with
consumed grants.

Playground daemon
`python3 scripts/run_nexus_unlimited_playground.py --epochs 3 --dev-sandbox`
finished in **0.020s** (`< 0.5s`), `atp_total_sum=100.0`,
`normalized_atp_entropy=0.9536` in `[0.25, 0.98]`, all three epochs
solved.

v9 worker wall **2.701s**, parent verify attempt **0.013s**, independent
direct replay **0.025s**. Worker + independent verify **2.726s < 3.0s**.
Worker payload `execution_status=COMPLETE`, `source_manifest_version=11`,
`direct_certificate_verification=true`, `false_certificate_count=0`,
100/100 matrix cells. Payload SHA-256
`1a5d7e87e8e3b52c7274b7fc2e0c37c973e73247cf29229e4e6da26ee7625e05`.
Retained at `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v9`.
No `docs/evidence/wave24_azr_dev_guidance_v9.json` (dev grant, not a
freeze).

### v9 confirmation gates

| Gate | v9 measured outcome |
| --- | --- |
| Identical-library guidance | **Cleared.** Learned Noether 517 vs fixed canonical 545 on the same 3-skill library, 1 hop each. |
| Adaptive vs fixed streams | **Cleared.** Adaptive **12/12 > 11/12** fixed. Residual 3-hop canonical rescue after hop-1 spine recovered the v8 STR_PARSE miss. |
| Arena Lyapunov depths | **Cleared.** Depths `[1, 2, 3, 4, 5]`, `dynamic_lyapunov_max_hops_reached=5`. Stream depths `[2,1,1,3,1,1,2,1,1,2,1,1]` (max 3). Safety cap remains 16. `arbitrary_depth_demonstrated` stays false. |
| ATP homeostasis | **Cleared.** `atp_total_sum=100.0`, `normalized_atp_entropy=0.9536466051859067` in `[0.25, 0.98]`, freeze 0, drift 0, 10 Shift-4 distractors quarantined, `band_respected=true`. |
| False certificates | **Cleared.** Matrix, streams, and arena all `false_certificate_count=0`. |
| Direct certificate verification | **Cleared after the leftover-wall accounting fix.** Parent first pass used `wall_limit=0.001s` because sandbox `session_remaining_s` was `-1.90` (v6–v8 already sat on the 3564.568/3600 ledger). Independent verify executes saved `g_1`/`g_2` on `D_pub ∪ {x_q}` plus one canary; **0.025s**, `integrity_valid=true`. |
| Total runtime | Worker 2.701s + independent verify 0.025s = **2.726s < 3.0s**. |

Open-world solved-count dominance still holds (evolving 13 > static 11,
unpruned 11, standalone 4). Work/solved remains a recorded comparison,
not a v9 hard fail: evolving 331.6 vs static/unpruned 149.4.

### 7-capability + Open-World status (v9 worker arithmetic)

| Capability | Flag / measurement |
| --- | --- |
| Arbitrary depth | false (finite hops/cap9; ladder reached depth 5 in the arena) |
| Lifelong learning | false (`12>11` correctness cleared, but training-inclusive adaptive work 240500 ≮ fixed 40130 / cache 25181) |
| Cross-domain transfer | true (3 zero-shot transferred skills; frozen fifth-world) |
| Symptom-doctor meta-learning | true (identical-library learned 517 < fixed 545) |
| Closed-loop self-audit | false on the derived flag this run (3 poisons still quarantined; post-quarantine work did not drop) |
| Tool invention | true (promoted helpers on the open-toolbox stream) |
| Open Python synthesis | true (open-toolbox cells unique + certificate-valid) |
| Open-World Arena | evolving 13/24 vs 11/11/4 baselines; work/solved does not dominate |
| Metabolic homeostasis | ATP 100, entropy 0.9536, 10 poisons evicted |
| Persistent playground | 3 epochs, ATP 100, skills persist on disk under `--brain-dir` |

100 matrix cells completed, zero false certificates. Adaptive first
acquisition 23532 vs repeat 4283. Cache work 25181 is cheap proof reuse,
not a search.

### Current working-tree SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_quotient_core.py` | `b6a92ce46a40a83a3d275031134b7c9de619f7e809ea28ce76a0d52e404da2a8` |
| `src/nexus/wave24_self_evolving_loop.py` | `37fcbfbcc7c671699cf989b7ea5e711dc2b58d43ccc34e556f854abb1e995837` |
| `src/nexus/wave24_resource_host.py` | `c9d6afedcce5ff8fe41c4ef9ca377a1bd513eb1a0af9494dd05f77734ef4e74b` |
| `src/nexus/wave24_helper_spawn.py` | `644c05babfb9ca759874359e3fde0490e54c384b4c3ac557095930f915e69ad2` |
| `src/nexus/wave24_pytest_guard.py` | `cf9f931914125839f8f7906d1ed3a3c3c1a8ac867aceef7257e845078c0e8224` |
| `src/nexus/wave24_lifelong_streams.py` | `b6f850771184cc9a87fc11461dace3b21d493fdaab5631f86a1882880daa7927` |
| `src/nexus/wave24_auto_laws.py` | `46ad4aba7e59c82d2d4c1152b284be0a6a2459a7e42b741ef1390f713d23ccc3` |
| `src/nexus/wave24_open_world_arena.py` | `821d64393a44b396efbb797c4d39aadd9342b2856a6fa103bc877e69caf75311` |
| `src/nexus/wave24_unlimited_playground.py` | `e97d2660643ba8ba938f25bf67ee4ce787bb3aa60b193753b99ea49c747abbfe` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `f1d5ff4d3a1353b45580baa12fd1cabe3950119da3a555ae040b64b703d75d54` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `52248194c746aaf69faef9613ac1f2a99d648678d08c496fcf25af8c6d4be0aa` |
| `scripts/run_nexus_unlimited_playground.py` | `afd08e7e73a5212fa44a57e36ec5e0ad7cd096478e1e154c98c6996f2f97a1fe` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `0fa7bec80408fc52ccaefec720bed3ed5ae18e2a11ed55666f96e3a80a31464c` |
| `configs/wave24_azr_ruler_cegis.json` | `580839f82c31e7b8105a4786cb92ddcbc487aa2291921953c7568e5c46cc4814` |
| `tests/test_wave24_unlimited_playground.py` | `e9c9d052db14282d010294504f50cce1318a328fba0e12aee53725d91903dca6` |
| `tests/test_wave24_lifelong.py` | `e130e20263dd19cf23e105d10915b5312e48b189b8ce8f55e86fae872df380ab` |
| `tests/test_wave24_lifelong_streams.py` | `07ccb4223bfe152eec472c7628f28998f62aa5a56907c1ac363be51149d83e86` |
| `tests/test_wave24_open_world_arena.py` | `17f214d690575272f53503c88ec148094053502f0eae2d72afcf98d512d86a06` |
| `tests/test_wave24_quotient_soundness.py` | `f460c78ebb3ff3120e2c629e22983c070b6f8bcf8c6d088213643c5de0c46690` |
| `tests/test_wave24_resource_host_and_runner.py` | `196e31805d2d4dbbd9dee63041fa2bae81dea0531d050b421781d630aab806da` |

v9 attempt: `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v9`.
**Stop for inspection. Do not commit or push. Do not retry v7, v8, or
v9.** Remaining scientific holes, if authorized later: evolving
open-world work/solved is still 331.6 vs static 149.4;
`lifelong_learning_demonstrated` stays false because adaptive
training-inclusive work is not cheaper than cache; Commit-1 freeze
still requires a pushed freeze SHA and an explicit final allocation.

## Historical: guidance v8 Commit-1 + Open-World Arena — worker complete, replay exhausted

Executed exactly once on `codex/wave24-azr-ruler-cegis`, unchanged committed
HEAD `073d9297e6b9b350368f31ee7d18418ef9071634`. Allocation
`dev-24001-guidance-v8` (`carried_used_s` 3564.568, wall 10s). Worker wall
8.510s plus verifier 1.532s; session used **3599.186s**, remaining
**0.814s**. v1–v7 grants stay consumed. This is inspected SOURCE DEVELOPMENT
on seed 24001, not untouched confirmation or an AGI proof. Focused Wave24
tests after the architectural patch: **165 passed, 0 RuntimeWarnings** in
9.81s (`-W error::RuntimeWarning`). Full unfiltered `pytest -v` was not run
because it includes closed scientific/GPU studies with consumed grants.

Worker payload `execution_status=COMPLETE`, `false_certificate_count=0`,
100/100 matrix cells. Parent verifier raised `WorkExhausted` while
replaying the streams+arena under the leftover wall, so
`integrity_valid=false` and no `docs/evidence/wave24_azr_dev_guidance_v8.json`
was written. The worker JSON is retained at
`runs/experimental/wave24-azr/attempts/dev-24001-guidance-v8`.

### Four Commit-1 blockers plus Open-World / metabolic gates

| Gate | v8 measured outcome |
| --- | --- |
| Identical-library cost 6432 vs 4998 | **Cleared on the worker.** Learned Noether 517 vs fixed canonical 545 on the same 3-skill library, 1 hop each, 0 false certificates. |
| Adaptive 7/12 vs 9/12 | **Still blocked.** Adaptive 11/12 vs fixed 11/12. STR_PARSE event 0: adaptive `lyapunov_converged` after 3 hops (`NO_PROGRAM`); fixed solved in 3 hops. STR_PARSE event 1: adaptive solved in 3 hops; fixed hit `hop_budget` at 3. They trade one task each. Verifier requires adaptive **strictly greater** than fixed and adaptive ≥ 10. |
| Hardcoded `max_hops=3` | **Cleared as a mechanism.** Stream Lyapunov depths `[2,1,1,3,3,1,2,1,1,3,1,1]` (max 3). Open-World ladder depths `[1,2,3,4,5]`, `dynamic_lyapunov_max_hops_reached=5`. Safety cap remains 16. `arbitrary_depth_demonstrated` stays false. |
| Pytest fork/thread warning | **Cleared.** Spawn helper is torch-free (`wave24_helper_spawn.py`). Suite ran under `-W error::RuntimeWarning` with 0 warnings. |
| Open-World solved-count dominance | **Worker-only: evolving 13 > static 11, unpruned 11, standalone 4.** 24 tasks, 42 guarded stdlib primitives, 0 false certificates. |
| Open-World work/solved dominance | **Not cleared.** Evolving 331.6 work/solved vs static/unpruned 149.4 and standalone 8.0. More tasks solved, but not cheaper per solve. |
| Metabolic stability | **Cleared on the worker.** `atp_total_sum=100.0`, `normalized_atp_entropy=0.9536` in `[0.25,0.98]`, freeze 0, drift 0, 10 Shift-4 distractors quarantined, `band_respected=true`. |

### 7-capability + Open-World status (worker arithmetic)

| Capability | Flag / measurement |
| --- | --- |
| Arbitrary depth | false (finite hops/cap9; ladder nevertheless reached depth 5 in the arena) |
| Lifelong learning | false (11 ≰ 11 on the strict `>` rule; 4 intra-domain skills retained) |
| Cross-domain transfer | true (3 zero-shot transferred skills; frozen fifth-world) |
| Symptom-doctor meta-learning | true (identical-library learned 517 < fixed 545) |
| Closed-loop self-audit | true (3 injected poisons quarantined; identity answer unchanged) |
| Tool invention | false (0 promoted helpers; 3/3 open-toolbox cells `NO_PROGRAM`) |
| Open Python synthesis | false (same 3/3 open-toolbox misses) |
| Open-World Arena | worker-complete: 13/24 evolving vs 11/11/4 baselines; work/solved does not dominate |
| Metabolic homeostasis | worker-complete: ATP 100, entropy 0.9536, 10 poisons evicted |

Doctor/meta-learning, closed-loop quarantine and cross-domain transfer are true
on this finite source grid. Lifelong learning is false (tie, not a strict win).
100 matrix cells completed, zero false certificates. Adaptive first-acquisition
work 32164 vs repeat 4443; training-inclusive 259909 vs fixed 40130 and cache
25181. Cache is cheap proof reuse, not a search.

### Metabolic telemetry (worker)

`atp_total_sum=100.0`, `normalized_atp_entropy=0.9536466051859067`,
`metabolic_freeze_events=0`, `metabolic_drift_events=0`,
`evicted_poisoned_shortcuts=10`, `injected_distractors_quarantined=true`,
`band_respected=true`.

### Current working-tree SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_quotient_core.py` | `b6a92ce46a40a83a3d275031134b7c9de619f7e809ea28ce76a0d52e404da2a8` |
| `src/nexus/wave24_self_evolving_loop.py` | `5624d9a4d68911b637ddd09f3508df8013aa8b7d0c540923c6356681f489b002` |
| `src/nexus/wave24_resource_host.py` | `c73ffc840e27988eaacbf004e1d9a5aa29cf12708b4a05a287c1113a32861905` |
| `src/nexus/wave24_helper_spawn.py` | `644c05babfb9ca759874359e3fde0490e54c384b4c3ac557095930f915e69ad2` |
| `src/nexus/wave24_pytest_guard.py` | `cf9f931914125839f8f7906d1ed3a3c3c1a8ac867aceef7257e845078c0e8224` |
| `src/nexus/wave24_lifelong_streams.py` | `485415e1c74dc5ee77dd473fefc5fcf5534124d849ec254b337821cab82c7500` |
| `src/nexus/wave24_auto_laws.py` | `46ad4aba7e59c82d2d4c1152b284be0a6a2459a7e42b741ef1390f713d23ccc3` |
| `src/nexus/wave24_open_world_arena.py` | `821d64393a44b396efbb797c4d39aadd9342b2856a6fa103bc877e69caf75311` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `0235a49356d745ed25b8cf53f37f58b52cb76ed0d8f45998377ba6d50846b320` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `71a385c2808badd0e8bf566c5d109278eb8f9a9e9094fcf362bb57c7d2a7a38c` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `ab95cdb77ae6eb59c42763750248dbb8a8b46fb05a2a0ea701f0a87192297f47` |
| `tests/test_wave24_lifelong.py` | `e130e20263dd19cf23e105d10915b5312e48b189b8ce8f55e86fae872df380ab` |
| `tests/test_wave24_lifelong_streams.py` | `07ccb4223bfe152eec472c7628f28998f62aa5a56907c1ac363be51149d83e86` |
| `tests/test_wave24_open_world_arena.py` | `17f214d690575272f53503c88ec148094053502f0eae2d72afcf98d512d86a06` |
| `tests/test_wave24_quotient_soundness.py` | `f460c78ebb3ff3120e2c629e22983c070b6f8bcf8c6d088213643c5de0c46690` |
| `tests/test_wave24_resource_host_and_runner.py` | `196e31805d2d4dbbd9dee63041fa2bae81dea0531d050b421781d630aab806da` |

v8 attempt: `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v8`.
No evidence JSON because replay exhausted the wall. Closed and logged.
v9 later recovered the STR_PARSE miss (`12>11`) and replaced full replay
with direct certificate verification. Work/solved dominance was not a v9
hard gate and remains uncleared.

## Historical: guidance v7 Commit-1 blocker retry — complete, mixed

Executed exactly once on `codex/wave24-azr-ruler-cegis`, unchanged committed
HEAD `073d9297e6b9b350368f31ee7d18418ef9071634`. Allocation
`dev-24001-guidance-v7` (`carried_used_s` 3564.568). Worker wall 6.121s plus
verifier 1.243s; session remaining **10.857s**. v1–v6 grants stay consumed.
This is inspected SOURCE DEVELOPMENT on seed 24001, not untouched confirmation
or an AGI proof. Focused Wave24 tests: **156 passed, 0 RuntimeWarnings** in 5.68s.

### Four Commit-1 blockers

| Blocker | v7 measured outcome |
| --- | --- |
| Identical-library cost 6432 vs 4998 | **Cleared.** Learned Noether 517 vs fixed canonical 545 on the same 3-skill library, 1 hop each. |
| Adaptive 7/12 vs 9/12 | **Still blocked.** Adaptive 11/12 vs fixed 12/12. The only miss is STR_PARSE event 0: adaptive `lyapunov_converged` after 3 hops with `NO_PROGRAM_IN_BOUNDED_GRAMMAR`; fixed solved in 3 hops. Hop-2+ Noether/Lyapunov left a different workspace than the canonical path. Verifier requires adaptive **strictly greater** than fixed and adaptive ≥ 10. |
| Hardcoded `max_hops=3` | **Cleared as a mechanism.** Lyapunov depths `[2, 1, 1, 3, 3, 1, 2, 1, 1, 3, 1, 1]`, max 3. Safety cap remains 16. `arbitrary_depth_demonstrated` stays false. |
| Pytest fork/thread warning | **Cleared.** Spawn helper is torch-free (`wave24_helper_spawn.py`); CPU rlimit 2s after import. Streams `COMPLETE`. Suite ran under `-W error::RuntimeWarning`. |

### Capability flags on this run

Doctor/meta-learning, closed-loop quarantine and cross-domain transfer are true
on this finite source grid. Lifelong learning is false (11 ≰ 12). Tool
invention and open-Python flags are false: zero promoted helpers; all three
open-toolbox cells hit `hop_budget` without a program. 100 matrix cells
completed, zero false certificates. Spawn isolation no longer timed out (v6
failure mode).

### Current working-tree SHA-256

| Path | SHA-256 |
| --- | --- |
| `src/nexus/wave24_quotient_core.py` | `b6a92ce46a40a83a3d275031134b7c9de619f7e809ea28ce76a0d52e404da2a8` |
| `src/nexus/wave24_self_evolving_loop.py` | `05fa1af622a1763e37716ad56c0fefd955d05c8b77ffe31447b4bb33631032a2` |
| `src/nexus/wave24_resource_host.py` | `c73ffc840e27988eaacbf004e1d9a5aa29cf12708b4a05a287c1113a32861905` |
| `src/nexus/wave24_helper_spawn.py` | `644c05babfb9ca759874359e3fde0490e54c384b4c3ac557095930f915e69ad2` |
| `src/nexus/wave24_pytest_guard.py` | `cf9f931914125839f8f7906d1ed3a3c3c1a8ac867aceef7257e845078c0e8224` |
| `src/nexus/wave24_lifelong_streams.py` | `485415e1c74dc5ee77dd473fefc5fcf5534124d849ec254b337821cab82c7500` |
| `src/nexus/wave24_auto_laws.py` | `46ad4aba7e59c82d2d4c1152b284be0a6a2459a7e42b741ef1390f713d23ccc3` |
| `scripts/run_wave24_azr_ruler_cegis.py` | `d2c8ccae5d6335e32c86e4c493a34384b78e6ef181f0f4bd103dd52d4abfee3d` |
| `scripts/verify_wave24_azr_ruler_cegis.py` | `71a385c2808badd0e8bf566c5d109278eb8f9a9e9094fcf362bb57c7d2a7a38c` |
| `configs/wave24_azr_dev_guidance_allocation.json` | `960873bd0c06c5b950cd6309be76c4f18e611d7c8eb3abf27c61b886358d8c5e` |
| `tests/test_wave24_lifelong.py` | `e130e20263dd19cf23e105d10915b5312e48b189b8ce8f55e86fae872df380ab` |
| `tests/test_wave24_lifelong_streams.py` | `07ccb4223bfe152eec472c7628f28998f62aa5a56907c1ac363be51149d83e86` |
| `tests/test_wave24_quotient_soundness.py` | `f460c78ebb3ff3120e2c629e22983c070b6f8bcf8c6d088213643c5de0c46690` |
| `tests/test_wave24_resource_host_and_runner.py` | `196e31805d2d4dbbd9dee63041fa2bae81dea0531d050b421781d630aab806da` |

v7 attempt: `runs/experimental/wave24-azr/attempts/dev-24001-guidance-v7`.
No `docs/evidence/wave24_azr_dev_guidance_v7.json` was written because
scientific gates failed. **Stop for inspection. Do not commit or push.
Do not launch v8 without a new allocation.** Next scientific patch, if
authorized: keep hop-1 spine identical to fixed, and stop Lyapunov from
converging before a canonical hop-3 STR_PARSE witness that fixed search finds.

## Historical: seven-mechanism development revision5 — complete, valid, mixed/negative

Executed exactly once on `codex/wave24-azr-ruler-cegis`, unchanged committed
HEAD `073d9297e6b9b350368f31ee7d18418ef9071634`. Config v4 explicitly changes
B's primitive cap6 to9; B0=3, three hops, three portfolio slots remain bounded.
A remains the same primitive-B0 grammar and80/20 scheduler. This is inspected
SOURCE DEVELOPMENT on seed24001, not untouched confirmation or an AGI proof.
No outcome was used to change the algorithms or thresholds after scoring.

### What is implemented versus what passed

| Requested capability | Working implementation | Measured development outcome |
| --- | --- | --- |
| Arbitrary depth | Exact unfolded scratchpad islands, three hops, cap9; a deterministic unit solves primitive cost7 | Bounded multi-hop solving observed; **arbitrary-depth flag false**. The finite grammar cannot establish unbounded depth or every depth12 task. |
| Lifelong learning | Source-only online ridge heads, typed shortcut retention, E1 history, anchored durable save/restore including protected tasks and archive/audit state | **Failed** strong learning gate: adaptive7/12 correct versus9/12 fixed/cache; training-inclusive933872 work versus504809 fixed and306510 cache. |
| Cross-domain transfer | Learned source job recipes instantiated on fifth-world anonymous operators without task training | One frozen-target task correct: transferred doctor6432 work versus26127 source-free same-hop. Three transferred skills; **limited transfer check passed**. |
| Symptom-doctor meta-learning | Fixed ten-feature, ridge1 dual heads fitted from actual source counterfactual errors/disagreements | **Failed** benefit gate: same transferred library with canonical ordering costs4998, less than doctor6432. Updating weights is not evidence of a better learning procedure. |
| Closed-loop self-audit | Measured paired shortcut utility, quarantine, source-stall portfolio tuning | All3 deliberately injected bad shortcuts quarantined; identity answer unchanged;11658→1596 work;3 actual exploration adjustments. **Controlled mechanism check passed**, not general autonomous improvement. |
| Tool invention | Typed program generalized into real generated Python, vetted AST compiler, fork-isolated execution, exact expansion checks and source acceptance before registration | One actual helper promoted, composing five +1 calls and charged full incremental primitive cost5. **Composite-helper check passed**; no semantics beyond supplied operators were invented. |
| Open Python synthesis | Trusted pure-callable adapter connected to search, verification, source updates, recipes and audit | Raw +1/negation/doubling toolbox outside the five worlds:3/3 correct certified decisions. **Supported-subset check passed**, not safe execution of arbitrary hostile Python or arbitrary classes. |

These JSON flags are finite mechanism-specific checks. Four true flags do not
establish four general-intelligence capabilities. In particular, no experiment
can make a fixed three-hop engine arbitrarily deep by renaming its success flag.
The verifier explicitly rejects such a claim. The historical all-source workspace
compilation gate also remains false: INT_SEQ's earlier selected source workspace
has no additional deep source signature. It was not removed to make readiness green.

### Actual task stream and controls

The original matrix completed10 procedural contexts ×5 methods ×2 passes =100
cells, zero false certificates, zero unresolved cells. All fixed-B0 Tier1
completed certificates agree exactly with the independent exhaustive reference.
Tier1 summed uniqueness work across both passes is2034 exhaustive,1118 quotient,
1098 quotient+laws and1394 source-speculative fixed-bound. Certificate B finds
teacher-covered deep witnesses on all five Tier2 contexts (both passes); one
is a declared ambiguity, so this is not10 unique predictions.

The additional source streams completed36 paired source cells (four worlds,
three events, three methods),3 frozen fifth-world cells, and3 raw-toolbox source
cells. The third event per source world is an exact repeat, not independent
replication. There are15 permitted source feedback events, zero fifth-world
self-play tasks/rows/updates, and no target promotion. Target state fingerprints
before/after solving are identical. The critic is frozen before target scoring.

| Source world | Adaptive correct | Fixed/cache correct | Active retained skills | First adaptive decision work | Repeat adaptive decision work |
| --- | --- | --- | --- | --- | --- |
| INT_SEQ |1/3|3/3|0|107171|109091|
| STR_PARSE |1/3|0/3|1|49311|15636|
| DICT_RECORD |3/3|3/3|1|29750|2802|
| STATE_TRANSITION |2/3|3/3|1|123857|2398|

Total adaptive decision work567086 plus366786 learning/retention work gives
933872. Aggregate first310089 versus repeat129927 work is insufficient evidence:
the INT_SEQ repeat still fails, the original STR_PARSE failures recover only on
the repeat, and total learning costs exceed both baselines. Ordinary caching is
allowed cheap proof reuse on an identical task and unchanged grammar; its repeat
costs are43/7/31/19 units. It was not made to search unnecessarily. No statistical
interval is claimed from these small, correlated inspected curricula.

The raw toolbox's initial/new-composition/repeat decision work is99783/3368/3186,
all correct; update work37762/45668/34396 is saved separately. The accepted helper
is executable `op_0(op_0(op_0(op_0(op_0(z)))))`. Its source and primitive expansion
are archived, not a name-only invention. It adds a reusable button, not a new
unprovided operation. Unsupported types/side effects fail closed; the child
audit hook is not a hostile-code or C-extension security boundary.

Three recorded source-stall adjustments change exploration preference
.20→.25→.30→.35, with a real portfolio change at>=.30. This preference is distinct
from A's fixed80/20 work scheduler. Quarantine removes active search overhead;
archive storage and audit history still cost memory.

### Exactness, costs and reproducibility

The parent verifier reconstructed the procedural bank, source labels and frozen
libraries, replayed exact unquotiented hop proofs, then independently replayed
the complete source/frozen-target streams with the same CPU numeric backend.
Logical choices, costs, updates and checkpoint hashes match exactly. Only child
wall time and sampled RSS are exempted from byte-exact replay. Invalid/missing
grids, leaked target updates, fabricated flags and misaggregated costs fail.
Negative benefit gates remain distinct from execution integrity, which passed.

Final post-accounting regression: **164 passed,1 warning in5.04s**, JUnit
`/tmp/nexus-wave24-lifelong-final-verified.xml`. The warning is Python3.13's
fork-after-threads warning during saved-helper replay. The current backend is
restricted to vetted pure primitive compositions and has a child watchdog;
it is not claimed to be a portable hostile-code sandbox. The RSS-watchdog unit
fixture was extended to recognize the fifth consumed receipt after an initial
post-accounting run exposed its stale four-receipt mock. No learner change or
second experimental launch followed. Independent saved-data arithmetic and
ten historical/runtime/evidence byte-hash checks also pass; `git diff --check`
has no errors. Python3.13.5 and Torch2.14.1 are recorded in the payload.

Pre-launch regression: **163 passed in3.33s**, JUnit
`/tmp/nexus-wave24-lifelong-prefreeze-verified.xml`. An earlier integration run
had162 passes/1 failure because a historical retry test implicitly selected the
new default allocation; it now explicitly requests the consumed v4 grant.
An initial role-transfer unit failed on mixed-sign magnitude probes; the unit's
positive-transfer fixture now declares nonnegative probes and documents the
probe-dependence. Benchmark probes were not changed. All earlier failures are
recorded; no historical result was rewritten. Full unfiltered `pytest -v` was
not run because it includes closed scientific/GPU studies with consumed grants.
Focused coverage includes all seven new Wave24/AZR test modules, deceptive operators, selected
historical boundary/checkpoint/AST checks and Seed API regressions.

Allocation `configs/wave24_azr_dev_lifelong_allocation.json`: one CPU-only20s
combined launch/replay,20s worker CPU,1024MiB sampled RSS,zero interactions.
Worker wall2.5500942500075325s; independent replay1.6684677500161342s;
**debit4.218562000023667s**. Internal worker CPU1.8936200000000003s;
sampled peak worker RSS233.578125MiB. Carried used3570.0953012089894→
**3574.313863209013s**, remaining**25.686136790986893s**. No grant reset/retry.

Actual host counters:2175 CPU scoring calls,16 CPU ridge updates,58.459171152208ms
timed CPU tensor work. GPU scoring/updates, runtime/LLM calls, historical neural
inference/training, and real environment interactions are all ZERO. GPU timing
table is cached historical six-feature calibration, explicitly not revalidated
for this ten-feature path. CPU routing was not overridden to claim GPU use.

Logical setup1230334 includes cached1228380 plus1954 actual new setup units;
training613402 includes stream updates, source stream total1757653 including
matched controls and exact verification. These are logical work, not CPU seconds.
Main-matrix full-cost stage5 ledger1880682 versus4068 exhaustive has no observed
break-even; it conservatively includes all current setup/training, including the
additional stream's source fitting. Exact verification costs are recorded as
their own meter category. All SymKAN counters are0: no inducer ran, no induction
success is claimed; both accounting identities hold exactly.

Portable immutable record: `docs/evidence/wave24_azr_dev_lifelong_v5.json`:

- File SHA256 `df803e5905a11589e830724a25dcdc3c4c3c3ca3b831246640f250310bc65453`.
- Payload digest `98a0c13488780f61bf25f1d357c62caf1f67c024b1c4a68d82abec683873d359`.
- Original worker bytes SHA256 `f94127af04ed49112ba2d88eaeb3c24b762ef92fda53e0d8487f93897788a03d`.
- Executed34-file manifest digest `0520f982ab5114e5a6fe139fd2699734f49c20706e51893dbe634d1431b642db`.
- Config digest `7502343f867afaaedf8f78d16e4c11d84184ab58362bd55bcc8941a225c74b76`.
- Durable stream checkpoint digest `282029b95c0ce6d123c08a63f10406aaa1bd01ec78487d9f2db4bf77f9da08f2`.

The record archives22 executed source/config/test/protocol files and12 immutable
dependency hashes. Post-run edits only add portable receipt consumption, retry
refusal, saved-artifact tests, concise CLI output and this documentation.
Manifest8 identifies executed bytes; manifest9 adds its consumed receipt.
The algorithm was not rerun or tuned after outcomes. All five consumed receipts
survive cloning, and the default preflight refuses a second launch.

Current prospective35-file manifest9 digest:
`a24cb7b03baa1f4c87218cfc2b42c1911e5259092fe01652967b584d3ecf8dda`.
This identifies receipt-hardened code, distinct from the executed manifest8.
The branch reflog contains only its creation at the unchanged base; no commit,
amend, reset or rebase was performed. Current `git status -sb`:

```text
## codex/wave24-azr-ruler-cegis
 M docs/NEXUS_CANONICAL_CURRENT_STATE.md
 M docs/NEXUS_CODE_REUSE_MAP.md
 M src/nexus/seed/public_failure.py
?? configs/wave24_azr_dev_allocation.json
?? configs/wave24_azr_dev_frontier_allocation.json
?? configs/wave24_azr_dev_lifelong_allocation.json
?? configs/wave24_azr_dev_role_allocation.json
?? configs/wave24_azr_dev_workspace_allocation.json
?? configs/wave24_azr_ruler_cegis.json
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_PROTOCOL.md
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_SOURCE_PREFLIGHT.md
?? docs/evidence/
?? scripts/run_wave24_azr_ruler_cegis.py
?? scripts/verify_wave24_azr_ruler_cegis.py
?? src/nexus/wave24_auto_laws.py
?? src/nexus/wave24_lifelong_streams.py
?? src/nexus/wave24_pytest_guard.py
?? src/nexus/wave24_quotient_core.py
?? src/nexus/wave24_resource_host.py
?? src/nexus/wave24_self_evolving_loop.py
?? tests/test_wave24_lifelong.py
?? tests/test_wave24_lifelong_streams.py
?? tests/test_wave24_parametric_frontier.py
?? tests/test_wave24_quotient_soundness.py
?? tests/test_wave24_resource_host_and_runner.py
?? tests/test_wave24_roles_ratchet.py
?? tests/test_wave24_workspace.py
```

### One next scientific question — proposed, not executed

On fresh independently generated source curricula, does a frozen source-trained
symptom policy improve **portfolio reachability** under equal search work compared
with canonical ordering when both arms receive exactly the same fixed shortcut
library? INT_SEQ and STATE_TRANSITION lost correct solutions under adaptive
portfolio choices, while frozen target recipes helped without the doctor.
This isolates learned search guidance from library/caching effects before any
claim of a better learning procedure. No new run or architecture sweep is started.

## Previous revision4 report — preserved chronology

## Latest: requested multi-hop workspace development revision 4

The owner requested implementation and ONE development preflight, with an
explicit commit/push hold. Work remains in the scratch worktree on
`codex/wave24-azr-ruler-cegis`, committed HEAD
`073d9297e6b9b350368f31ee7d18418ef9071634`. No Commit1, final cryptographic seed,
post-freeze assessment, main change, history rewrite, or remote push occurred.
The old negative MDL experiment and every historical artifact remain unchanged.

### Implemented mechanics and exact proof scope

- Anonymous operator roles and raw trusted Python-tool ingestion reuse
  `AutoOperatorFingerprinter` and `OpenPythonToolboxAdapter`. Empirical roles
  drive ordering and source functor matching; only the separately certified
  structural laws can eliminate a class during a uniqueness proof.
- `PhenotypeAffinityCompass` combines canonical typed UTF-8 bytes, raw DEFLATE
  (`level=6,wbits=-15`), symmetric/clipped finite-string NCD, multiset Jaccard
  and measure delta at .40/.40/.20. Missing differs from None, dictionary keys
  are canonical, and tuples/lists/booleans/integers do not alias. Compression,
  bytes, tokens, caches, indexing and commits are metered. This heuristic is
  neither a semantic oracle nor a mathematical metric.
- `StigmergicWorkspaceEngine` runs at most3 hops, B_hop=B0=3,3 new public-island
  slots (EXPLOIT / ROLE_BRIDGE / NOVELTY), full primitive cap6. A bridge can be
  farther from the target than x. Each island retains executable primitive
  syntax of x, loaded at hop cost1, never a supplied target-valued constant.
  Zero new public signatures stops exploration. Every distinct query value of
  a selected public island survives; the single stored twin is just a summary.
  A three-query-value/non-injective-parent regression prevents alpha2 truncation.
- The core interpreter, quotient recurrence, independent exhaustive recurrence,
  grammar checker and twin proposer all understand typed workspace leaves.
  Unfolded witnesses, folded derivations, hop/primitive costs and complete-hop
  semantic digests are saved. An independent verifier reconstructs each hop
  without quotient pruning, checks previous island membership, all query
  variants and minimum primitive costs, then verifies the final certificate.
- A failed twin never proves uniqueness. B's precise scope is **the reached
  hop's declared grammar**, not all possible later portfolios or every
  primitive program of cost<=6. This is versioned config v3 and a different
  search space from v3's evolved-step-only grammar and v2's infeasible MDL
  grammar. A is still the original primitive-B0 space with the 80/20 scheduler.
- Source-only workspace exploration adds at most2 generated source signatures
  per training world to the existing frontier. Actual derivations generate
  labels for the unchanged ten-feature ridge critic. Open contexts with
  incremental primitive cost2..3 pass source descriptor-rent checks and the
  <=3-skill cap before retention. Source roles lift to transferable functors.
  Returned target compiled contexts are **unpromoted** proposals; they cannot
  change the frozen library, critic or source preferences.
- `OpenToolboxLearningEngine` connects this path to the bounded existing API,
  E1 journal, source learner, scorer and immutable target solves. No generated
  source execution, arbitrary import, hostile-code sandbox, live GUI promotion,
  unrestricted background agent or external permission is added.

### One launch: exact development outcome

Allocation: `configs/wave24_azr_dev_workspace_allocation.json`, attempt
`dev-24001-workspace-v4`, CPU only,25s combined worker/verifier wall,25s worker
CPU,1024MiB sampled RSS,zero environment interactions. The inspected dev seed
24001 is reused explicitly as DEVELOPMENT. Both tiers in all five worlds,
five methods,two acquisition passes: **10 task contexts /100 complete cells**.
Repeats are not additional independent tasks. The source library is frozen
before evaluation generation; the teacher query never enters the solver.

Exact independent verifier output:

```text
integrity_valid: true
false_certificate_count: 0
completed_tier1_exact_agreement: true
stage2_reduces_work_to_uniqueness: true
stage3_reduces_work_to_uniqueness: true
stage4_reduces_work_to_uniqueness: true
certificate_b_deep_horizon: true
source_frontier_and_rows_each_permitted_world: true
intra_domain_promotions_each_source_world: true
cross_domain_role_functors: true
zero_shot_transfer_without_target_training: true
disagreement_positive_source_feedback: true
source_workspace_exploration_and_compilation: false
scientific_gates_passed: false
ready_for_freeze: false
errors: []
CLI exit: 1
```

Source receipts (tasks / generated rows / retained skills / extra deep tasks /
compiled candidate contexts / explored hops):

- INT_SEQ: **3 /18 /3 /0 /0 /2**. Stopped with no new public signatures.
- STR_PARSE: **6 /54 /3 /2 /6 /3**. Reached the hop cap.
- DICT_RECORD: **4 /36 /3 /2 /6 /3**. Stopped with no new public signatures.
- STATE_TRANSITION: **8 /96 /3 /2 /6 /3**. Reached the hop cap.
- Fifth world: **0 task training /0 fitting rows**,3 zero-shot proposals.

Total21 source tasks (15 B0-frontier +6 workspace-derived),204 generated rows,
114 fitted rows,12 source skills,6 role functors. The critic uses20 ridge
coefficients plus20 source RMS scales; this is not neural architecture training.
It made776 CPU scoring calls and one CPU weight update. No source disagreement
feedback or held-out outcomes were fabricated.

All five independent deep contexts have verified bounded witnesses and teacher
query coverage. INT_SEQ is **AMBIGUOUS_WITNESS_FOUND**, not a uniquely identified
answer. STR_PARSE,DICT_RECORD,STATE_TRANSITION and BIT_CELLULAR_AUTOMATA have
unique query outputs within their reached hop grammar. All static B0 methods
return NO_PROGRAM on these deep contexts. **Every scored deep task finished in
hop1**, using the frozen skill grammar: this run does not establish that target
island hopping improves acquisition, nor that all cost6 functions are reachable.
Unit fixtures separately demonstrate hop1->hop2 depth4/5 synthesis and actual
one-step compilation. Those fixtures are correctness evidence, not fresh tasks.

### Why readiness remains blocked

The all-source compilation gate was declared BEFORE this launch. INT_SEQ's
recorded source probes are `(1,0,0)`, `(0,)`, query `(1,0,1)`. Hop2 had no new
public signatures; no extra deep source task or multi-hop compiled context was
generated there. This is saturation of the selected source workspace view,
not proof of global impossibility or evidence that the compiler is absent.
The unchanged unit test demonstrates compilation on a non-saturated increment
grammar. All four source worlds did retain ordinary source skills.

The run is **COMPLETE, mathematically valid, and NEGATIVE on its full declared
development screen**. It is not invalid execution, an incomplete grid or an
acceptable all-green freeze. No new seeds, longer source inputs, easier gate,
second launch or post-hoc task replacement was used to turn this result green.
Separate unfiltered historical regression coverage also remains unestablished:
protected historical/GPU experiments cannot be reopened by `pytest -v`.

### Costs, preserved evidence and current source distinction

Worker wall1.4612342920154333s + independent replay0.7167142499820329s =
**2.1779485419974662s debit**. Internal worker CPU0.902256s, sampled peak
219.3125MiB. Carried used**3570.0953012089894s**, remaining**29.90469879101056s**.
No GPU operations, LLM/world-model calls, new environments or historical weight
changes. The cached six-feature CPU/MPS table is NOT revalidated for ten features.

First/repeated acquisition work per pass in method order:
**2034 /1178 /1150 /1469 /17492**. Matched Tier1 uniqueness sums over both
passes: **2034 /1118 /1098 /1394 /15700**. Source learning168123 work, new
setup1057 + conservative cached1228380 = reported setup1229437. At20 calls
per method, full-cost stage5 is **1432544 versus4068** primitive-baseline work;
there is **no full-cost break-even or overall speed improvement**. Only stage2
breaks even in this tiny run. Different horizons and extra computation are not
evidence of a learned efficiency advantage. All four SymKAN counts remain0.

[Exact v4 payload, receipt, verifier and source snapshot](evidence/wave24_azr_dev_workspace_v4.json):
payload digest `4db63a307a868b8601ba503aa80c5cefa2d85467ed9b1d9c0527b02a2b97dc6d`;
worker byte SHA256 `f52c3e7e269bcc1c584bc03aaa149c2eb35212924c0759aeac84b6fbdfb010e8`.
Executed source manifest **v6,29 files**. The following portable receipt guard,
fourth fresh-clone debit, contradiction handling and failed source-cycle limit
were hardened AFTER this snapshot, with focused regression tests only. Current
prospective manifest v7 additionally binds the v4 evidence file; it is not
misrepresented as having had another scientific preflight. The consumed default
command now refuses a second launch before any worker or seed generation.

Before launch: **143 passed in1.90s**, JUnit
`/tmp/nexus-wave24-workspace-freeze-candidate-tests.xml`. This includes all new
unit modules, deceptive operators, independent certificates, both old negative
dev replays, the v3 replay, selected boundary/interpreter/checkpoint and API
regressions. Two earlier engineering assertions caught an overly broad fixture
portfolio expectation and an incorrectly reconstructed critic fingerprint; the
fixture now tests the intended selected public class, and the fingerprint uses
the actual versioned critic wrapper. No scientific data or outcome changed.
Post-accounting test results and final provenance are appended below.

**One next scientific milestone:** a predeclared source-frontier headroom and
equal-workspace baseline comparison using source probes selected by structural
coverage before outcomes. Establish that the workload exercises deep hopping,
then compare learned skills with source-free same-hop planning including all
discovery/validation/retention cost. This proposal is NOT executed here.

### Final v4 source checkpoint (post-run accounting and API hardening)

The final focused/regression command is the focused command in the preserved
test section below, extended with `tests/test_wave24_parametric_frontier.py`,
`tests/test_wave24_roles_ratchet.py`, and `tests/test_wave24_workspace.py`:

```text
148 passed in 2.67s
JUnit: /tmp/nexus-wave24-workspace-v4-final-verified.xml
git diff --check: clean
```

All five current Wave24 test modules ran, plus the selected independent
historical boundary/interpreter, binary-integrity and public API regressions.
This is explicitly **not** an unfiltered historical-suite pass. Protected
closed experiments/GPU tests remain excluded from execution, not counted as
passing. No ordinary regression command ran another scored preflight.

An independent saved-JSON arithmetic audit (separate from the verifier) confirms
the exact100-cell grid,10 contexts,all per-method work sums,full-cost ledgers,
all four consumption debits,all executed source snapshots,and the four unchanged
historical result/manifests. `local_model_runtime.py` is byte-identical to HEAD,
SHA256 `5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.
The post-run hardening adds four-receipt portable debit/refusal, contradictory
observation handling,failed source-cycle charging,and bounded consumption of
callable/skill iterators with an explicit three-skill API cap. These current
files passed deterministic regressions and saved-output replay; no new scientific
run followed. The actual executed v6 sources remain embedded unchanged.

- Executed29-file v6 manifest digest:
  `dc13f0c83d66ed88f917d0d0350fede581c35f11b3119266f9575b8001ae68c0`.
- Prospective30-file v7 manifest digest:
  `75d0315133da37b74825fd677237815f377678daba53744b245a943ede62e971`.
- Whole v4 evidence-file SHA256:
  `7fd74700ebefc4b98a701937b85260f50136a7bde8e8534ccfc59ac52dabb96b`.
- Whole v3 evidence-file SHA256:
  `ab81023a08a8572d13a01658777d0c27ca8f3a5cec933b00925ed556250614c1`.

Current branch/HEAD remain unchanged; nothing staged,committed or pushed.
The final observed status is:

```text
## codex/wave24-azr-ruler-cegis
 M docs/NEXUS_CANONICAL_CURRENT_STATE.md
 M docs/NEXUS_CODE_REUSE_MAP.md
 M src/nexus/seed/public_failure.py
?? configs/wave24_azr_dev_allocation.json
?? configs/wave24_azr_dev_frontier_allocation.json
?? configs/wave24_azr_dev_role_allocation.json
?? configs/wave24_azr_dev_workspace_allocation.json
?? configs/wave24_azr_ruler_cegis.json
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_PROTOCOL.md
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_SOURCE_PREFLIGHT.md
?? docs/evidence/
?? scripts/run_wave24_azr_ruler_cegis.py
?? scripts/verify_wave24_azr_ruler_cegis.py
?? src/nexus/wave24_auto_laws.py
?? src/nexus/wave24_pytest_guard.py
?? src/nexus/wave24_quotient_core.py
?? src/nexus/wave24_resource_host.py
?? src/nexus/wave24_self_evolving_loop.py
?? tests/test_wave24_parametric_frontier.py
?? tests/test_wave24_quotient_soundness.py
?? tests/test_wave24_resource_host_and_runner.py
?? tests/test_wave24_roles_ratchet.py
?? tests/test_wave24_workspace.py
```

## Preserved development revision 3 — role-ratchet gate pass

The preceding run completed before the workspace attachment. It remains in
[its exact separate record](evidence/wave24_azr_dev_role_v3.json), payload
`442a86adc6296b42af836809e2e684a6dfbb82dffbe8525f67e4f2887b67a900`.
10 contexts/100 cells,zero false certificates,all its registered gates passed,
12 source skills,14 functors,3 zero-shot fifth-world skills,zero fifth-world
task training. Generated126 rows,fitted98. Worker1.2127454580040649s +
replay0.32106024998938665s =1.5338057079934515s debit; remaining32.082647333008026s.
This passed a different evolved-step-only development grammar, NOT the new
all-source workspace compilation gate or the old infeasible MDL gate. Its
executed v5 snapshot is preserved; it is not relabeled as a v4 result.

## Preserved v2 preflight chronology

The earlier blocked conclusion below refers to the unchanged MDL proposal at
that time. Later explicit owner design revisions supersede that proposal, not
its negative evidence. All old records remain immutable.

## Latest: explicitly requested frontier-fix development revision 2

The owner requested this follow-up implementation and one development rerun.
The original failed dev launch below remains immutable. Nothing was committed
or pushed; no final seed, final bank or post-freeze assessment was generated.

### Implemented and tested

- `ZeroDataFrontierSelfPlay.wake` now completes one metered full-signature
  quotient DAG on seed probe inputs and selects nonconstant minimum-cost
  frontier classes. It does not reject random syntax until a lucky task occurs.
- Binary ancestor/nonancestor and query-disagreement membership rows feed a
  separate `DerivationOutcomeCritic` using the existing ridge implementation.
  Negative examples belong to ancestor cost tiers. These are not elapsed-time
  targets; predictions are negated for ascending search priorities.
- `ParametricSkillMacro` is a pure typed open AST with one or two linear holes.
  Its call receives actual intermediate expressions. Both quotient and the
  independent exhaustive syntax recurrence enumerate these calls. Interpreter,
  wire format, grammar membership, cooperative evaluation and certificate
  replay understand them. Primitive expansion excludes hole loads, then adds
  actual argument costs. MDL adds the true library-size code plus arguments.
- Anti-unification groups repeated depth-2/3 contexts from distinct frontier
  derivations, scores exact finite-source quotient compression, checks actual
  prospective library-size compression, and preserves the existing positive
  source-shadow Hoeffding-LCB gate. Finite compression is not a population CI.
  Nonpositive later source utility automatically appends quarantine evidence;
  it cannot erase journal entries or consume assessment feedback.
- CPU/MPS crossover routing also controls weight updates. With the saved
  calibration showing CPU faster at every size, no slower Metal path is forced.
  New artifacts expose both batch-time dictionaries and `selected_device=cpu`.
- A typed deterministic increment fixture proves genuine Certificate B
  reachability: a three-operation open skill applied to an intermediate result
  reaches primitive cost 5 at MDL cost 4 while primitive B0=4 returns NO_PROGRAM.
  This is a unit fixture, not a fifth-world scientific result or a promoted
  assessment skill. A second skill's longer code can erase that compression;
  the library-size test verifies this explicitly.

### Mathematical corrections and unchanged entry conditions

The requested universal 100% frontier yield is not valid for arbitrary
grammars: an identity-only grammar has no nontrivial frontier. The miner reports
empty bands rather than inventing tasks. Full-signature minimum cost rules out
a cheaper program with identical public AND query outputs; it does not rule out
a cheaper public-fitting program with another query answer. A separate
identity/abs counterexample and public-only minimum-cost diagnostic verify this.

At the unchanged B0=3, the required incremental skill interval `[3,B0-1]` is
`[3,2]`: empty. Also, two or three skills cost 3 MDL units per call before the
argument's positive cost, so no such call fits MDL bound 3. Counting a hole
load twice would manufacture compression. The fifth world continues to forbid
source and test-time self-play, so requiring its newly learned skill count to
be positive conflicts with that prohibition. Neither B0 nor the fifth-world
policy was changed in this task. The proposed alternatives were raised for an
explicit design decision, not inferred from silence.

### Exact v2 preflight outcome

The tested implementation and development revision were recorded in the
working tree before the launch. Source manifest version 3 binds the executed
23-file snapshot. The one allowed command was:

```sh
PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/run_wave24_azr_ruler_cegis.py --dev-preflight
```

New allocation: `configs/wave24_azr_dev_frontier_allocation.json`, distinct
attempt `dev-24001-frontier-v2`, CPU only, 25s wall/CPU, 1024MiB sampled RSS,
zero interactions. The inspected seed 24001 is DEVELOPMENT, not untouched
confirmation. The original MPS grant was not reused.

- INT_SEQ: 9 retained classes, **5 frontier tasks / 45 training rows / 0 skills**.
- STR_PARSE: 9 classes, **5 frontier tasks / 45 rows / 0 skills**.
- DICT_RECORD: 8 classes, **4 frontier tasks / 32 rows / 0 skills**.
- STATE_TRANSITION: 10 classes, **6 frontier tasks / 60 rows / 0 skills**.
- BIT_CELLULAR_AUTOMATA: **0 training tasks/rows/skills**, as required by its
  unchanged source-unseen boundary; law probes remain allowed.

Total **20 frontier tasks / 182 generated rows / 128 fitted rows**, versus
0/0/0 in v1. One actual CPU ridge update fitted 12 coefficients across the two
heads. The fitting rows contain 44 positive ancestor labels and **zero positive
disagreement labels**. Public probe signatures distinguish every retained
source class in this run, so the disagreement head has no positive signal.
No positive disagreement feedback was fabricated. With no eligible skills,
there were zero critic scoring calls during assessment: fitting a critic is
not evidence it improved a decision.

The unchanged evaluation grid completed **5 task contexts / 50 cells**, all
independently replayed. `integrity_valid=true`, `false_certificate_count=0`,
all method unresolved rates zero. Stage-2/3/4 completed Tier-1 agreement and
uniqueness-work reductions pass. Matched Tier-1 uniqueness work remains
**1302 / 654 / 644 / 654 / 654** in five-method order. Matched Tier-1 g1 work
is **72 / 74 / 76 / 74 / 74**: g1 is not improved. First/repeated acquisition
sums remain **1017 / 559 / 549 / 559 / 559** each. No learning-derived search
gain is established by these unchanged method scores.

Stage 5 still solves **0/2 independent deep development tasks** (0/4 repeated
cells). The three false scientific gates are `certificate_b_deep_horizon`,
`promoted_skills_each_permitted_world`, and `promoted_skills_every_domain`.
The frontier/row gate now passes. `ready_for_freeze=false`; outer CLI exit 1.
This is a COMPLETE valid negative development result, not INVALID execution.

### Resource debit, raw evidence and test coverage

Worker wall **0.6129887090064585s**, independent verification wall
**0.05442337499698624s**, total new debit **0.6674120840034448s**. Internal
worker CPU counter **0.094177s**; peak sampled worker RSS **211.421875MiB**.
Carried used **3566.3835469589985s**, remaining **33.61645304100148s**.
There were zero new MPS operations, LLM/world-model calls, environment
interactions and checkpoint modifications. The previous measured calibration
table is explicitly cached with payload provenance, not claimed as remeasured.

New measured setup work is 353; conservative cached full setup is 1,228,380,
giving reported setup 1,228,733. Source work is 10,084. Stage-4/5 full-cost
totals are **1,239,935** versus **2,034** exhaustive work over ten calls, so no
full-cost break-even is claimed. Stage 2 alone breaks even (1118 versus 2034).
All four SymKAN counts remain zero, with zero inducer invocations.

Exact raw payload, receipt, verifier and executed mutable-source snapshots:
[v2 preserved evidence](evidence/wave24_azr_dev_frontier_v2.json). Payload digest:
`99d8306aedbef3f271e94ab1ac541a49dbf3c01fc74bc949bc4668bef6cbcbea`.
Host attempt directory is
`runs/experimental/wave24-azr/attempts/dev-24001-frontier-v2/`.
Both consumed receipts now debit a fresh clone once and refuse another launch.

After the run, portable receipt handling, malformed-hole checks, automatic
source quarantine, same-tier negative filtering and prospective library-size
compression rejection were tightened and tested. Those current files are NOT
misrepresented as the exact executed version-3 snapshot. No rerun followed.
Prospective manifest version 4 additionally binds the new preserved receipt.

The final focused/regression command is the earlier focused command below plus
`tests/test_wave24_parametric_frontier.py`; JUnit receipt:
`/tmp/nexus-wave24-frontier-v2-final-verified.xml`. A preceding post-accounting
run exposed two test-fixture errors: the mocked sandbox knew only one consumed
receipt, and an increment-only grammar incorrectly required a nonexistent
same-tier negative. The mock now represents both receipts; a separate branching
fixture proves real negative/disagreement labels. No scientific gate was relaxed.
Final command: **104 passed in 1.32s** (0 failed). The entire source-safe
collection checkpoint also completed: **4106 tests collected in 4.10s**, with
35 protected historical/GPU files explicitly excluded and not counted as
passing (`/tmp/nexus-wave24-frontier-v2-source-collection.log`). That collection
preceded the last added coefficient-corruption test. It was collection only,
not 4106 test executions.

Independent saved-data auditing now regenerates the source DAG labels from
their source-only seeds and checks the saved ridge prediction and normal
equations. A forged training tag/hash cannot hide changed labels. Float32
ridge and independent float64 ridge have coefficient maximum difference
0.00010360741511888927 on a matrix of condition number 997.1152409156434;
the actual maximum prediction difference is only 0.0000016536627276408922.
Coefficient distance alone was therefore the wrong numerical check. The
verifier uses the existing absolute prediction tolerance 1e-4 and specified
normalized backward-error bound `32 * eps(float32) = 3.8146973e-6`. Observed
head-0 error is 2.663233659753684e-7; head-1 error is zero. A test also perturbs
coefficients in a predictively invisible collinear direction and confirms the
normal-equation check rejects it. No training precision, data, scientific
threshold, saved coefficient or recorded result was changed.
The unfiltered historical full suite is not represented as green: it includes
closed scientific/GPU runners and still requires a separate safe regression
coverage audit. No historical tests or outcome artifacts were rewritten.

**Required next decision:** reconcile primitive/MDL bounds and unseen-world
arrival-training policy, and prove nonempty deep semantic strata for the
proposed grammar before authorizing another development run. Preserve this
negative result. Do not freeze Commit 1 or run a final assessment on this basis.

### Final source/provenance checkpoint, still uncommitted

HEAD remains `073d9297e6b9b350368f31ee7d18418ef9071634` on
`codex/wave24-azr-ruler-cegis`. Executed v2 manifest: 23 files, digest
`56ba44fbc224b9939bbc183f8073c48c5afd8c321c5b44e7039aafbe420e2dda`.
Current prospective v4 manifest: 24 files, digest
`981f4c2c478fa91cd668aa9348ee8fb1452c7b94c4196a9e645060348ce11493`.
This distinction preserves the actual executed bytes when post-run audit checks
are added. Current key source SHA-256 values:

- Quotient core: `0ded572d082a79b1d20f2161ff20d98aad10c01020c57a023739d7fa5eb39955`.
- Self-play/skill implementation: `c8da448116d5832ead229170dda06c5585f94a78886a9d0abff34be552c31c68`.
- Resource host: `ecaf6593c3ca0ce9be491f996d10e6abaf3ce3dc1739fa95a7f7f74ccf9038e2`.
- Runner: `5f5ac0545a00cc5c803e57561de62df9d4fac3815f54023da6273cd38716ce07`.
- Verifier: `8ff6320b567ccef69fd3f5a6281e2cbacc0d8b1740f47a7895456995431cc069`.
- Parametric/frontier tests: `e8525c4ba1c89ca78b1ba8efb86cb00bcd6aba7b8d8e550eb22f353748cbb387`.
- Original v1 evidence file: `84c58d63b9271c40b66cdd72aa31e0bb3155ee565a0ff9c1c69f85f6221967d1`.
- New v2 evidence file: `b228f9b5608ac1ece019e2c139413eb52544f8cee0fbf47ee3613e8611cec204`.

`git diff --check` passes. `git diff --exit-code -- artifacts/
src/nexus/seed/local_model_runtime.py` is empty. No tracked historical artifact
or Track B runtime source changed. The final `git status -sb` checkpoint is:

```text
## codex/wave24-azr-ruler-cegis
 M docs/NEXUS_CANONICAL_CURRENT_STATE.md
 M docs/NEXUS_CODE_REUSE_MAP.md
 M src/nexus/seed/public_failure.py
?? configs/wave24_azr_dev_allocation.json
?? configs/wave24_azr_dev_frontier_allocation.json
?? configs/wave24_azr_ruler_cegis.json
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_PROTOCOL.md
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_SOURCE_PREFLIGHT.md
?? docs/evidence/
?? scripts/run_wave24_azr_ruler_cegis.py
?? scripts/verify_wave24_azr_ruler_cegis.py
?? src/nexus/wave24_auto_laws.py
?? src/nexus/wave24_pytest_guard.py
?? src/nexus/wave24_quotient_core.py
?? src/nexus/wave24_resource_host.py
?? src/nexus/wave24_self_evolving_loop.py
?? tests/test_wave24_parametric_frontier.py
?? tests/test_wave24_quotient_soundness.py
?? tests/test_wave24_resource_host_and_runner.py
```

## Preserved v1 preflight chronology (original failed run)

The remaining sections describe the earlier approved MPS launch and earlier
source snapshots. Their old "current" labels are historical, superseded by the
v2 status above; their numerical outcomes and raw evidence are unchanged.

## Provenance

- Workspace: `/Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai`.
- Branch: `codex/wave24-azr-ruler-cegis`.
- Starting/current committed HEAD: `073d9297e6b9b350368f31ee7d18418ef9071634`.
- Both previously fetched remote references for the preceding cross-family
  Wave24 study matched this base. Main and historical branches are untouched.
- Initial source-only checkpoint: 45 tests passed in 0.56s, plus a safe
  historical regression giving 46 passed. That checkpoint preceded this host
  integration and did not run an assessment.
- The completed older cross-family Wave24 study, including its initial run and
  forward correction, remains separate closed evidence.

## Completed engineering checklist

- [x] `Wave24ResourceHost` uses explicit CPU/MPS devices and exact allocations.
- [x] MPS tensor operations and timing boundaries synchronize before and after.
- [x] CPU/MPS calibration uses batches 16, 64, 256, 512, 1024 and two repetitions.
  Routing never invents a crossover if MPS does not win.
- [x] Actual scorer inference and batched ridge updates have metered device
  adapters. The MPS weight-update path exists but was **not exercised** by the
  dev run, because no source training rows were produced.
- [x] Optional PersistentMetalRuntime calls require a separate LLM grant and a
  fully terminated response. Pure-symbolic cells use deterministic fallback.
- [x] Existing EXPERIMENTAL Sandbox grants, Journal reservations and settlements
  are reused. Worker CPU limits are kernel-enforced; wall time and sampled RSS
  are watched by the parent. RSS sampling is every 20ms, not an assertion of
  exact instantaneous kernel memory isolation.
- [x] Certified structural laws and empirical priors are disjoint. Certified
  rewrites require exhaustive closed-carrier evidence and actual contextual
  membership. Priors only reorder within a cost layer; all deferred branches
  are checked before uniqueness, or the result remains UNKNOWN.
- [x] Both deceptive-operator tests pass: small-probe commutativity cannot
  justify pruning at input 7, even when the small carrier itself is certified.
- [x] Exact child-output caching preserves scoped interpreter semantics. The
  cooperative work backend and ordinary enumerator agree on outputs and costs.
- [x] Single-attempt runner implements the five methods, procedural strata,
  first/repeated acquisition, work endpoints, source learning and hygiene,
  complete grids, partial/invalid preservation and source hashes.
- [x] Strict verifier independently replays certificates, regenerates the
  recorded procedural bank, reconstructs arithmetic and all four SymKAN counts,
  and keeps scientific failure separate from invalid/incomplete execution.
- [x] Post-freeze provenance requires pushed Commit 1, exact Phase-1 bytes,
  anchored ancestry and the available branch reflog. Reflog checks are scoped
  evidence, not proof that erased history could never have existed.
- [x] A consumed dev receipt is versioned outside `artifacts/`. The dev command
  now refuses another launch before reservation, seed generation or GPU use.
  A fresh clone imports its prior debit once using the existing journal.
- [x] The final entry point refuses an already recorded final artifact before
  collecting outcomes. The dev grant cannot authorize final execution.
- [x] Proposed config and protocol are present, explicitly unfrozen.
- [ ] Certificate B deep-horizon development gate passes.
- [ ] Source self-play supplies actual training rows and useful learned skills.
- [ ] Full unfiltered historical regression suite passes.
- [ ] Final assessment allocation exists. It is intentionally not granted here.

## Reuse and implementation boundaries

The existing catalog-based `ObservationalQuotientWitnessEngine` is preserved.
The new recursive typed core adds complete public-plus-query signatures, exact
reachable element scopes, full-state prefix congruence and a separate exhaustive
syntax recurrence. It does not install a new live agent or replace historical
models.

The scorer reuses `nexus.nn.ridge`; provenance reuses
`evolution1.catalogue.digest`; skill promotions use the existing E1 Journal.
The resource host reuses `seed.experimental.Sandbox`, its reservation/debit
contracts and `seed.process_memory`. Existing skill-store ownership was reviewed;
the AST journal view does not replace Session or create a parallel RL framework.

No family-specific pruning tables, hidden task answers, teacher query outcomes
or target feedback enter the source proposer. The fifth world receives no
source training or test-time self-play. Static expansion cost, dynamic primitive
execution work, neural scoring calls and actual wall time are distinct metrics.

## Tests actually performed

Existing local dependencies were used; nothing was installed. Environment:
Python 3.13.5, pytest 9.1.1, PyTorch 2.14.1, Apple MPS available.

The final focused command used:

```sh
PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m pytest -o addopts='' tests/test_wave24_quotient_soundness.py tests/test_wave24_resource_host_and_runner.py tests/test_seed_wave24_cross_family_experiment.py::test_multi_family_ast_bounds_and_zero_compound_boxes tests/test_seed_wave17_boundary_and_cache_invariance.py::test_static_boundaries_and_historical_runtime tests/test_seed_wave17_boundary_and_cache_invariance.py::test_differential_boundary_masks_and_expanded_observations tests/test_seed_wave17_boundary_and_cache_invariance.py::test_legacy_primitive_semantics_and_op_counts_are_unchanged tests/test_acrobot_compute_matched.py::test_frozen_checkpoints_and_lookahead_identity tests/test_seed_api_apply_modes.py -v
```

```text
82 passed in 1.15s
```

These include certificate forgery, missing/duplicate grids, independent SymKAN
accounting, exact cache/work-event equivalence, CPU ridge equivalence,
synchronization order, RSS termination, consumed-grant refusal, fresh-clone
debit preservation and replay of the preserved negative dev outcome.

The first broad source-safe collection found seven pre-existing import errors:
`function_contracts.py` imported a missing `serialize_revision_feedback`.
A minimal deterministic public-JSON serializer was added to its existing owner
without changing feedback generation or inserting operator hints. Source-safe
collection now completes without those errors.

The subsequent broad source-safe run found a missing Acrobot checkpoint,
stopped after 28 passing tests and one failure, and was interrupted at 179.94s.
All ten original Acrobot files were located in the primary local checkout,
verified against the existing manifest, and copied into the ignored scratch
checkpoint directory. No model was retrained or overwritten. The previously
failing checkpoint audit now passes.

A full unfiltered `pytest -v` would also execute protected historical experiments
and GPU tests under expired grants. The optional
`-p nexus.wave24_pytest_guard` conservatively excludes 35 such files and prints
every exclusion. It is not a security sandbox or a claim that excluded tests
passed. The broad run was **not completed**; only the final focused 82-test run
is reported as passing. Ordinary engineering tests are not new scientific
outcome collection. Temporary JUnit receipts remain under `/tmp/nexus-wave24-*`.

An archive regression also caught whole-number floats being re-encoded as
integers during export, changing canonical hashes. The export was corrected
using the original Python-parsed worker output; original runtime data was never
modified. Canonical configuration and payload hash replay now pass.

## Approved single dev launch and actual outcome

The owner explicitly approved one local MPS dev launch, maximum 30s wall/CPU,
1024MiB process memory, zero environment interactions, within the carried
35.432s allowance. This is recorded in
`configs/wave24_azr_dev_allocation.json`; it is now consumed.

```sh
PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/run_wave24_azr_ruler_cegis.py --dev-preflight
```

This launch used seed 24001, one procedurally generated task per world, five
methods and two acquisition passes: **5 task contexts / 50 cells**.
The verifier checked the temporary output. Raw rows, receipt and the exact
executed source snapshots are preserved in
[evidence/wave24_azr_dev_24001.json](evidence/wave24_azr_dev_24001.json).
The existing private host journal also retains the seed, cell records, worker
log and receipt at `runs/experimental/wave24-azr/attempts/dev-24001/`.

```text
integrity_valid: true
false_certificate_count: 0
unresolved_rate: 0.0 for every method
completed_tier1_exact_agreement: true
stage2_reduces_work_to_uniqueness: true
stage3_reduces_work_to_uniqueness: true
certificate_b_deep_horizon: false
ready_for_freeze: false
CLI exit: 1
```

Matched Tier-1 uniqueness work, summed over six cells (three tasks, two passes):

- Exhaustive primitive: **1302**.
- Exact quotient: **654**.
- Quotient plus certified laws: **644**.
- Fixed-bound self-play method: **654**.
- Evolved-horizon method: **654**.

First-acquisition work across all five tasks was 1017 / 559 / 549 / 559 / 559
in method order. Repeated-use work was identical. Repeated calls are not extra
independent tasks. These are tiny development diagnostics, not confirmation.

The STR_PARSE and STATE_TRANSITION tasks had primitive teacher cost 4.
Stage 5 returned NO_PROGRAM_IN_BOUNDED_GRAMMAR for both, on both passes.
All six source attempts per source world were rejected by the frontier rule:
**24 attempts, zero accepted frontier tasks, zero fitted rows, zero candidate
skills, zero promotions**. The scorer parameters are null. Training work still
counts the failed source attempts; it does not mean a weight update occurred.
The saved receipts establish failure to produce training evidence; they do
not identify every rejection cause.

There is a further design limitation: with a source-unseen fifth world, no
typed fifth-world skills, no test-time self-play and equal integer B0/MDL bounds,
stage 5 cannot gain a new fifth-world horizon merely by its name. This conflict
cannot be repaired by relabeling tasks or silently increasing the MDL bound.

## CPU/MPS findings and full-cost accounting

All ten synchronized MPS calibration evaluations ran. CPU/MPS maximum absolute
output difference was **1.4901161193847656e-8**, below 1e-4. No measured batch
favored MPS, so `mps_crossover_batch_size` is null and scoring routes to CPU.

Best-of-two CPU/MPS times in milliseconds by batch:

- 16: 0.022666 / 4.305542.
- 64: 0.047458 / 3.786875.
- 256: 0.108041 / 4.190375.
- 512: 0.153875 / 2.133500.
- 1024: 0.296042 / 2.225333.

Totals including startup/cold work: 10 CPU scoring calls, 10 MPS scoring calls,
3.368624 CPU scoring ms, 467.801501 synchronized MPS ms; zero weight updates and
zero LLM calls. The dev launch used zero new real environment interactions and
no historical world-model training or inference.

Setup work was 1,228,380 logical units; attempted source learning used 3,428.
Across ten calls per method, only stage 2 reached observed full-cost break-even:
1118 proposed versus 2034 exhaustive units. Stage 3 cost 1,229,478 including the
conservative full setup charge; stages 4 and 5 each cost 1,232,926 including
setup/training. None of those reached break-even. Logical arithmetic work
counts and measured GPU/CPU time must not be interpreted interchangeably.

All SymKAN counts are explicitly zero: attempted = nonempty + abstained = 0
and faithful = nonempty = 0. No inducer ran; this is not evidence of induction.

## Resources and carried ledger

- Supervised worker wall: **1.111837500007823 s**.
- Independent temporary-output verification: **0.03629737498704344 s**.
- Total new debit: **1.1481348749948664 s**.
- Sampled peak worker RSS: **353.890625 MiB**.
- Internal worker CPU counter: **0.264833 s** (not total controller/import CPU).
- Carried used: 3564.568s → **3565.716134874995s**.
- Remaining: **34.28386512500492s**.
- Worker resource failure: none. Scientific result: negative Certificate B gate.

The old grant files and historical Track B/Metal ledgers are unchanged. The new
EXPERIMENTAL journal holds this debit; versioned consumption prevents an agent
from claiming a fresh allowance by cloning or changing branches. There is no
final allocation and no automatic retry.

## Source snapshots and preserved history

The dev payload's embedded canonical digest is
`64f34dc30bf3a23578d8eb3196c36be0f5a4f6e2bbf9bbce86125370433f21fe`.
Its original worker-file byte SHA-256 is
`1e1486e7af35e6f0be29bd388a1a2a438caecf71804149b84d22b86d5ee7db5c`.
The executed 19-file source-manifest digest was
`9ca99450fc41ff11f7276c6df64d82dd799ff8b632270c2f873c04f0cbd386fb`.

After that launch, only portable consumption/accounting and source-archive
verification were hardened. No generator, learner, candidate-selection rule or
success threshold was retuned. The executed earlier host/runner/verifier/test
sources are archived verbatim. Manifest version 1 identifies that earlier dev
run; version 2 binds the current 21-file prospective freeze. The newer complete
code is **not** represented as having passed another MPS preflight.

Current prospective 21-file manifest digest:
`ab556f875782d0d0174a832634d4580e873f8aa01d68521a6ebdc363d6acc8cc`.
Current key source byte hashes:

- Resource host: `45eed116e5fc83ea636b74424b22125c546990019f5ec29a2c644c97ac144e20`.
- Runner: `53a2ec832bebfa2d4e05281802a305777278aa701099fa67399f0ff34787535e`.
- Verifier: `611687c90bb0be4027e1dee1e2226f53d4c39094430517eb6f00ce36361ba22a`.

All four historical Wave24 JSON artifacts are byte-identical before and after
the dev launch. Their complete-file hashes remain:

- Current cross-family result: `ea936f2778441c204e99a442bef0fa9a67b7023c3273a78a59fc96055aa6bd14`.
- Current suite manifest: `9a6adcfe088a5e7cd4b3980e804626f78a46e12f8ed1252a96584ec19f4365b2`.
- Preserved initial result: `5a5da426ed2546751bd03aee00431051bf7e0ea64ed0176ecdf93e9750dd6ddc`.
- Preserved initial manifest: `20d4e19b215012b72b7cf7165fcb38dbd8d68dd23763efe84be16acd8771e73a`.

Embedded canonical payload hashes and whole-file byte hashes are different
representations and must not be confused. No historical experiment result,
checkpoint contents or closed seeds were changed. No source was amended,
rebased or reset.

## Required next action

Keep Commit 1 blocked. Perform a focused **source-frontier and typed-skill
feasibility audit** to establish why the locked source recipe yields no usable
learning evidence and whether the proposed unseen-world horizon claim is
representable at all. Do not launch another benchmark, enlarge the model or
weaken the certificate gate to obtain a green result.

Current `git status -sb` is recorded below; everything remains uncommitted.

```text
## codex/wave24-azr-ruler-cegis
 M docs/NEXUS_CANONICAL_CURRENT_STATE.md
 M docs/NEXUS_CODE_REUSE_MAP.md
 M src/nexus/seed/public_failure.py
?? configs/wave24_azr_dev_allocation.json
?? configs/wave24_azr_ruler_cegis.json
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_PROTOCOL.md
?? docs/NEXUS_WAVE24_AZR_RULER_CEGIS_SOURCE_PREFLIGHT.md
?? docs/evidence/
?? scripts/run_wave24_azr_ruler_cegis.py
?? scripts/verify_wave24_azr_ruler_cegis.py
?? src/nexus/wave24_auto_laws.py
?? src/nexus/wave24_pytest_guard.py
?? src/nexus/wave24_quotient_core.py
?? src/nexus/wave24_resource_host.py
?? src/nexus/wave24_self_evolving_loop.py
?? tests/test_wave24_quotient_soundness.py
?? tests/test_wave24_resource_host_and_runner.py
```
