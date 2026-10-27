# de4-dev-973 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "hard_only", "discount_unit": "percent_only", "fx": "none", "fx_unknown": "quarantine", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
