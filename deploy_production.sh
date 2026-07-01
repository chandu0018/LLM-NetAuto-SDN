#!/bin/bash
# Production Deployment Script for LLM-NetAuto-SDN
# Deploy with real Mininet topology and production configuration

set -e

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║      LLM-NetAuto-SDN: Production Deployment with Real Mininet            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"

# Check if already running
check_running() {
    if pgrep -f "production_topology.py" > /dev/null; then
        echo -e "${YELLOW}⚠ Mininet topology already running${NC}"
        return 0
    fi
    return 1
}

# Verify prerequisites
verify_prerequisites() {
    echo -e "${YELLOW}▶ Verifying prerequisites...${NC}"

    # Check ONOS
    if ! curl -s --user onos:rocks http://localhost:8181/onos/v1/cluster > /dev/null 2>&1; then
        echo -e "${RED}✗ ONOS not running. Start ONOS first:${NC}"
        echo "   docker-compose up onos"
        return 1
    fi
    echo -e "${GREEN}✓ ONOS is running${NC}"

    # Check Mininet
    if ! command -v mn &> /dev/null; then
        echo -e "${RED}✗ Mininet not installed${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Mininet is available${NC}"

    # Check virtual environment
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${RED}✗ Virtual environment not found${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Virtual environment found${NC}"

    return 0
}

# Start production services
start_services() {
    echo ""
    echo -e "${YELLOW}▶ Starting LLM-NetAuto services...${NC}"

    # Create logs directory
    mkdir -p "$LOG_DIR"

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Start FastAPI
    echo -e "${YELLOW}  Starting FastAPI backend...${NC}"
    nohup uvicorn dashboard.api:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        > "$LOG_DIR/fastapi.log" 2>&1 &
    API_PID=$!
    echo -e "${GREEN}  ✓ FastAPI started (PID: $API_PID)${NC}"

    sleep 3

    # Start Streamlit
    echo -e "${YELLOW}  Starting Streamlit dashboard...${NC}"
    nohup streamlit run dashboard/app.py \
        --server.port 8501 \
        --server.address 0.0.0.0 \
        > "$LOG_DIR/streamlit.log" 2>&1 &
    STREAMLIT_PID=$!
    echo -e "${GREEN}  ✓ Streamlit started (PID: $STREAMLIT_PID)${NC}"

    sleep 3

    # Verify services
    echo ""
    echo -e "${YELLOW}▶ Verifying services...${NC}"

    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ FastAPI is responding${NC}"
    else
        echo -e "${RED}✗ FastAPI not responding${NC}"
        return 1
    fi

    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Streamlit is responding${NC}"
    else
        echo -e "${RED}✗ Streamlit not responding${NC}"
        return 1
    fi

    return 0
}

# Start Mininet topology
start_mininet() {
    echo ""
    echo -e "${YELLOW}▶ Starting Mininet topology...${NC}"

    # Clean up any previous Mininet state
    echo -e "${YELLOW}  Cleaning up previous state...${NC}"
    sudo mn -c 2>/dev/null || true
    sleep 2

    # Start topology in background
    echo -e "${YELLOW}  Starting production topology...${NC}"
    source "$VENV_DIR/bin/activate"
    nohup sudo python3 production_topology.py background \
        > "$LOG_DIR/mininet.log" 2>&1 &
    MININET_PID=$!

    echo -e "${GREEN}  ✓ Mininet started (PID: $MININET_PID)${NC}"

    # Wait for topology discovery
    echo -e "${YELLOW}  Waiting for ONOS topology discovery...${NC}"
    sleep 15

    # Verify topology
    DEVICES=$(curl -s --user onos:rocks http://localhost:8181/onos/v1/devices | \
        python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('devices', [])))" 2>/dev/null || echo "0")

    if [ "$DEVICES" -gt 0 ]; then
        echo -e "${GREEN}✓ ONOS discovered $DEVICES devices${NC}"
    else
        echo -e "${YELLOW}⚠ No devices discovered yet (topology discovery in progress)${NC}"
    fi

    return 0
}

# Display deployment summary
show_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════════╗"
    echo "║                   Deployment Successful! 🎉                               ║"
    echo "╚════════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}Services Running:${NC}"
    echo "  ✓ FastAPI Backend"
    echo "  ✓ Streamlit Dashboard"
    echo "  ✓ Mininet Network"
    echo ""
    echo -e "${GREEN}Access Points:${NC}"
    echo "  Dashboard:      http://localhost:8501"
    echo "  API:           http://localhost:8000"
    echo "  API Docs:      http://localhost:8000/docs"
    echo "  Grafana:       http://localhost:3000"
    echo "  Prometheus:    http://localhost:9090"
    echo "  ONOS GUI:      http://127.0.0.1:8181/onos/ui"
    echo ""
    echo -e "${GREEN}Next Steps:${NC}"
    echo "  1. Open Dashboard: http://localhost:8501"
    echo "  2. Go to 'Intent Control' page"
    echo "  3. Submit network intents in natural language"
    echo ""
    echo -e "${GREEN}Example Intents:${NC}"
    echo "  - 'Block all traffic from 10.0.0.1'"
    echo "  - 'Allow HTTP from h1 to h3'"
    echo "  - 'Isolate switch s2'"
    echo ""
    echo -e "${GREEN}Monitoring:${NC}"
    echo "  View topology:    http://127.0.0.1:8181/onos/ui/#!/topo"
    echo "  View flows:       http://127.0.0.1:8181/onos/ui/#!/flows"
    echo "  View intents:     http://127.0.0.1:8181/onos/ui/#!/intents"
    echo ""
    echo -e "${YELLOW}Logs:${NC}"
    echo "  FastAPI:  tail -f $LOG_DIR/fastapi.log"
    echo "  Streamlit: tail -f $LOG_DIR/streamlit.log"
    echo "  Mininet:   tail -f $LOG_DIR/mininet.log"
    echo ""
    echo -e "${YELLOW}Stop Deployment:${NC}"
    echo "  sudo mn -c"
    echo "  pkill -f 'uvicorn'"
    echo "  pkill -f 'streamlit'"
    echo ""
}

# Main deployment flow
main() {
    cd "$PROJECT_DIR"

    # Check prerequisites
    if ! verify_prerequisites; then
        echo -e "${RED}Prerequisites check failed${NC}"
        exit 1
    fi

    # Start services
    if ! start_services; then
        echo -e "${RED}Service startup failed${NC}"
        exit 1
    fi

    # Start Mininet
    if ! start_mininet; then
        echo -e "${RED}Mininet startup failed${NC}"
        exit 1
    fi

    # Show summary
    show_summary
}

# Run main
main
