#!/usr/bin/env bash
# Drives writes on this cluster. Arg1: id base (so the two clusters write mostly
# disjoint key ranges), arg2: duration (s). A few low ids are written on both
# sides on purpose to generate DR conflicts.
set -euo pipefail
BASE="${1:-0}"
DURATION="${2:-90}"
SQLCMD=/opt/voltdb/bin/sqlcmd

end=$(( $(date +%s) + DURATION ))
i=0
while [ "$(date +%s)" -lt "$end" ]; do
  i=$(( i + 1 ))
  id=$(( BASE + i ))
  cat <<SQL | $SQLCMD >/dev/null 2>&1 || true
UPSERT INTO events (id, ts, val) VALUES ($id, NOW, 'base$BASE-$i');
UPSERT INTO refdata (k, v) VALUES ('k$(( i % 20 ))', 'v$i');
-- deliberate conflict: both clusters write the same low ids
UPSERT INTO events (id, ts, val) VALUES ($(( i % 5 )), NOW, 'conflict-from-$BASE');
SQL
done
echo "workload(base=$BASE): $i iterations"
