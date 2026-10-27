# val-7922 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "offsets_first", "dedup": "none", "deletes": "hard_only", "fx": "none", "gold_maintenance": "recompute_affected", "lateness": "watermark", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "iso_only", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
