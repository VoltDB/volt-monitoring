#!/usr/bin/env bash
# One-shot: bring up the stack, load schema, drive a workload, audit the panels.
#
#   VOLTDB_IMAGE=voltdb/voltdb-enterprise-dev:<tag> ./run.sh [dashboard-dir]
#
# Reads VOLTDB_IMAGE from .env if present. DASHBOARDS (or arg 1) selects which
# dashboard set Grafana provisions and the audit checks; defaults to V15.x.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] && set -a && . ./.env && set +a
export DASHBOARDS="${1:-${DASHBOARDS:-../dashboards/Volt-V15.x}}"
DURATION="${DURATION:-90}"

if [ ! -f license.xml ]; then
  echo "ERROR: place a VoltDB license.xml in $(pwd) (gitignored)" >&2
  exit 1
fi

echo ">> bringing up stack (image: ${VOLTDB_IMAGE:-unset}, dashboards: $DASHBOARDS)"
docker compose up -d

echo ">> waiting for VoltDB to be healthy"
until [ "$(docker inspect -f '{{.State.Health.Status}}' volt-dash-test 2>/dev/null)" = "healthy" ]; do
  sleep 2
done

echo ">> loading schema"
docker exec -i volt-dash-test /opt/voltdb/bin/sqlcmd < ddl.sql

echo ">> driving workload for ${DURATION}s"
docker cp workload.sh volt-dash-test:/tmp/workload.sh
docker exec volt-dash-test bash /tmp/workload.sh "$DURATION"

echo ">> letting Prometheus scrape a few more samples"
sleep 10

echo ">> auditing panels"
python3 audit_dashboards.py --dir "$DASHBOARDS" --prometheus http://localhost:9090 --namespace test-volt "${@:2}"
rc=$?

echo
echo ">> Grafana:    http://localhost:3000 (anonymous admin)"
echo ">> Prometheus: http://localhost:9090"
echo ">> tear down with: docker compose down -v"
exit $rc
