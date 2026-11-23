#!/usr/bin/env bash
# Start all four factory agents as background processes, one log each.
# Each role is its own process: BAND permits only one live WebSocket per agent.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runs
PY=.venv/bin/python

for role in architect builder verifier gatekeeper; do
  if [ -f "runs/$role.pid" ] && kill -0 "$(cat "runs/$role.pid")" 2>/dev/null; then
    echo "  $role already running (pid $(cat "runs/$role.pid"))"
    continue
  fi
  nohup $PY -u -m agents.run "$role" > "runs/$role.log" 2>&1 &
  echo $! > "runs/$role.pid"
  echo "  started $role (pid $!)"
done

echo
echo "waiting for all four to join the room..."
for i in $(seq 1 30); do
  joined=$(grep -l "Agent started:" runs/*.log 2>/dev/null | wc -l)
  [ "$joined" -ge 4 ] && break
  sleep 1
done
grep -h "Agent started:" runs/*.log 2>/dev/null | sed 's/^/  /' || echo "  (none reported yet)"
