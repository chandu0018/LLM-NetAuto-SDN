"""
Streamlit Dashboard for LLM-NetAuto-SDN.

Main entry point for the multi-page dashboard.
"""

import os
import sys
import requests
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


# ==========================================
# Configuration
# ==========================================

API_URL = f"http://127.0.0.1:{os.getenv('FASTAPI_PORT', '8000')}"


# ==========================================
# Helper Functions
# ==========================================

def api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make API request to backend."""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            return {"error": f"Unknown method: {method}"}

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Backend not running. Start with: python -m dashboard.api"}
    except requests.exceptions.Timeout:
        return {"error": "Request timeout"}
    except Exception as e:
        return {"error": str(e)}


def check_backend_health() -> bool:
    """Check if backend is healthy."""
    result = api_request("/health")
    return "error" not in result


def get_service_status() -> dict:
    """Get status of all services."""
    status = {
        "backend": False,
        "onos": False,
        "ollama": False,
        "chromadb": False
    }

    # Check backend
    result = api_request("/health")
    if "error" not in result:
        status["backend"] = True

    # Check actual services (live-only)
    try:
        r = requests.get(
            f"http://127.0.0.1:{os.getenv('ONOS_PORT', '8181')}/onos/v1/cluster",
            auth=('onos', 'rocks'),
            timeout=2
        )
        status["onos"] = r.status_code == 200
    except:
        pass

    try:
        r = requests.get(
            f"{os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')}/api/tags",
            timeout=2
        )
        status["ollama"] = r.status_code == 200
    except:
        pass

    try:
        r = requests.get(
            f"http://127.0.0.1:{os.getenv('CHROMADB_PORT', '8001')}/api/v2/heartbeat",
            timeout=2
        )
        status["chromadb"] = r.status_code == 200
    except:
        pass

    return status


# ==========================================
# Page Configuration
# ==========================================

st.set_page_config(
    page_title="LLM-NetAuto SDN",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# Custom CSS
# ==========================================

st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1rem;
    }

    /* Status indicators */
    .status-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-green { background-color: #4CAF50; }
    .status-red { background-color: #F44336; }
    .status-yellow { background-color: #FFC107; }

    /* Mode badge */
    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .mode-demo { background-color: #FFF3E0; color: #E65100; }
    .mode-live { background-color: #E8F5E9; color: #2E7D32; }

    /* Remove default streamlit padding */
    .block-container {
        padding-top: 2rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# Sidebar
# ==========================================

with st.sidebar:
    # Logo and Title
    st.markdown(
        '<div class="main-header">🌐 LLM-NetAuto</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-header">Intelligent SDN Control Center</div>',
        unsafe_allow_html=True
    )

    st.divider()

    # Mode Badge
    st.markdown(
        '<span class="mode-badge mode-live">🟢 LIVE MODE</span>',
        unsafe_allow_html=True
    )

    st.divider()

    # Service Status
    st.subheader("Service Status")

    status = get_service_status()

    for service, healthy in status.items():
        color = "green" if healthy else "red"
        dot = f'<span class="status-dot status-{color}"></span>'
        st.markdown(
            f'{dot} **{service.upper()}**: {"Connected" if healthy else "Offline"}',
            unsafe_allow_html=True
        )

    st.divider()

    # Last Updated
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Manual refresh
    if st.button("🔄 Refresh Status"):
        st.rerun()




# ==========================================
# Main Content
# ==========================================

# Live-only mode

# Backend connection check
if not check_backend_health():
    st.error(
        "❌ **Backend Not Running**\n\n"
        "Please start the FastAPI backend:\n"
        "```bash\n"
        "cd llm-netauto-sdn\n"
        "source venv/bin/activate\n"
        "python -m dashboard.api\n"
        "```"
    )
    st.stop()

# Welcome message
st.title("🌐 LLM-NetAuto-SDN Dashboard")
st.markdown("""
Welcome to the **LLM-Based Network Automation with Real-Time Monitoring** dashboard.

Use the sidebar to navigate between pages:

| Page | Description |
|------|-------------|
| **Intent Control** | Submit natural language intents to configure the network |
| **Network Topology** | Visualize the current network topology |
| **Flow Manager** | View and manage flow rules and intents |
| **Realtime Monitor** | Monitor network telemetry and anomalies |
| **System Health** | Check system status and run benchmarks |
| **Comparison** | Compare traditional vs LLM-based configuration |
""")

st.divider()

# Quick Stats
st.subheader("Quick Overview")

col1, col2, col3, col4 = st.columns(4)

# Get topology summary
topo = api_request("/topology")
if "error" not in topo:
    all_devices = topo.get("devices", [])
    all_hosts = topo.get("hosts", [])
    all_links = topo.get("links", [])

    # Filter to only AVAILABLE (live) devices so stale ONOS cache entries are hidden
    devices = [d for d in all_devices if d.get("available", False)]
    available_ids = {d.get("id") for d in devices}

    # Filter hosts: only keep hosts connected to an available switch
    hosts = [
        h for h in all_hosts
        if any(
            loc.get("elementId") in available_ids
            for loc in h.get("locations", [])
        )
    ]

    # Filter links: only keep links where BOTH endpoints are available
    links = [
        l for l in all_links
        if l.get("src", {}).get("device") in available_ids
        and l.get("dst", {}).get("device") in available_ids
    ]

    # Deduplicate links (ONOS reports each link in both directions)
    seen_link_pairs = set()
    unique_link_count = 0
    for l in links:
        pair = tuple(sorted([l.get("src", {}).get("device", ""), l.get("dst", {}).get("device", "")]))
        if pair not in seen_link_pairs:
            seen_link_pairs.add(pair)
            unique_link_count += 1

    with col1:
        st.metric("Switches", len(devices))

    with col2:
        st.metric("Hosts", len(hosts))

    with col3:
        st.metric("Links", unique_link_count)

    # Get flows - only count flows on available devices
    flows_resp = api_request("/flows")
    if "error" not in flows_resp:
        all_flows = flows_resp.get("flows", [])
        live_flows = [f for f in all_flows if f.get("deviceId") in available_ids]
        with col4:
            st.metric("Flow Rules", len(live_flows))

st.divider()

# Recent Activity
col1, col2 = st.columns(2)

with col1:
    st.subheader("Recent Anomalies")
    anomalies = api_request("/anomalies")
    if "error" not in anomalies:
        history = anomalies.get("history", [])[-5:]
        if history:
            for a in reversed(history):
                st.markdown(
                    f"- **{a.get('device_id', 'unknown')}**: "
                    f"{a.get('type', 'unknown')} "
                    f"(score: {a.get('score', 0):.2f})"
                )
        else:
            st.info("No anomalies detected")
    else:
        st.error(anomalies.get("error"))

with col2:
    st.subheader("Recent Remediations")
    remediations = api_request("/remediations")
    if "error" not in remediations:
        history = remediations.get("history", [])[-5:]
        if history:
            for r in reversed(history):
                status = "✅" if r.get("success") else "❌"
                st.markdown(
                    f"- {status} **{r.get('device_id', 'unknown')}**: "
                    f"{r.get('action_type', 'unknown')}"
                )
        else:
            st.info("No remediations performed")
    else:
        st.error(remediations.get("error"))

# Footer
st.divider()
st.caption(
    "LLM-NetAuto-SDN | LLM-Based Network Automation with Real-Time Monitoring in SDN | "
    "Version 1.0.0 | Live Mode"
)
