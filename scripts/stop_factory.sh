#!/usr/bin/env bash
# Stop all factory agents. SIGTERM lets the SDK disconnect gracefully.
#
# Also sweeps strays by process pattern: a pid file only knows the LAST launch, and a
# surviving process keeps Band's single-instance lock, so the next start dies with
# AgentAlreadyRunningError. Observed 23 Nov.
cd "$(dirname "$0")/.."

for role in architect builder verifier gatekeeper; do
  f="runs/$role.pid"
  [ -f "$f" ] || continue
  pid=$(cat "$f")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" && echo "  stopped $role (pid $pid)"
  fi
  rm -f "$f"
done

# Sweep anything the pid files missed.
if pgrep -f 'agents\.run' >/dev/null 2>&1; then
  echo "  sweeping strays..."
  pkill -f 'agents\.run' 2>/dev/null
  sleep 2
  pkill -9 -f 'agents\.run' 2>/dev/null
fi

# Band refuses to start an agent whose lock is still held.
rm -f /tmp/band-agent-*.lock 2>/dev/null
echo "  all stopped, locks cleared"
