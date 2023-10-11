# volt-monitoring

This repo provides Grafana dashboards for reporting on Volt Active Data metrics captured by Prometheus. The dashboards are provided as-is and can be used directly or as examples for incorporating Volt metrics into integrated dashboards with other business components. 

## Dashboards

The dashboards are provided in Grafana JSON format and are divided into categories:

- **Volt** - Dashboards for the latest version of Volt Active Data in any environment, including bare metal, Kubernetes and VMs.
- **Volt-V9.x** - Dashboards for the long-term support (LTS) version 9 of Volt Active Data, running in Kubernetes.
- **Volt-V10.x** - Dashboards for the long-term support (LTS) version 10 of Volt Active Data, running in Kubernetes.
- **Volt-V12.3.x** - Dashboards for the long-term support (LTS) version 12 of Volt Active Data, running in Kubernetes.
- **Volt-V13.x** - Dashboards for the long-term support (LTS) version 13 of Volt Active Data, running in Kubernetes.

Within each subdirectory are multiple dashboards, each providing a different view of the database activity, performance, or status. Try the different dashboards to see which ones suit your monitoring needs.

Dashboards will work without any additional configuration inside Kubernetes, if you want to use them for Volt running in other environment, you will need an additional label `namespace` in the Volt metrics. (See below.)

## Installing the Dashboards

The dashboards require a Grafana plugin, `Treemap`, that must be loaded into Grafana before using the dashboards. To load the plugin:

1. Click on the configuration icon in Grafana (the cog at the bottom of the left menu bar).
2. Select the `Plugins` tab.
3. Type "treemap" into the search box.
4. Select and install the Treemap plugin.

Next, you need to select the dashboards appropriate to your Volt version and operating system. Only install dashboards from the subdirectory that matches your operating environment.

There are several different methods you can use for importing dashboards into Grafana. You can download the dashboard JSON files then use the `import` menu item in the Grafana UI to load the dashboards. Alternately, you can include the dashboards using the Grafana REST API pointing to the individual JSON files. Or you can provision a directory of dashboards as part of the Grafana startup process. See the [Grafana documentation](https://grafana.com/docs/) for more information on how to install dashboards.

## Configuring Prometheus and Grafana

For the dashboards to work properly, Grafana and Prometheus must agree on how frequently data is collected. Make sure the scrape interval setting in the Grafana configuration matches the scrape interval in Prometheus.

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


