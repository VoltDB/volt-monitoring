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

## Quick GDG tutorial

Unfortunately, until Grafana adds support for native dashboard git storage, we need to handle it ourselves.
Here I describe how we can easily import dashboards from Grafana to a local disk and then upload them to our dashboards repo.
(It is a manual process, you need to run these commands every time you make changes to our dashboards if someone has too much free time at work, feel free to automate it :P - and ping me before because I already tried some approaches and I might be able to help)

Prerequisites:

You need to download [gdg](https://github.com/esnet/gdg). It is the tool that we use to download dashboards - https://github.com/esnet/gdg/releases. Find the one for your architecture, and download it.
Unpack the archive and move it to some convenient place for you.

Add it to your PATH.
Run `gdg ctx new grafana-central1`
And configure our Grafana context accordingly:

```
? Will you be using a Token, BasicAuth, or both? basicauth
? List the folders you wish to manage (example: folder1,folder2)? (Blank for General)? VoltDB
? Please enter your datasource default username
? Please enter your datasource default password
? What is the Grafana URL include http(s)? http://104.155.171.198/
? Destination Folder?
? Please enter your admin UserName admin
? Please enter your admin Password *****
```

BONUS TIP
```
Your context configuration will be saved to /Users/<user>/conf/importer.yml. GDG uses this file if it can't find one in your directory.
```

Run `gdg ctx list`, to verify if our context configuration is active. grafana-central1 should be marked as active

Run `gdg dash list`, to list available dashboards,

Now, we can go to the repo with dashboards if everything is working.

And we can import them using `gdg dash import`.

It will save them to <output_path - we set it to .>/dashboards/<folder - in our case VoltDB>/*

Then we can add them to git, commit and push.
