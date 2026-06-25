#!/bin/zsh
cd "$(dirname "$0")"
python3 src/app_server.py &
SERVER_PID=$!
sleep 1
open http://127.0.0.1:8765
wait $SERVER_PID
