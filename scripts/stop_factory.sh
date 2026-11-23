#!/usr/bin/env bash
# Stop all factory agents. SIGTERM lets the SDK disconnect gracefully.
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
