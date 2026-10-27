# de4-dev-971 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "sink_then_offsets", "dedup": "none", "deletes": "soft_and_hard", "discount_unit": "registry_unit", "fx": "none", "fx_unknown": "error", "gap_handling": "skip", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
