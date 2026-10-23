# Where Seed memory actually lives

`metal_ledger.json` and sleep `*.jsonl` are files. They are not the
Knowledge Vault.

| Kind | Home | Notes |
| --- | --- | --- |
| Documents / citations | `KnowledgeVault` SQLite FTS5 (`facts`) | `doc_id`, title, content, `source_hash`, timestamp |
| Learned lexical bindings | `LexicalCapsuleStore` SQLite (`capsules`) | term, definition, frame, required tokens, use/pass counts |
| Sleep export | JSONL via `write_sleep_jsonl` | Only verifier-passing triples. Failed drafts stay out. |
| Metal grant accounting | `metal_ledger.json` | Wall of `guarded_call` only. Not a memory store. |
| Frozen CPU ledger | documented 3564.568 s | Must not mix with the Metal file. |
| Saved lab procedures | `Lab.procedures_dir()` JSON files | Conversation/workspace transforms |
| Repair schemas | `RepairSchemaStore` JSON | Coding repair families, not lexicon terms |
| Investigation procedures | existing investigation / capsule engines | Not stored in the lexicon vault |

Restart test: close the SQLite connections, reopen the same paths, load
`get_document(doc_id)` and `LexicalCapsuleStore.get(term)`, and check
`source_hash` / timestamp / required tokens. Provenance is the SQLite
row, not the Metal ledger.
