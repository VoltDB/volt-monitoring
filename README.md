# volt-monitoring

I will write it here until we have a proper documentation page on our dashboards and monitoring setup.

## Dashboards

At the moment, we have two sets of dashboards:
- VoltDB - they work in k8s and are based on the `namespace` label
- VoltDB-new - they should work in any environment. They rely on the additional label `cluster`.

Dashboards are currently uploaded to this repo using [gdg tool](https://github.com/esnet/gdg). It is not perfect because it leaves default values, and it is not using the "export for sharing externally" functionality. We should investigate it when we want to make this repo public.

## Dashboard shareability issues

If we want to make our dashboards shareable, we need to remember about couple of things:
-  We should set the data source of the panel to ${datasource}, and not the specific Prometheus data source because it differs between the Grafana deployments
-  If we use the TreeMap panel with only one query, due to this [issue](https://community.grafana.com/t/singles-query-value-name-differs-between-grafana-versions-value-a-and-value/68248), we should add another dummy query with a constant 1 value.

## Setting up Prometheus

To make our dashboards work, you need to configure the Scrape interval rate setting of the Prometheus data source in Grafana.

### Kubernetes

Our helm operator is configured to add this label automatically. We only require users to use a recent enough version of the operator. (I don't know the specific version yet)

### Not Kubernetes

If Volt is not run in Kubernetes, we will need to add additional config to the Prometheus deployment so that it will add this label.
Example config:
```
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "volt"
    static_configs:
    - targets: ["localhost:8484"]
      labels:
        cluster: 'local-volt'
```

It will add a `cluster` label with the value `local-volt`.

In the future, we might add it as a configuration option to the Prometheus agent.
