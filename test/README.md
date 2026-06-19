# Dashboard test harness

Brings up a local VoltDB node with metrics enabled, scraped by Prometheus and
visualized in Grafana, then audits every dashboard panel's PromQL against the
live cluster.

## Prerequisites

- Docker + Docker Compose, Python 3 (stdlib only — no pip installs)
- A VoltDB enterprise dev image and a `license.xml` in this directory
  (both gitignored)

## Run

```sh
cp /path/to/license.xml .
echo 'VOLTDB_IMAGE=voltdb/voltdb-enterprise-dev:<tag>' > .env
./run.sh                              # audits ../dashboards/Volt-V15.x by default
./run.sh ../dashboards/Volt-V14.x/metricsv2   # audit a different set
```

`run.sh` brings up the stack, loads `ddl.sql`, drives `workload.sh`, then runs
the panel audit. Grafana is at http://localhost:3000 (anonymous admin) for a
visual pass, Prometheus at http://localhost:9090. Tear down with
`docker compose down -v`.

Match the dashboard set to the image's metrics generation: the new metrics
system (V13.x `new-metrics`, V14.x `metricsv2`, V15.x) — not the legacy sets.

## What the audit checks

`audit_dashboards.py` extracts each panel target's expression, substitutes the
Grafana template variables (`$cluster` → namespace, `$host`/`$table`/… → `.*`,
`$__rate_interval` → `1m`), queries Prometheus and classifies each:

- **OK** — query returned data
- **EMPTY** — query is valid but returned nothing (feature not exercised in this
  single-cluster test, or a metric/label that silently matches nothing)
- **ERROR** — query failed to parse/execute (a genuinely broken expression)

Exit code is non-zero if anything ERRORs, so this is also the CI gate. Run it
standalone against any Prometheus:

```sh
python3 audit_dashboards.py --dir ../dashboards/Volt-V15.x \
    --prometheus http://localhost:9090 --namespace test-volt --show-empty
```

## Coverage and known EMPTY panels

The single-node, no-DR workload exercises tables, partitions, procedures,
memory, command log, snapshots and export. The following are EMPTY *by design*
here (not dashboard bugs — the queries are valid):

- **XDCR** — needs two clusters (see "XDCR" below)
- **Import / Topics** — no importer or topic configured
- **Tasks** — no scheduled tasks created
- **Table Compaction** — compaction only fires under memory pressure
- **TTL** — works once the schema is correct. TTL only purges rows (and only
  then emits `voltdb_ttl_*`) when the TTL column has a supporting index whose
  first column is the TTL column; without it every delete round aborts with
  "Could not find index to support LowImpactDelete". `ddl.sql` includes the
  index on `sessions(created)`, so the TTL dashboard populates. (Minor real
  gap noticed: that missing-index abort comes back as a success-with-error
  response, so it increments neither `voltdb_ttl_rows_deleted_total` nor
  `voltdb_ttl_failed_total` — the failure is logged but not in metrics.)

## Testing the ENG-29298 metrics

The config/limit and new gauges (`voltdb_memory_limit_bytes`,
`commandlog_backpressure`, `snapshot_in_progress`, `xdcr_readiness_since`, and
the new `deployment_info`/`commandlog_info` labels) only exist in images built
from the ENG-29298 branches. Point `VOLTDB_IMAGE` at a CI build of that branch,
then assert with e.g.:

```sh
curl -s localhost:11781/metrics | grep -E 'voltdb_memory_limit_bytes|commandlog_backpressure|snapshot_in_progress|memorylimit='
```

## XDCR (second phase)

The XDCR dashboard (and the new `xdcr_readiness_since` / DR sync-snapshot
progress metrics) need two clusters configured as peers. That is a separate,
heavier compose file not included here yet; track it as follow-up.
