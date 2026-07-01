# LLM-NetAuto-SDN: How to Run the Project

Welcome to the **LLM-NetAuto-SDN** (Live Dynamic Network Topology & Intent Control) workspace! The project has been fully transitioned to a **Live-Only production mode**, featuring dynamic ring topology generation and seamless controller-integrated execution.

---

## 🏗️ System Architecture & Services

The application consists of four main components running in harmony:
1. **Ollama LLM**: Parses natural language intents (e.g., *“block all UDP traffic from host 1 to host 3”*) into structured network intent rules using localized models.
2. **FastAPI Backend (`dashboard/api.py`)**: The central control server that interfaces with the ONOS controller, updates RAG embeddings in ChromaDB, handles topology scaling, and triggers network remediation.
3. **Streamlit Dashboard (`dashboard/app.py`)**: A modern UI for visualizing the live topology graph, configuring network size, monitoring flow rules, and submitting control intents.
4. **Mininet Network Topology (`topology/mininet_topo.py`)**: Generates and simulates a dynamic OpenFlow 1.3 ring topology of arbitrary size ($N$ switches, $M$ hosts/switch) connected to the local ONOS controller.

---

## ⚙️ Configuration (`.env`)

All core system configurations are stored in the `.env` file at the root of the project.
Make sure the following variables are configured:

```env
# Network Controller Details
ONOS_HOST=127.0.0.1
ONOS_PORT=8181
ONOS_OF_PORT=6653
ONOS_USER=onos
ONOS_PASSWORD=rocks

# Dashboard API Settings
FASTAPI_PORT=8000
STREAMLIT_PORT=8501

# Dynamic Topology Settings
TOPO_SWITCHES=3             # Number of switches (2 to 8)
TOPO_HOSTS_PER_SWITCH=2     # Number of hosts per switch (1 to 4)
SUDO_PASSWORD=Admin         # Sudo password used to launch Mininet automatically
```

---

## 🚀 Step 1: Starting the Entire Project

We have built a unified and fully-automated startup script `run.sh` that takes care of everything (Ollama, FastAPI, Streamlit, and Mininet) sequentially.

Simply run the following command in your terminal:
```bash
./run.sh both
```
Or just:
```bash
./run.sh
```

### What this script does automatically:
1. **Starts Ollama** in the background (if not already running) to load the local LLM (`llama3.2:1b`).
2. **Activates the Python virtual environment** (`venv/bin/activate`).
3. **Launches the FastAPI backend** on port `8000`.
4. **Launches the Streamlit Dashboard** on port `8501`.
5. **Launches the Mininet Network Topology** (in background daemon mode using `SUDO_PASSWORD=Admin` from `.env`) and automatically connects it to your ONOS controller.
6. **Seeds the ChromaDB vector database** dynamically with your active network switches, hosts, and paths to optimize RAG parsing.

---

## ⚙️ Step 2: Dynamic Topology Customization

You can change the size of the network topology programmatically or directly inside the dashboard UI without requiring manual CLI restarts or terminal access.

### Method A: Via the Web Dashboard (No Sudo Required!)
1. Open the dashboard in your browser: **`http://localhost:8501`**
2. Click **Network Topology** in the left sidebar navigation.
3. Expand the **⚙️ Configure Topology (Switches & Hosts)** panel at the top.
4. Adjust the sliders to your desired scale (e.g., 4 switches, 3 hosts/switch).
5. Click **🚀 Apply & Launch Mininet**.
   - The FastAPI backend will automatically stop the old Mininet, generate the new OpenFlow ring topology, restart the virtual switches, connect them to ONOS, and re-seed ChromaDB with the new layout in the background.

### Method B: Via CLI Arguments
If you prefer starting Mininet manually in a separate terminal:
```bash
sudo ./start_mininet.sh --n-switches 4 --hosts-per-switch 3
```
Or directly via the Python file:
```bash
sudo python3 topology/mininet_topo.py --n-switches 4 --hosts-per-switch 3 --no-cli
```

---

## 🔍 Step 3: Verifying the Network State

Once started, you can run a quick status summary of all services:
```bash
./run.sh status
```

**Example Status Output:**
```text
============================================
  Service Status
============================================
✓ FastAPI is running
  URL: http://localhost:8000
✓ Streamlit is running
  URL: http://localhost:8501
✓ Ollama is running
✓ Mininet is running (PID 8960)

Mode: LIVE
Switches: 3, Hosts/Switch: 2
============================================
```

> [!TIP]
> **Why are hosts showing as 0?**
> In a live ONOS environment, hosts are only discovered once they send their first packet. Open the Mininet CLI or run a pingall to generate traffic, and ONOS will instantly register all hosts and draw them on the **Network Topology** graph!
> To do this manually inside the Mininet process:
> ```bash
> sudo mn -c
> sudo python3 topology/mininet_topo.py
> mininet> pingall
> ```

---

## 🛑 Stopping the Services

To shut down all background processes (FastAPI, Streamlit, Ollama, and Mininet) and clean up OpenFlow virtual switches:
```bash
./run.sh stop
```
This safely terminates processes and runs `sudo mn -c` to reset virtual bridges.
