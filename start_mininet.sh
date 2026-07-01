#!/bin/bash
# ============================================================
# Start Mininet topology for LLM-NetAuto-SDN
# Reads switch/host counts from .env (or overrides via args).
#
# Usage:
#   sudo ./start_mininet.sh                      # use .env defaults
#   sudo ./start_mininet.sh --n-switches 4 --hosts-per-switch 3
# ============================================================

set -e

# Load .env if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

# Defaults (overridden by CLI flags or .env)
N_SWITCHES=${TOPO_SWITCHES:-3}
HOSTS_PER_SWITCH=${TOPO_HOSTS_PER_SWITCH:-2}
CONTROLLER_IP=${ONOS_HOST:-127.0.0.1}
CONTROLLER_PORT=${ONOS_OF_PORT:-6653}

# Parse optional CLI overrides
while [[ $# -gt 0 ]]; do
    case "$1" in
        --n-switches)       N_SWITCHES="$2";       shift 2 ;;
        --hosts-per-switch) HOSTS_PER_SWITCH="$2"; shift 2 ;;
        --controller-ip)    CONTROLLER_IP="$2";    shift 2 ;;
        --controller-port)  CONTROLLER_PORT="$2";  shift 2 ;;
        *) echo "Unknown arg: $1"; shift ;;
    esac
done

TOTAL_HOSTS=$(( N_SWITCHES * HOSTS_PER_SWITCH ))

echo "============================================="
echo "  LLM-NetAuto-SDN  — Starting Mininet"
echo "============================================="
echo "  Switches         : $N_SWITCHES"
echo "  Hosts/Switch     : $HOSTS_PER_SWITCH"
echo "  Total Hosts      : $TOTAL_HOSTS"
echo "  Controller       : $CONTROLLER_IP:$CONTROLLER_PORT"
echo "============================================="
echo ""

# Clean up any existing Mininet state
echo "Cleaning previous Mininet state..."
sudo mn -c > /dev/null 2>&1 || true

# Launch topology in background
nohup sudo python3 topology/mininet_topo.py \
    --n-switches="$N_SWITCHES" \
    --hosts-per-switch="$HOSTS_PER_SWITCH" \
    --controller-ip="$CONTROLLER_IP" \
    --controller-port="$CONTROLLER_PORT" \
    --no-cli \
    > logs/mininet.log 2>&1 &
MININET_PID=$!
echo $MININET_PID > mininet.pid

echo "Mininet started with PID: $MININET_PID"
echo "Waiting for ONOS topology discovery (up to 60s)..."
echo ""

# Wait for devices to appear in the API
DEVICES=0
for i in {1..30}; do
    sleep 2
    DEVICES=$(curl -s http://localhost:8000/devices 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('devices', [])))" \
        2>/dev/null || echo "0")

    if [ "$DEVICES" -gt 0 ]; then
        HOSTS=$(curl -s http://localhost:8000/hosts 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('hosts', [])))" \
            2>/dev/null || echo "0")
        LINKS=$(curl -s http://localhost:8000/links 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('links', [])))" \
            2>/dev/null || echo "0")

        echo ""
        echo "============================================="
        echo "  Topology Discovered!"
        echo "============================================="
        echo "  PID       : $MININET_PID"
        echo "  Switches  : $DEVICES"
        echo "  Hosts     : $HOSTS"
        echo "  Links     : $LINKS"
        echo "  Log       : logs/mininet.log"
        echo ""
        echo "To stop: sudo kill $MININET_PID && sudo mn -c"
        echo "============================================="
        exit 0
    else
        echo "⏳ Waiting for topology discovery... (attempt $i/30)"
    fi
done

echo ""
echo "❌ Topology discovery timeout after 60 seconds."
echo "   Check logs/mininet.log for details."
echo "   Make sure ONOS is running and listening on $CONTROLLER_IP:$CONTROLLER_PORT"
sudo kill $MININET_PID 2>/dev/null || true
exit 1