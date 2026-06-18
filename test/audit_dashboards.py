#!/usr/bin/env python3
"""Audit every panel query in a dashboard set against a live Prometheus.

For each panel target it substitutes Grafana template variables with test
values, runs the PromQL against Prometheus, and classifies the result:

  OK     query succeeded and returned >=1 series
  EMPTY  query succeeded but returned no series (feature not exercised, or a
         broken metric/label name that silently matches nothing)
  ERROR  query failed to parse/execute (a genuinely broken expression)

Exit code is non-zero if any query ERRORs, so this doubles as a CI gate. EMPTY
panels are reported but do not fail the run (a single-cluster test has no XDCR
data, no importers, etc.); pass --strict to fail on EMPTY too.

Usage:
  python3 audit_dashboards.py --dir ../dashboards/Volt-V15.x \
      --prometheus http://localhost:9090 --namespace test-volt
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Grafana template variables -> values that make the query runnable. Multi-value
# regex variables become ".*" so a panel filtering on =~"$host" matches anything.
def substitute(expr, namespace):
    repl = {
        "$__rate_interval": "1m",
        "$__interval": "1m",
        "$__range": "1h",
        "${__range}": "1h",
        "$cluster": namespace,
        "${cluster}": namespace,
        "$namespace": namespace,
    }
    for k, v in repl.items():
        expr = expr.replace(k, v)
    # Any remaining $var / ${var} used inside a regex match become ".*",
    # elsewhere become empty-ish wildcards.
    expr = re.sub(r"\$\{?\w+(:\w+)?\}?", ".*", expr)
    return expr


def walk_panels(obj):
    if isinstance(obj, dict):
        if obj.get("type") and obj.get("type") != "row" and "targets" in obj:
            yield obj
        for v in obj.values():
            yield from walk_panels(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_panels(v)


def query(prom_url, expr):
    url = prom_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read())
        except Exception:
            return "ERROR", f"HTTP {e.code}"
    except Exception as e:
        return "ERROR", str(e)
    if data.get("status") != "success":
        return "ERROR", data.get("error", "unknown")[:160]
    n = len(data.get("data", {}).get("result", []))
    return ("OK" if n else "EMPTY"), f"{n} series"


def audit_file(path, prom_url, namespace):
    dash = json.loads(path.read_text())
    rows = []
    for panel in walk_panels(dash):
        title = panel.get("title", "(untitled)")
        for tgt in panel.get("targets", []):
            if not isinstance(tgt, dict):
                continue
            expr = tgt.get("expr")
            if not expr or not expr.strip():
                continue
            verdict, detail = query(prom_url, substitute(expr, namespace))
            rows.append((verdict, title, detail, expr.strip().replace("\n", " ")[:90]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--prometheus", default="http://localhost:9090")
    ap.add_argument("--namespace", default="test-volt")
    ap.add_argument("--strict", action="store_true", help="fail on EMPTY too")
    ap.add_argument("--show-empty", action="store_true", help="list EMPTY panels")
    args = ap.parse_args()

    files = sorted(Path(args.dir).glob("*.json"))
    if not files:
        print(f"no dashboards in {args.dir}", file=sys.stderr)
        return 2

    tot = {"OK": 0, "EMPTY": 0, "ERROR": 0}
    errors = []
    for path in files:
        rows = audit_file(path, args.prometheus, args.namespace)
        c = {"OK": 0, "EMPTY": 0, "ERROR": 0}
        for verdict, *_ in rows:
            c[verdict] += 1
            tot[verdict] += 1
        flag = "FAIL" if c["ERROR"] else ("warn" if c["EMPTY"] else "ok")
        print(f"[{flag:4}] {path.name:32} OK={c['OK']:3} EMPTY={c['EMPTY']:3} ERROR={c['ERROR']:3}")
        for verdict, title, detail, expr in rows:
            if verdict == "ERROR":
                errors.append((path.name, title, detail, expr))
                print(f"        ERROR  {title}: {detail}")
                print(f"               {expr}")
            elif verdict == "EMPTY" and args.show_empty:
                print(f"        empty  {title}  ({expr})")

    print(f"\nTOTAL  OK={tot['OK']}  EMPTY={tot['EMPTY']}  ERROR={tot['ERROR']}")
    if args.strict and tot["EMPTY"]:
        return 1
    return 1 if tot["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
