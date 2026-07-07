#!/usr/bin/env python3
"""Pull UI-edited dashboards out of a running Grafana back into the repo.

Companion to normalize-dashboards.py. For each dashboard JSON in a set, it
computes the deterministic uid, fetches that dashboard from Grafana, and — if it
was edited in the UI (meta.version > 1, unless --all) — writes the exported
definition back to the repo file after the same normalization
(strip id/version/iteration, stable uid, __requires for known plugins).

Usage (run from repo root):
  python3 tools/pull-from-grafana.py --dir dashboards/Volt-V15.x \
      --grafana http://localhost:3000 --user admin --password admin

Then review `git diff` and commit. Only edited dashboards are written, so
untouched ones produce no diff.
"""
import argparse
import base64
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Reuse the exact uid / plugin-requires rules from normalize-dashboards.py so the
# two tools can never drift.
_spec = importlib.util.spec_from_file_location(
    "normalize_dashboards", ROOT / "tools" / "normalize-dashboards.py")
_norm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_norm)


def fetch(grafana, uid, auth_header):
    req = urllib.request.Request(f"{grafana.rstrip('/')}/api/dashboards/uid/{uid}")
    if auth_header:
        req.add_header("Authorization", auth_header)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def normalize_dashboard(dash, path):
    dash.pop("id", None)
    dash.pop("version", None)
    dash.pop("iteration", None)
    dash["uid"] = _norm.dashboard_uid(path)
    plugins = _norm.used_plugins(dash)
    if plugins:
        requires = [r for r in dash.get("__requires", [])
                    if r.get("id") not in _norm.KNOWN_PLUGINS]
        for plugin in sorted(plugins):
            requires.append({"type": "panel", "id": plugin,
                             "name": _norm.KNOWN_PLUGINS[plugin]["name"],
                             "version": _norm.KNOWN_PLUGINS[plugin]["version"]})
        dash["__requires"] = requires
    return json.dumps(dash, indent=2, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--all", action="store_true",
                    help="write every dashboard, not just UI-edited (version>1) ones")
    args = ap.parse_args()

    auth_header = "Basic " + base64.b64encode(
        f"{args.user}:{args.password}".encode()).decode() if args.user else None

    written, skipped, missing = [], [], []
    for path in sorted(Path(args.dir).resolve().glob("*.json")):
        uid = _norm.dashboard_uid(path)
        data = fetch(args.grafana, uid, auth_header)
        if data is None:
            missing.append((path.name, uid))
            continue
        version = data.get("meta", {}).get("version", 1)
        if version <= 1 and not args.all:
            skipped.append((path.name, version))
            continue
        path.write_text(normalize_dashboard(data["dashboard"], path))
        written.append((path.name, version))

    for name, v in written:
        print(f"pulled   {name} (grafana v{v})")
    for name, v in skipped:
        print(f"skipped  {name} (unedited, v{v})")
    for name, uid in missing:
        print(f"NOT FOUND in grafana: {name} (uid {uid})")
    print(f"\n{len(written)} written, {len(skipped)} skipped, {len(missing)} missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
