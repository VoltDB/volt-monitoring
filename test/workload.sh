#!/usr/bin/env bash
# Drives load against the test cluster so the dashboards have data to show.
# Runs inside the voltdb container via `docker exec`. Argument: duration (s).
set -euo pipefail
DURATION="${1:-90}"
SQLCMD=/opt/voltdb/bin/sqlcmd
VOLTADMIN=/opt/voltdb/bin/voltadmin

end=$(( $(date +%s) + DURATION ))
i=0
saved=0
while [ "$(date +%s)" -lt "$end" ]; do
  i=$(( i + 1 ))
  cat <<SQL | $SQLCMD >/dev/null 2>&1 || true
EXEC record_event $i 'cat$(( i % 5 ))' 'payload-$i';
INSERT INTO sessions (session_id, created, data) VALUES ($i, NOW, 'sess-$i');
UPSERT INTO config (k, v) VALUES ('counter', '$i');
SELECT COUNT(*) FROM events;
SELECT category, COUNT(*) FROM events GROUP BY category;
SQL
  # Trigger one manual snapshot partway through to populate snapshot metrics.
  if [ "$saved" -eq 0 ] && [ "$(date +%s)" -gt $(( end - DURATION/2 )) ]; then
    $VOLTADMIN save --blocking >/dev/null 2>&1 || true
    saved=1
  fi
done
echo "workload: $i iterations"
