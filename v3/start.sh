#!/bin/bash
# Start the wechat bridge supervisor (v3). Safe to re-run.
B="$(cd "$(dirname "$0")" && pwd)"
pkill -f "[s]upervisor\.py" 2>/dev/null
sleep 1
if [ -f "$B/NEED_RESCAN" ]; then
  echo "NEED_RESCAN exists, not starting (user must rescan)"
  exit 1
fi
cd "$B"
nohup python3 "$B/supervisor.py" >> supervisor.log 2>&1 &
echo "supervisor started, pid $!"
