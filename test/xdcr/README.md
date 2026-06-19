# XDCR (two-cluster) test harness

Brings up two VoltDB clusters peered as XDCR (active-active) over the DR port,
scraped by one Prometheus with `namespace` labels `test-volt-a` / `test-volt-b`,
plus Grafana. Exercises the XDCR dashboard and the DR producer/consumer/conflict
/ sync-snapshot / readiness metrics.

## Run

```sh
cp /path/to/license.xml .          # or it is copied from ../license.xml
echo 'VOLTDB_IMAGE=voltdb/voltdb-enterprise-dev:<tag>' > .env
./run.sh
```

`run.sh` brings both clusters up, loads identical DR schema on each, waits for
readiness, drives writes on both sides (with deliberate key collisions to
generate conflicts), then audits the XDCR dashboard from cluster A's view.
Grafana http://localhost:3000 (pick namespace `test-volt-a` or `test-volt-b`).
Tear down: `docker compose down -v`.

## Verified against `master--840`

- XDCR establishes cleanly; `xdcr_readiness_info{dr_is_ready="true"}` on both
  sides; our new `voltdb_xdcr_readiness_since_timestamp_seconds` emits a real
  timestamp.
- The full DR metric set populates: producer (node + partition: queued bytes,
  queue gap, buffers-waiting-for-ack, last-queued/ack timestamps, round-trip
  histogram), consumer (bytes replicated, last received/applied, available
  buffers, duplicate/ignored), and conflict counters.
- Conflicts register: with colliding PKs written on both sides,
  `voltdb_dr_conflicts_count_total` and `voltdb_dr_row_timestamp_mismatch_count_total`
  climb (hundreds across partitions).
- **XDCR dashboard audit: 38 OK, 1 EMPTY, 0 ERROR.** The one EMPTY panel filters
  `dr_connection_status="DOWN"` and is correctly empty while the link is up.

## Findings on the sync-snapshot progress metrics (client's reinit scenario)

The metrics that answer "how much has transferred to a reinitialized target",
`voltdb_dr_producer_node_rows_acked_for_sync_snapshot_total` and
`..._rows_in_sync_snapshot_total`, exist and are tagged by `cluster_id` /
`remote_cluster_id`. Two caveats found in testing, both worth raising:

1. **Sentinel value when idle.** With no sync snapshot in progress
   (`dr_sync_snapshot_state="NONE"`), `rows_in_sync_snapshot` reports
   `-9223372036854775808` (Long.MIN_VALUE), not 0 or absent. Any
   `acked / in_sync_snapshot` progress panel must guard against this sentinel or
   it shows garbage. Candidate server fix: emit 0 / omit the series when no sync
   is active.
2. **Not observable at test scale / via container reinit.** Restarting cluster B
   empty did not trigger an observable resync (B stayed at 0 rows, no consumer
   bytes) — XDCR reset is a deliberate procedure, not a container bounce. And
   even when a sync runs, a test-scale dataset transfers within a single 6s
   metric interval, so the in-progress value is never sampled. Validating the
   client's scenario needs a real DR-reset procedure and production-scale data
   (or a shorter metric interval).

Net for the client: the metric they want is present, but (a) the idle sentinel
and (b) sampling vs. transfer duration mean a usable "sync progress %" panel
needs both a server-side look at the sentinel and production-scale validation.
