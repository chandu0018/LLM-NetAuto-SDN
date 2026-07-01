#!/bin/bash
# ============================================
# LLM-NetAuto-SDN Run Script
# ============================================
# This script starts the application components.
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default ports
FASTAPI_PORT=${FASTAPI_PORT:-8000}
STREAMLIT_PORT=${STREAMLIT_PORT:-8501}

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activate virtual environment if not active
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}Error: Virtual environment not found. Run setup.sh first.${NC}"
        exit 1
    fi
fi

# Function to start FastAPI
start_api() {
    echo -e "${BLUE}Starting FastAPI server on port $FASTAPI_PORT...${NC}"
    cd "$(dirname "$0")"
    uvicorn dashboard.api:app --host 0.0.0.0 --port $FASTAPI_PORT --reload &
    API_PID=$!
    echo -e "${GREEN}FastAPI started with PID $API_PID${NC}"
}

# Function to start Streamlit
start_dashboard() {
    echo -e "${BLUE}Starting Streamlit dashboard on port $STREAMLIT_PORT...${NC}"
    cd "$(dirname "$0")"
    streamlit run dashboard/app.py --server.port $STREAMLIT_PORT --server.address 0.0.0.0 &
    STREAMLIT_PID=$!
    echo -e "${GREEN}Streamlit started with PID $STREAMLIT_PID${NC}"
}

# Function to start Ollama
start_ollama() {
    if pgrep -x "ollama" > /dev/null 2>&1; then
        echo -e "${GREEN}Ollama already running${NC}"
    else
        echo -e "${BLUE}Starting Ollama...${NC}"
        ollama serve > logs/ollama.log 2>&1 &
        OLLAMA_PID=$!
        echo -e "${GREEN}Ollama started with PID $OLLAMA_PID${NC}"
        sleep 2
    fi
}

# Function to start Mininet (password from .env SUDO_PASSWORD)
start_mininet() {
    N_SWITCHES=${TOPO_SWITCHES:-3}
    HOSTS_PER_SWITCH=${TOPO_HOSTS_PER_SWITCH:-2}
    SUDO_PW=${SUDO_PASSWORD:-""}
    CTRL_IP=${ONOS_HOST:-127.0.0.1}
    CTRL_PORT=${ONOS_OF_PORT:-6653}

    echo -e "${BLUE}Starting Mininet (${N_SWITCHES} switches, ${HOSTS_PER_SWITCH} hosts/switch)...${NC}"

    # Clean up any existing state
    echo "$SUDO_PW" | sudo -S mn -c > /dev/null 2>&1 || true

    mkdir -p logs
    echo "$SUDO_PW" | sudo -S python3 topology/mininet_topo.py \
        --n-switches="$N_SWITCHES" \
        --hosts-per-switch="$HOSTS_PER_SWITCH" \
        --controller-ip="$CTRL_IP" \
        --controller-port="$CTRL_PORT" \
        --no-cli \
        > logs/mininet.log 2>&1 &
    MININET_PID=$!
    echo $MININET_PID > mininet.pid
    echo -e "${GREEN}Mininet started with PID $MININET_PID${NC}"
}

# Function to start both
start_both() {
    start_ollama
    start_api
    sleep 2  # Wait for API to start
    start_dashboard
    sleep 2
    start_mininet
}

# Function to show usage
show_usage() {
    echo "============================================"
    echo "  LLM-NetAuto-SDN Run Script"
    echo "============================================"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  api       - Start FastAPI backend only"
    echo "  dashboard - Start Streamlit dashboard only"
    echo "  both      - Start both services (default)"
    echo "  stop      - Stop all running services"
    echo "  status    - Show status of services"
    echo "  test      - Run test suite"
    echo "  benchmark - Run benchmark suite"
    echo "  help      - Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  DEMO_MODE      - true/false (default: true)"
    echo "  FASTAPI_PORT   - API port (default: 8000)"
    echo "  STREAMLIT_PORT - Dashboard port (default: 8501)"
    echo ""
    echo "============================================"
}

# Function to stop services
stop_services() {
    echo -e "${YELLOW}Stopping services...${NC}"

    pkill -f "uvicorn dashboard.api:app" 2>/dev/null && echo -e "${GREEN}Stopped FastAPI${NC}" || echo -e "${YELLOW}FastAPI not running${NC}"
    pkill -f "streamlit run dashboard/app.py" 2>/dev/null && echo -e "${GREEN}Stopped Streamlit${NC}" || echo -e "${YELLOW}Streamlit not running${NC}"
    pkill -f "ollama serve" 2>/dev/null && echo -e "${GREEN}Stopped Ollama${NC}" || echo -e "${YELLOW}Ollama not running${NC}"

    SUDO_PW=${SUDO_PASSWORD:-""}
    if [ -f mininet.pid ]; then
        MN_PID=$(cat mininet.pid)
        echo "$SUDO_PW" | sudo -S kill "$MN_PID" 2>/dev/null && echo -e "${GREEN}Stopped Mininet${NC}" || true
        rm -f mininet.pid
    fi
    echo "$SUDO_PW" | sudo -S mn -c > /dev/null 2>&1 || true

    echo -e "${GREEN}All services stopped.${NC}"
}

# Function to show status
show_status() {
    echo "============================================"
    echo "  Service Status"
    echo "============================================"

    if pgrep -f "uvicorn dashboard.api:app" > /dev/null; then
        echo -e "${GREEN}✓ FastAPI is running${NC}"
        echo "  URL: http://localhost:$FASTAPI_PORT"
    else
        echo -e "${RED}✗ FastAPI is not running${NC}"
    fi

    if pgrep -f "streamlit run dashboard/app.py" > /dev/null; then
        echo -e "${GREEN}✓ Streamlit is running${NC}"
        echo "  URL: http://localhost:$STREAMLIT_PORT"
    else
        echo -e "${RED}✗ Streamlit is not running${NC}"
    fi

    if pgrep -x "ollama" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Ollama is running${NC}"
    else
        echo -e "${RED}✗ Ollama is not running${NC}"
    fi

    if [ -f mininet.pid ] && kill -0 "$(cat mininet.pid)" 2>/dev/null; then
        echo -e "${GREEN}✓ Mininet is running (PID $(cat mininet.pid))${NC}"
    else
        echo -e "${RED}✗ Mininet is not running${NC}"
    fi

    echo ""
    echo "Mode: LIVE"
    echo "Switches: ${TOPO_SWITCHES:-3}, Hosts/Switch: ${TOPO_HOSTS_PER_SWITCH:-2}"
    echo "============================================"
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}Running test suite...${NC}"
    pytest tests/ -v --tb=short
}

# Function to run benchmark
run_benchmark() {
    echo -e "${BLUE}Running benchmark...${NC}"
    python3 benchmark.py
}

# Main script
case "${1:-both}" in
    api)
        start_api
        wait
        ;;
    dashboard)
        start_dashboard
        wait
        ;;
    both)
        echo "============================================"
        echo -e "${GREEN}  LLM-NetAuto-SDN (Live Mode)${NC}"
        echo "============================================"
        echo ""
        start_both
        echo ""
        echo "============================================"
        echo "  All Services Started!"
        echo "============================================"
        echo ""
        echo "FastAPI:    http://localhost:$FASTAPI_PORT"
        echo "API Docs:   http://localhost:$FASTAPI_PORT/docs"
        echo "Dashboard:  http://localhost:$STREAMLIT_PORT"
        echo "Mininet:    $(cat mininet.pid 2>/dev/null | xargs -I{} echo 'PID {}' || echo 'starting...')"
        echo ""
        echo "Press Ctrl+C to stop all services."
        echo "============================================"
        wait
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    test)
        run_tests
        ;;
    benchmark)
        run_benchmark
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_usage
        exit 1
        ;;
esac
