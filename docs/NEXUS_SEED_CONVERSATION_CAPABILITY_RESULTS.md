# Conversation capability matrix v1 — development results

Protocol lock `14a19f9`, runner directory fix `40b7218`, parent
`c704ca12d75da570adaf1f39fd2128dcb2c57e5f`. Artifact
`artifacts/seed_conversation_capability_v1/seed_conversation_capability_v1.json`.
Independent verifier rebuilt CSV tallies with no model inference (`valid: true`).
This is source-development coverage, not confirmation and not an AGI score.

Standing 2026-10-16 grant: 900 s experiment cap. Observed runner wall was under
one second. Scored CSV tasks made **0** model calls. Closed v2/v2.1 and
repair/real-data artifacts were not rewritten. Scientific ledger carry is
unchanged (2193.632103455996 s used / 1406.367896544004 s remaining).

## CSV chat (integrated)

| Method | Correct | Notes |
|---|---|---|
| tools | 7/7 | Parser + vetted adapters. No cache or capsule. |
| ordinary_cache | 7/7 | Same correctness. One exact-file hit (`csv_fresh_no_inherit` reused `csv_easy_sum` on the same SHA and expected intent). That is allowed exact caching, not a parser inheritance check. |
| nexus_procedures | 7/7 | Same correctness. No extra later-task successes. Capsule reuse was not required for the easy later file. |
| nexus_reset | 0/1 | Fresh session, no journal and no capsules. “Do the same” clarified; nothing executed. |

Unsupported “below 10” and the three-column reuse case wrote no outputs.
Fresh “summarize” after “at least 5” executed with `min=null` on tools and
nexus_procedures.

**Finding:** retained procedures did not beat tools or exact cache on this
locked suite. Reset loses follow-up reference resolution. That is session
state, not a learned learning procedure.

## Coverage probes (not weighted)

| Probe | Integration | Result |
|---|---|---|
| JSON sum | API only | Adapter executed (east total 10). Chat does not accept `.json`. |
| SQLite one-table read | API only | Adapter executed; null amount dropped. **No join through chat.** |
| Config repair | API only | `public_passed=true` via `Baseline` / `RepositoryModel`. Not a chat tool. |
| World goal | Chat | o1 moved to (5, 0). |
| Conversation restart | Chat | Explicit capsule reused after save/load. |

JSON, SQLite joins, and repository repair remain **unsupported in chat**.
Reporting an API probe is not a claim that the GUI can do those tasks.

## Families (not equivalent)

Exact repeat and renamed-schema CSV both succeeded with the same two-op
binder. That is role inference on one-text/one-numeric tables, not
cross-interface generalization. Inappropriate and unsupported cases abstained.
No substantially new mechanism was tested.

## Limits

No process-tree memory sample was collected on this sub-second run. Timing
repeats were not extra task families. A pytest pass is not capability
evidence. Persistence is not learning-to-learn.
