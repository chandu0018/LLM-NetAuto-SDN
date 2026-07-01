# LLM-NetAuto-SDN: Production Deployment Guide

## Overview

This guide provides complete instructions for deploying LLM-NetAuto-SDN with a real Mininet topology in a production environment.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Production Deployment                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────┐       │
│  │     Mininet Network (OpenFlow 1.3)               │       │
│  │  ┌────┐                      ┌────┐              │       │
│  │  │ h1 │                      │ h6 │              │       │
│  │  └─┬──┘                      └──┬─┘              │       │
│  │    │  ┌────┐      ┌────┐      ┌────┐            │       │
│  │  ┌────┤ s1 ├──────┤ s2 ├──────┤ s3 ├────┐       │       │
│  │  │    └────┘      └────┘      └────┘     │       │       │
│  │  │  ┌────┐      ┌────┐      ┌────┐       │       │       │
│  │  ├──┤ h2 │  h3  │ h4 │ h5  │ h6 │       │       │       │
│  │  │  └────┘      └────┘      └────┘       │       │       │
│  │  │                                        │       │       │
│  └──┼────────────────────────────────────────┼───────┘       │
│     │                                        │               │
│  ┌──▼──────────────────────────────────────┐ │               │
│  │     ONOS SDN Controller                 │ │               │
│  │  (OpenFlow 1.3 Support)                 │ │               │
│  └─────────────────────────┬────────────────┘ │               │
│                            │                  │               │
│  ┌────────────────────────▼──────────────────────────┐       │
│  │          LLM-NetAuto Backend (FastAPI)           │       │
│  │  ┌──────────┐  ┌─────────────┐  ┌────────────┐  │       │
│  │  │LLM Parser│  │RAG Engine   │  │Flow Builder│  │       │
│  │  │(Ollama)  │  │(ChromaDB)   │  │(OpenFlow)  │  │       │
│  │  └──────────┘  └─────────────┘  └────────────┘  │       │
│  └────────────────────────┬──────────────────────────┘       │
│                            │                                  │
│  ┌────────────────────────▼──────────────────────────┐       │
│  │    Streamlit Dashboard (HTTP/WebSocket)           │       │
│  │  ┌────────┐ ┌─────────┐ ┌────────────┐            │       │
│  │  │ Intent │ │Topology │ │Monitoring  │            │       │
│  │  │Control │ │Viewer   │ │            │            │       │
│  │  └────────┘ └─────────┘ └────────────┘            │       │
│  └─────────────────────────────────────────────────────┘      │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  Prometheus      │  │   Grafana        │                │
│  │  (Metrics)       │  │   (Dashboards)   │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### System Requirements
- Linux (Ubuntu 20.04 LTS or later)
- 8GB RAM minimum (16GB recommended)
- 50GB disk space
- Root/sudo access
- Python 3.8+

### Required Software
```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    build-essential \
    git \
    mininet \
    openvswitch-switch \
    curl \
    jq
```

### Docker Services Running
```bash
# ONOS Controller
docker-compose up onos -d

# ChromaDB Vector DB
docker-compose up chromadb -d

# Ollama LLM Runtime
docker-compose up ollama -d

# Prometheus & Grafana (Optional)
docker-compose up prometheus grafana -d
```

---

## Deployment Steps

### 1. Verify Services

Check that all required services are running:

```bash
# Check ONOS
curl --user onos:rocks http://localhost:8181/onos/v1/cluster | jq

# Check ChromaDB
curl http://localhost:8001/api/v2/heartbeat | jq

# Check Ollama
curl http://localhost:11434/api/tags | jq

# Check project
cd /home/chandu/Desktop/llm-netauto-sdn
```

### 2. Set Production Configuration

Edit `.env` for production settings:

```bash
# Switch to live mode (not demo)
DEMO_MODE=false

# ONOS Configuration
ONOS_HOST=127.0.0.1
ONOS_PORT=8181
ONOS_OF_PORT=6653

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 3. Deploy with Production Script

```bash
# Run automated deployment
cd /home/chandu/Desktop/llm-netauto-sdn
./deploy_production.sh
```

This script will:
1. ✓ Verify all prerequisites
2. ✓ Start FastAPI backend
3. ✓ Start Streamlit dashboard
4. ✓ Start real Mininet topology
5. ✓ Verify topology discovery in ONOS
6. ✓ Display access points and monitoring instructions

### 4. Manual Deployment (Alternative)

If you prefer manual control:

```bash
# Terminal 1: Start FastAPI
source venv/bin/activate
uvicorn dashboard.api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start Streamlit
source venv/bin/activate
streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0

# Terminal 3: Start Mininet
sudo python3 production_topology.py
```

---

## Accessing the System

### Web Interfaces

| Service | URL | Purpose |
|---------|-----|---------|
| Dashboard | http://localhost:8501 | Main UI for intent submission |
| API Docs | http://localhost:8000/docs | Interactive API testing |
| ONOS GUI | http://127.0.0.1:8181/onos/ui | Network visualization |
| Grafana | http://localhost:3000 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics queries |

### Command Line

```bash
# Test intent submission
curl -X POST http://localhost:8000/intent \
  -H "Content-Type: application/json" \
  -d '{"intent": "Block all traffic from 10.0.0.1"}'

# Get topology
curl http://localhost:8000/topology | jq

# Get all intents
curl http://localhost:8000/intents | jq

# Get ONOS devices
curl --user onos:rocks http://localhost:8181/onos/v1/devices | jq
```

---

## Testing Intent Deployment

### Example 1: Block Traffic

```bash
Intent: "Block all traffic from 10.0.0.1"

Expected:
- LLM parses intent to block rule
- System generates OpenFlow rule
- Rule deployed to switches
- Traffic from 10.0.0.1 blocked
```

### Example 2: Allow Specific Traffic

```bash
Intent: "Allow HTTP traffic from h1 to h3"

Expected:
- LLM parses as allow rule
- Identifies source/destination IPs
- Creates TCP port 80 rule
- Deployed to appropriate switches
```

### Example 3: QoS/Prioritization

```bash
Intent: "Prioritize VoIP traffic on UDP port 5060"

Expected:
- Identifies UDP protocol and port
- Sets high priority (60000)
- Applied to backbone switches
```

---

## Monitoring

### Real-time Logs

```bash
# FastAPI logs
tail -f logs/fastapi.log

# Streamlit logs
tail -f logs/streamlit.log

# Mininet topology logs
tail -f logs/mininet.log
```

### Network State

```bash
# Check ONOS cluster
curl --user onos:rocks http://localhost:8181/onos/v1/cluster | jq '.nodes | length'

# Check discovered devices
curl --user onos:rocks http://localhost:8181/onos/v1/devices | jq '.devices | length'

# Check installed intents
curl --user onos:rocks http://localhost:8181/onos/v1/intents | jq '.intents | length'

# Check flow rules
curl --user onos:rocks http://localhost:8181/onos/v1/flows | jq '.flows | length'
```

### System Health

```bash
# Backend health
curl http://localhost:8000/health | jq

# Service connectivity
curl http://localhost:8000/metrics/summary | jq

# RAG engine stats
curl http://localhost:8000/rag/stats | jq
```

---

## Troubleshooting

### ONOS Not Discovering Switches

```bash
# Check ONOS OpenFlow port
netstat -tlnp | grep 6653

# Verify Mininet switches reaching ONOS
sudo mn -c
nohup sudo python3 production_topology.py background > logs/mininet.log 2>&1 &
tail -f logs/mininet.log

# Check ONOS OpenFlow listener
curl --user onos:rocks http://localhost:8181/onos/v1/devices | jq '.devices'
```

### Intent Deployment Fails

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags | jq '.models'

# Check ChromaDB connectivity
curl http://localhost:8001/api/v2/heartbeat | jq

# Verify FastAPI logs
tail -f logs/fastapi.log | grep -i error
```

### High Latency

```bash
# Check API response time
time curl http://localhost:8000/health

# Profile Ollama inference
# Monitor GPU usage:
watch -n1 'nvidia-smi'

# Check system resources
top
```

---

## Production Best Practices

### 1. Monitoring & Alerting
- Set up Prometheus alerts for service failures
- Configure Grafana dashboards for intent processing metrics
- Monitor ONOS performance metrics

### 2. Logging
- Enable structured logging
- Archive logs daily
- Set retention policies

### 3. Backups
- Backup ChromaDB vector database
- Backup ONOS configuration
- Backup Prometheus time-series database

### 4. Security
- Use HTTPS in production
- Implement API authentication
- Enable network isolation

### 5. Scaling
- Use Docker Compose for multi-host deployment
- Enable load balancing for dashboard
- Consider Ollama GPU acceleration

### 6. Performance Tuning
```bash
# Increase open file limits
ulimit -n 65536

# Tune network parameters
sysctl -w net.ipv4.tcp_nodelay=1
sysctl -w net.core.somaxconn=4096

# Optimize Ollama GPU
export OLLAMA_NUM_GPU=1  # Use GPU if available
```

---

## Shutdown & Cleanup

### Graceful Shutdown

```bash
# Stop Mininet
sudo mn -c

# Stop services
pkill -f uvicorn
pkill -f streamlit

# Verify all processes stopped
ps aux | grep -E "(uvicorn|streamlit|mininet)" | grep -v grep
```

### Full Cleanup

```bash
# Remove all Mininet artifacts
sudo mn -c
sudo ovs-vsctl del-br br-int 2>/dev/null || true

# Clear logs
rm -f logs/*.log

# Stop Docker services
docker-compose down
```

---

## Performance Metrics

### Expected Performance

| Metric | Value |
|--------|-------|
| LLM Intent Latency | 3-12 seconds |
| Intent Deployment Time | < 1 second |
| ONOS Topology Discovery | 10-15 seconds |
| API Response Time | ~ 50-100ms |
| Dashboard Load Time | ~ 2-3 seconds |
| Mininet Network Startup | ~ 20-30 seconds |

### Optimization Tips

1. **Reduce LLM Latency**
   - Use quantized models (4-bit)
   - Enable GPU acceleration
   - Increase Ollama thread count

2. **Improve Topology Discovery**
   - Tune ONOS OpenFlow timeouts
   - Increase hello interval
   - Check controller CPU utilization

3. **Optimize Dashboard**
   - Enable Streamlit caching
   - Reduce refresh rate
   - Compress data transfers

---

## Docker Deployment (Optional)

For containerized deployment:

```bash
# Build custom images (if needed)
docker build -t llm-netauto-backend -f Dockerfile.backend .
docker build -t llm-netauto-dashboard -f Dockerfile.dashboard .

# Deploy with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## Support & Debugging

### Useful Commands

```bash
# Get system info
uname -a
python3 --version
pip freeze | grep -E "(fastapi|streamlit|requests)"

# Network diagnostics
ifconfig
iptables -L -n
route -n

# ONOS diagnostics
curl --user onos:rocks -s http://localhost:8181/onos/v1/apps | jq '.apps[] | select(.state=="ACTIVE")'

# Mininet diagnostics
sudo ovs-vsctl list-br
sudo ovs-vsctl list-ports br0
```

---

## Next Steps

1. **Deploy the system** using `./deploy_production.sh`
2. **Open the dashboard** at http://localhost:8501
3. **Test with example intents** from the dashboard
4. **Monitor ONOS topology** at http://127.0.0.1:8181/onos/ui
5. **Check metrics** in Grafana

---

## Production Checklist

- [ ] All prerequisites installed
- [ ] All Docker services running
- [ ] ONOS cluster healthy
- [ ] Mininet topology created
- [ ] FastAPI responding
- [ ] Streamlit accessible
- [ ] Intent submission working
- [ ] ONOS discovering switches
- [ ] Intents deploying to switches
- [ ] Metrics being collected
- [ ] Logs being maintained
- [ ] Backups configured
- [ ] Monitoring alerts configured

---

*Last Updated: 2026-04-06*
*Version: 1.0.0*
