# VoltDB monitoring dashboards — working notes

This repo holds the public Grafana dashboards for VoltDB (`dashboards/Volt-V15.x/` is the
actively maintained set), Prometheus scrape configs, and small tools. Test/dev harness
(docker compose clusters, workload, licenses) lives in the **private** `volt-monitoring-infra`
repo — never add harness files, `license.xml`, or `.env` here.

## Editing dashboards

- **Surgical edits only.** The JSON files are not in one canonical format; running
  `tools/normalize-dashboards.py` reformats all 47 dashboards and produces an unreviewable
  diff. Edit the exact strings in place (Edit tool or targeted string replacement) and keep
  the diff limited to the values you meant to change. Validate with
  `python3 -c "import json;json.load(open('<file>'))"` after every edit.
- Dashboard uid scheme: `volt-v15x-<name>`. Datasource is the `prometheus` uid; don't
  reintroduce `${DS_*}` template inputs.
- Default time range is `now-1h` on all dashboards; keep new dashboards consistent.

## Panel descriptions (tooltips)

Written for **operators who do not know VoltDB internals** and may barely know the
application. Every panel description must:

- Say **what the graph shows and why someone would look at it** (what decision/alert it
  supports), in 1–3 plain sentences, no emojis.
- Keep **operational nuances and explain their visible effect** — e.g. CPU is the VoltDB
  *process*, not the whole machine; procedure invocation counts include replica re-runs so
  they exceed client TPS; command-log queue is always 0 with synchronous logging; import
  backlog can dip slightly negative from timing; export "missing" tuples usually refill when
  a down node rejoins.
- Contain **no implementation detail**: no raw metric names (`voltdb_*`), no
  `@SystemInformation`/CAPS tag names, no PromQL, no "how the metric is captured".
- Contain **no author meta-caveats** ("tracked separately", "see note", TODO).
- Match the query, not the title: verify rate vs cumulative total, per-node (`by (host_name)`)
  vs cluster aggregate (`sum`/`max`), current instant vs `increase(...[$__range])`,
  and units before writing "per second", "total", "each server", or "currently".

## Query/panel gotchas (bugs we actually shipped and fixed)

- **Cumulative counters in stat tiles**: use reducer `lastNotNull`, never `sum` (a `sum`
  reducer over a range query adds the counter once per scrape → wildly inflated number).
- **"Free capacity" panels** must subtract the *open/current* gauge from the limit, not the
  cumulative *accepted* counter.
- **Cluster tiles** showing a single value for a multi-node cluster: prefer `max(...)`
  ("worst/busiest node") and say so in the title/description; `sum(rate(...))` of a
  per-node fraction can exceed 100% and falsely trip thresholds.
- **Units**: VoltDB metrics are base-unit (`_seconds`, `_bytes`). Set the Grafana unit to the
  base unit (`s`, not `ms`) and express thresholds in base units too (50 ms = `0.05`).
  **Known exporter bug (15.3, Jira pending)**: the DR producer/consumer and export
  `last_*_timestamp_seconds` gauges actually export epoch **milliseconds** (topic/ttl/
  conflict/readiness timestamps are correct seconds). Panels/rules using them must divide
  by 1000 for second math — or use Grafana datetime units, which expect ms. Verify with a
  live query (`> 1e11` ⇒ ms) before trusting any `_timestamp_seconds` metric.
- **Always filter by `namespace="$cluster"`** (and usually `host_name=~"$host"`) — a missing
  cluster filter silently mixes data from every monitored cluster.
- **Titles must match the query**: don't say "5m" if the query uses `$__rate_interval`,
  don't say "max" if the panel shows percentiles, don't use present tense ("Failing") for
  cumulative have-ever-failed counters.
- **Initiator vs per-site metrics** (`voltdb_initiator_procedure_*` vs `voltdb_procedure_*`):
  initiator counters/latency count each transaction **once** and measure the full
  request-to-response path ("initiator latency" — a term clients know; OK in titles).
  Per-site metrics count the K-safety fan-out (once per partition copy) and time only the
  procedure body. Use initiator metrics for client-experience panels (TPS as clients see it,
  error rates, latency percentiles); per-site metrics for locating problems (hot partition,
  slow procedure, failing site) — and say which one a panel shows in its description.
  Some counters (e.g. `initiator_procedure_aborted_total`) are absent until the first event —
  guard stat tiles with `or vector(0)`.

## Table-cell visuals (Nodes-style tables)

- Gauges/LCD bars in table cells are only meaningful against a **real maximum**: show ratios
  (RSS / physical RAM, heap used / heap max) with 0–100 bounds, not raw values scaled to the
  column (column-relative bars convey nothing).
- **Sparklines** need range queries (`format=time_series`, instant=false) plus the
  `timeSeriesTable` transformation (produces `Trend #<refId>` fields), then join with
  `joinByField` on `host_name`.
- Timestamp columns rendered with `dateTimeFromNow`: a 0 value renders as "~57 years ago" —
  add a value mapping `{"0": {"text": "Never"}}` (or similar placeholder).
- Empty time series that should read as "zero" can use
  `(EXPR) or (vector(0) unless on() (EXPR))` to draw a 0-line without spurious series.

## Verifying changes

- The private harness (`volt-monitoring-infra/compose/v15`) runs 2 XDCR-paired clusters,
  Kafka import/export, topics, TTL, scheduled tasks and a workload — Prometheus on
  `localhost:9090`, Grafana on `localhost:3000`. Check that a metric you reference actually
  exists and eyeball its live values (units!) before wiring a panel to it.
- Authoritative metric semantics: `internal/volt-server/src/main/resources/org/voltdb/metrics/`
  `v1/exporter/http/handler/prometheus/bundle/helpMessages_en_US.properties` (official help
  text per metric) and the stats sources under `org/voltdb/stats/` in the internal repo.
- A per-dashboard review sweep (does each description match its query?) catches real bugs —
  when making broad edits, verify panel-by-panel against `targets[].expr`, not from memory.
