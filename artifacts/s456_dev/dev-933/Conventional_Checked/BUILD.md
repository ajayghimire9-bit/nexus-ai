# dev-933 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "transactional", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "recompute_affected", "lateness": "none", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
