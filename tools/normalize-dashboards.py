#!/usr/bin/env python3
"""Normalize Grafana dashboard JSON exports.

Run from the repository root after re-exporting a dashboard from Grafana:

    python3 tools/normalize-dashboards.py

For every dashboards/**/*.json it:

- assigns a stable, deterministic dashboard `uid` derived from the file path
  (e.g. dashboards/Volt-V15.x/voltdb-tables.json -> volt-v15x-tables) so that
  re-imports update dashboards in place instead of duplicating them, and so
  that dashboard sets for different VoltDB versions can coexist in one Grafana
- strips volatile export artifacts that churn diffs: top-level `id`,
  `version` and the legacy `iteration` field
- declares used non-core panel plugins in `__requires` (currently the
  Treemap panel) so Grafana warns at import time instead of rendering
  broken panels when the plugin is missing
- resolves dangling datasource inputs: "Export for sharing externally" turns
  datasource uids into ${DS_*} input placeholders and adds an __inputs block.
  If the block is dropped (or a panel nested in a collapsed row is missed when
  hand-editing), those panels fail at render with "Datasource ${DS_*} was not
  found" even though the query is valid. We rewrite every ${DS_*} uid to the
  dashboard's concrete Prometheus datasource uid and drop __inputs.
- re-serializes with stable 2-space indentation

The uid scheme is part of the repository contract: changing it breaks
in-place upgrades for users who imported earlier releases.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWN_PLUGINS = {
    "marcusolsson-treemap-panel": {"name": "Treemap", "version": "2.0.0"},
}


def dashboard_uid(path: Path) -> str:
    rel = path.relative_to(ROOT / "dashboards")
    parts = [p.lower() for p in rel.parts]
    version = parts[0].replace("volt-", "").replace(".", "")  # v15x, k8s-123x
    variant = ""
    if len(parts) > 2:
        sub = parts[1]
        if "legacy" in sub:
            variant = "-legacy"
        # new-metrics / metricsv2 are the default flavour: no suffix
    name = re.sub(r"\.json$", "", parts[-1])
    name = re.sub(r"^voltdb-", "", name)
    uid = f"volt-{version}{variant}-{name}"
    if len(uid) > 40:  # Grafana uid length limit
        uid = uid[:40]
    return uid


DS_INPUT_RE = re.compile(r"^\$\{DS_.*\}$")
DEFAULT_DS_UID = "prometheus"


def concrete_ds_uid(dashboard: dict) -> str:
    """The dashboard's real Prometheus datasource uid (most common), so we can
    substitute it for ${DS_*} placeholders. Falls back to "prometheus"."""
    counts = {}

    def walk(obj):
        if isinstance(obj, dict):
            ds = obj.get("datasource")
            if isinstance(ds, dict) and ds.get("type") == "prometheus":
                uid = ds.get("uid", "")
                if uid and not DS_INPUT_RE.match(uid):
                    counts[uid] = counts.get(uid, 0) + 1
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(dashboard)
    return max(counts, key=counts.get) if counts else DEFAULT_DS_UID


def resolve_datasource_inputs(dashboard: dict) -> None:
    """Rewrite ${DS_*} datasource uids to a concrete uid and drop __inputs."""
    dashboard.pop("__inputs", None)
    uid = concrete_ds_uid(dashboard)

    def walk(obj):
        if isinstance(obj, dict):
            ds = obj.get("datasource")
            if isinstance(ds, dict) and DS_INPUT_RE.match(str(ds.get("uid", ""))):
                ds["uid"] = uid
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(dashboard)


def used_plugins(dashboard: dict) -> set:
    found = set()

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("type") in KNOWN_PLUGINS:
                found.add(obj["type"])
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(dashboard.get("panels", []))
    return found


def normalize(path: Path) -> bool:
    original = path.read_text()
    dashboard = json.loads(original)

    dashboard.pop("id", None)
    dashboard.pop("version", None)
    dashboard.pop("iteration", None)
    dashboard["uid"] = dashboard_uid(path)

    resolve_datasource_inputs(dashboard)

    plugins = used_plugins(dashboard)
    if plugins:
        requires = [r for r in dashboard.get("__requires", [])
                    if r.get("id") not in KNOWN_PLUGINS]
        for plugin in sorted(plugins):
            requires.append({
                "type": "panel",
                "id": plugin,
                "name": KNOWN_PLUGINS[plugin]["name"],
                "version": KNOWN_PLUGINS[plugin]["version"],
            })
        dashboard["__requires"] = requires
    normalized = json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"
    if normalized != original:
        path.write_text(normalized)
        return True
    return False


def main():
    changed = 0
    for path in sorted((ROOT / "dashboards").rglob("*.json")):
        if normalize(path):
            changed += 1
            print(f"normalized {path.relative_to(ROOT)}")
    print(f"{changed} files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
