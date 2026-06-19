#!/usr/bin/env bash
# Bring up a two-cluster XDCR stack, establish replication, drive writes on both
# sides (including conflicts), and audit the XDCR dashboard from cluster A's view.
#
#   VOLTDB_IMAGE=voltdb/voltdb-enterprise-dev:<tag> ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] && set -a && . ./.env && set +a
# fall back to the parent harness's .env / license if present
[ -f .env ] || { [ -f ../.env ] && set -a && . ../.env && set +a; }
[ -f license.xml ] || { [ -f ../license.xml ] && cp ../license.xml license.xml; }
export DASHBOARDS="${DASHBOARDS:-../../dashboards/Volt-V15.x}"
DURATION="${DURATION:-90}"

[ -f license.xml ] || { echo "ERROR: place a VoltDB license.xml here (gitignored)" >&2; exit 1; }

echo ">> bringing up two clusters (image: ${VOLTDB_IMAGE:-unset})"
docker compose up -d

for c in volt-xdcr-a volt-xdcr-b; do
  echo ">> waiting for $c"
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)" = "healthy" ]; do sleep 2; done
done

echo ">> loading identical DR schema on both clusters"
docker exec -i volt-xdcr-a /opt/voltdb/bin/sqlcmd < ddl.sql
docker exec -i volt-xdcr-b /opt/voltdb/bin/sqlcmd < ddl.sql

echo ">> waiting for XDCR to become ready (both sides covered)"
ready=0
for i in $(seq 1 30); do
  a=$(curl -s localhost:11781/metrics | grep '^voltdb_xdcr_readiness_info' | grep -c 'dr_is_ready="true"' || true)
  b=$(curl -s localhost:11782/metrics | grep '^voltdb_xdcr_readiness_info' | grep -c 'dr_is_ready="true"' || true)
  if [ "$a" -ge 1 ] && [ "$b" -ge 1 ]; then ready=1; echo "   XDCR ready after $((i*3))s"; break; fi
  sleep 3
done
[ "$ready" = 1 ] || echo "   WARNING: XDCR not reported ready; continuing anyway (check voltdb-xdcr panels)"

echo ">> driving writes on both sides for ${DURATION}s"
docker cp workload.sh volt-xdcr-a:/tmp/workload.sh
docker cp workload.sh volt-xdcr-b:/tmp/workload.sh
docker exec -d volt-xdcr-a bash /tmp/workload.sh 0 "$DURATION"
docker exec -d volt-xdcr-b bash /tmp/workload.sh 1000000 "$DURATION"
sleep "$((DURATION + 10))"

echo ">> auditing XDCR dashboard (cluster A view: namespace=test-volt-a)"
python3 ../audit_dashboards.py --dir "$DASHBOARDS" --prometheus http://localhost:9090 \
    --namespace test-volt-a --show-empty "${@}" | grep -A40 "voltdb-xdcr.json" || true

echo
echo ">> Grafana: http://localhost:3000  (pick namespace test-volt-a or test-volt-b)"
echo ">> tear down with: docker compose down -v"
