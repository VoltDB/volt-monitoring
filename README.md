# volt-monitoring

This repo provides Grafana dashboards for reporting on Volt Active Data metrics captured by Prometheus. The dashboards are provided as-is and can be used directly or as examples for incorporating Volt metrics into integrated dashboards with other business components. 

## Dashboards

The dashboards are provided in Grafana JSON format and are divided into categories:

- **Volt** - Dashboards for the latest version of Volt Active Data in any environment, including bare metal, Kubernetes and VMs (currently a link to `Volt-V14.x/metricsv2`).
- **Volt-V15.x** - Dashboards for Volt Active Data V15.x (work in progress).
- **Volt-V14.x** - Dashboards for Volt Active Data V14.x (`metricsv2` uses the new metrics system).
- **Volt-V13.x** - Dashboards for Volt Active Data V13.x (`new-metrics` for the new metrics system, `legacy-metrics` for the legacy exporter).
- **Volt-V12.x** - Dashboards for the long-term support (LTS) version 12 of Volt Active Data.
- **Volt-V10.x** - Dashboards for the long-term support (LTS) version 10 of Volt Active Data.
- **Volt-V9.x** - Dashboards for the long-term support (LTS) version 9 of Volt Active Data.
- **Volt-K8s-13.x / Volt-K8s-12.3.x** - Kubernetes-flavoured variants of the V13.x / V12.3.x dashboards.

Within each subdirectory are multiple dashboards, each providing a different view of the database activity, performance, or status. Try the different dashboards to see which ones suit your monitoring needs.

Dashboards will work without any additional configuration inside Kubernetes, if you want to use them for Volt running in other environments, you will need an additional label `namespace` in the Volt metrics. (See below.)

## Installing the Dashboards

The dashboards require a Grafana plugin, `Treemap`, that must be loaded into Grafana before using the dashboards. To load the plugin:

1. Click on the configuration icon in Grafana (the cog at the bottom of the left menu bar).
2. Select the `Plugins` tab.
3. Type "treemap" into the search box.
4. Select and install the Treemap plugin.

For unattended installs (containers, provisioning), install the plugin with the Grafana CLI instead:

```
grafana cli plugins install marcusolsson-treemap-panel
```

or bake it into a custom Grafana image:

```dockerfile
FROM grafana/grafana:12.4.0
RUN grafana cli plugins install marcusolsson-treemap-panel
```

The dashboards declare the plugin in their `__requires` section, so Grafana warns at import
time if it is missing; without it the treemap panels render as broken panels while the rest
of the dashboard keeps working.

Next, you need to select the dashboards appropriate to your Volt version and operating system. Only install dashboards from the subdirectory that matches your operating environment.

There are several different methods you can use for importing dashboards into Grafana. You can download the dashboard JSON files then use the `import` menu item in the Grafana UI to load the dashboards. Alternately, you can include the dashboards using the Grafana REST API pointing to the individual JSON files. Or you can provision a directory of dashboards as part of the Grafana startup process. See the [Grafana documentation](https://grafana.com/docs/) for more information on how to install dashboards.

## Configuring Prometheus and Grafana

For the dashboards to work properly, Grafana and Prometheus must agree on how frequently data is collected. Make sure the scrape interval setting in the Grafana configuration matches the scrape interval in Prometheus.

### Rate-based panels showing "No Data"

Panels that use `rate()` / `increase()` (throughput, transactions/s, per-second
counters) need **at least two samples of the same series within the query
window**. Two things break that:

- **Metric interval vs. query window.** VoltDB's metrics interval defaults to
  **60s**, so a `rate(...[$__rate_interval])` panel needs a window of roughly
  **2× the metrics interval** (≥ ~120s at the default) before it can compute
  anything — otherwise the window contains one value and the panel reads "No
  Data" even under load. Scrape at half the VoltDB metrics interval (e.g. 30s
  scrape for a 60s interval) and make sure Grafana's `$__rate_interval`
  (driven by the scrape interval and panel min-step) comfortably exceeds 2×
  the metrics interval. Lowering the VoltDB metrics interval (e.g. to `6s` in a
  test cluster) makes these panels responsive much sooner.
- **Per-connection metrics + short-lived connections.** Connection-scoped
  series such as `voltdb_initiator_procedure_invoked_total` (labelled by
  `connection_id`) only accumulate while a client connection stays open. Load
  driven through short-lived connections (a new connection per request) creates
  a fresh series each time, so no single series lives long enough for `rate()`
  to compute. Real applications that hold pooled connections are fine; for a
  robust cluster-wide throughput panel, prefer the site-scoped
  `voltdb_procedure_invoked_total` (stable regardless of connection churn — note
  it counts per execution site, so multi-partition/replicated work reads higher
  than client-observed transactions).

## Applying the "namespace" Label

In Kubernetes, the Operator adds the `namespace` label automatically. If you are running VoltDB in another environment (or on bare metal) you must add the label as part of the Prometheus configuration. For example:

```
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "volt"
    static_configs:
    - targets: ["localhost:1234"]
      labels:
        namespace: 'local-volt'
```



## Alerting

The dashboards only colour-code thresholds; no alerts fire out of the box. Example Prometheus
alerting rules covering the most important conditions (reduced k-safety, memory near the
configured limit, command log backpressure, XDCR not ready, failed snapshots, export stalls)
are provided in [prometheus/voltdb-alerts.yml](prometheus/voltdb-alerts.yml). Review the
thresholds against your workload before using them in production.

## Contributing

After re-exporting a dashboard from Grafana, run:

```
python3 tools/normalize-dashboards.py
```

It strips volatile export fields (`id`, `version`, `iteration`), assigns the stable
per-version dashboard `uid` (so re-imports update dashboards in place and dashboard sets for
different VoltDB versions can coexist in one Grafana), and declares required panel plugins in
`__requires`. Commit the normalized JSON only.
