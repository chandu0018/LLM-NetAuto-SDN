#!/bin/bash
# ============================================
# LLM-NetAuto-SDN Setup Script
# ============================================
# This script sets up the development environment
# for LLM-Based Network Automation with Real-Time
# Monitoring in Software-Defined Networking.
# ============================================

set -e

echo "============================================"
echo "  LLM-NetAuto-SDN Setup Script"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$PYTHON_VERSION" != "3.10" && "$PYTHON_VERSION" != "3.11" ]]; then
    echo -e "${YELLOW}Warning: Python $PYTHON_VERSION detected. Recommended: Python 3.10${NC}"
fi
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

# Create virtual environment
echo ""
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment created.${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
fi

# Activate virtual environment
echo ""
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}Virtual environment activated.${NC}"

# Upgrade pip
echo ""
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo ""
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create .env file if it doesn't exist
echo ""
echo -e "${YELLOW}Setting up environment configuration...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}.env file created from .env.example${NC}"
    echo -e "${YELLOW}Please edit .env to configure your environment.${NC}"
else
    echo -e "${YELLOW}.env file already exists.${NC}"
fi

# Create data directories
echo ""
echo -e "${YELLOW}Creating data directories...${NC}"
mkdir -p data
mkdir -p logs
mkdir -p chromadb_data
echo -e "${GREEN}Data directories created.${NC}"

# Verify imports
echo ""
echo -e "${YELLOW}Verifying module imports...${NC}"
python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from llm import IntentParser, RAGEngine, PromptTemplates
    print('  ✓ LLM module')
except ImportError as e:
    print(f'  ✗ LLM module: {e}')

try:
    from netconfig import FlowBuilder, IntentBuilder
    print('  ✓ Netconfig module')
except ImportError as e:
    print(f'  ✗ Netconfig module: {e}')

try:
    from monitoring import AnomalyDetector, TelemetryCollector, FeedbackLoop
    print('  ✓ Monitoring module')
except ImportError as e:
    print(f'  ✗ Monitoring module: {e}')

try:
    from simulation import SimulationEngine
    print('  ✓ Simulation module')
except ImportError as e:
    print(f'  ✗ Simulation module: {e}')

try:
    from controller import ONOSClient, TopologyManager
    print('  ✓ Controller module')
except ImportError as e:
    print(f'  ✗ Controller module: {e}')

try:
    from comparison import Benchmark, TraditionalConfigManager
    print('  ✓ Comparison module')
except ImportError as e:
    print(f'  ✗ Comparison module: {e}')

try:
    from topology import SimulatedTopology, TopologySeed
    print('  ✓ Topology module')
except ImportError as e:
    print(f'  ✗ Topology module: {e}')

print('')
print('Import verification complete!')
"

# Seed topology data
echo ""
echo -e "${YELLOW}Seeding topology data...${NC}"
python3 -c "
from topology.topology_seed import seed_topology
try:
    seed_topology()
    print('Topology seeding complete!')
except Exception as e:
    print(f'Warning: Topology seeding skipped: {e}')
" 2>/dev/null || echo -e "${YELLOW}Topology seeding skipped (will run on first use).${NC}"

# Print completion message
echo ""
echo "============================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "============================================"
echo ""
echo "To start the application:"
echo ""
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Run the application:"
echo "     ./run.sh"
echo ""
echo "  Or run components individually:"
echo "     ./run.sh api       # FastAPI only"
echo "     ./run.sh dashboard # Streamlit only"
echo "     ./run.sh both      # Both services"
echo ""
echo "For Docker deployment:"
echo "     docker-compose up -d"
echo ""
echo "============================================"
