"""
System Health Page for LLM-NetAuto-SDN.

Service status and system diagnostics.
"""

import os
import sys
import requests
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

API_URL = f"http://127.0.0.1:{os.getenv('FASTAPI_PORT', '8000')}"
DEMO_MODE = False


def api_request(endpoint, method="GET", data=None):
    """Make API request."""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json=data, timeout=30)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def check_service(name, url, timeout=2, auth=None):
    """Check if a service is healthy."""
    try:
        r = requests.get(url, timeout=timeout, auth=auth if auth else None)
        return r.status_code == 200, r.elapsed.total_seconds() * 1000
    except:
        return False, 0


# Page config
st.set_page_config(page_title="System Health - LLM-NetAuto", page_icon="🏥", layout="wide")

st.title("🏥 System Health")

# Service status cards
st.subheader("Service Status")

services = [
    {"name": "FastAPI Backend", "url": f"{API_URL}/health"},
    {"name": "ONOS Controller", "url": f"http://127.0.0.1:{os.getenv('ONOS_PORT', '8181')}/onos/v1/cluster", "auth": ('onos', 'rocks')},
    {"name": "Ollama LLM", "url": f"{os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')}/api/tags"},
    {"name": "ChromaDB", "url": f"http://127.0.0.1:{os.getenv('CHROMADB_PORT', '8001')}/api/v2/heartbeat"},
]

cols = st.columns(3)

for i, service in enumerate(services):
    with cols[i % 3]:
        auth = service.get("auth", None)
        healthy, latency = check_service(service["name"], service["url"], auth=auth)
        status_text = "Connected" if healthy else "Offline"

        with st.container():
            st.markdown(f"### {service['name']}")
            if healthy:
                st.success(f"✅ {status_text}")
                st.caption(f"Response time: {latency:.0f}ms")
            else:
                st.error(f"❌ {status_text}")
                st.caption("Service unreachable")

st.divider()

# Component details
st.subheader("Component Details")

# ONOS Details
with st.expander("📡 ONOS Controller"):
    topo = api_request("/topology")
    if "error" not in topo:
        st.markdown(f"**Devices:** {len(topo.get('devices', []))}")
        st.markdown(f"**Hosts:** {len(topo.get('hosts', []))}")
        st.markdown(f"**Links:** {len(topo.get('links', [])) // 2}")
    else:
        st.error("Could not connect to ONOS")

# Ollama Details
with st.expander("🤖 Ollama LLM"):
    try:
        r = requests.get(f"{os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')}/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            for m in models:
                st.markdown(f"**Model:** {m.get('name', 'unknown')}")
                st.markdown(f"**Size:** {m.get('size', 0) / 1e9:.2f} GB")
        else:
            st.error("Ollama not responding")
    except:
        st.error("Could not connect to Ollama")

# ChromaDB Details
with st.expander("🗃️ ChromaDB"):
    rag_stats = api_request("/rag/stats")
    if "error" not in rag_stats:
        st.json(rag_stats)

        # Re-seed button
        if st.button("🔄 Re-seed Topology"):
            result = api_request("/rag/seed", method="POST")
            if "error" not in result and result.get("success"):
                st.success("Topology re-seeded successfully")
            else:
                st.error("Failed to re-seed")
    else:
        st.error("Could not get RAG stats")

st.divider()

# Metrics summary
st.subheader("Metrics Summary")

metrics = api_request("/metrics/summary")
if "error" not in metrics:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Telemetry**")
        telemetry = metrics.get("telemetry", {})
        st.markdown(f"- Devices monitored: {telemetry.get('devices_monitored', 0)}")
        st.markdown(f"- Total samples: {telemetry.get('total_samples', 0)}")
        st.markdown(f"- Poll interval: {telemetry.get('poll_interval', 5)}s")

    with col2:
        st.markdown("**Anomaly Detector**")
        anomaly = metrics.get("anomaly_detector", {})
        st.markdown(f"- Trained: {'Yes' if anomaly.get('is_trained') else 'No'}")
        st.markdown(f"- Training samples: {anomaly.get('training_samples', 0)}")
        st.markdown(f"- Anomalies detected: {anomaly.get('anomalies_detected', 0)}")

    with col3:
        st.markdown("**Alerts**")
        alerts = metrics.get("alerts", {})
        st.markdown(f"- Active alerts: {alerts.get('active_alerts', 0)}")
        st.markdown(f"- Critical: {alerts.get('critical_count', 0)}")
        st.markdown(f"- Warnings: {alerts.get('warning_count', 0)}")
        
        alerts_detail = api_request("/alerts")
        active_list = alerts_detail.get("active", []) if "error" not in alerts_detail else []
        if active_list:
            st.markdown("**Active Alerts:**")
            for a in active_list:
                sev_icon = "🚨" if a.get("severity") == "critical" else "⚠️"
                st.markdown(f"{sev_icon} **{a.get('title')}**")
                st.caption(f"_{a.get('message')}_")
        else:
            st.caption("🟢 No active alerts or warnings")
else:
    st.error("Could not get metrics")

st.divider()

# Benchmark
st.subheader("Benchmark")

col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🚀 Run Benchmark"):
        with st.spinner("Running benchmark..."):
            result = api_request("/comparison/run", method="POST")
        if "error" not in result:
            st.success("Benchmark started in background")
        else:
            st.error(f"Failed: {result['error']}")

benchmark_results = api_request("/comparison/results")
if "error" not in benchmark_results and benchmark_results:
    summary = benchmark_results.get("summary", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Time Reduction", f"{summary.get('avg_time_reduction_percent', 0):.1f}%")
    with col2:
        st.metric("Steps Saved", f"{summary.get('avg_steps_reduction_percent', 0):.1f}%")
    with col3:
        time_saved = summary.get('total_time_saved_seconds', 0)
        st.metric("Time Saved", f"{time_saved/60:.1f} min")
    with col4:
        st.metric("Tasks Passed", f"{summary.get('tasks_successful', 0)}/10")
else:
    st.info("No benchmark results available. Click 'Run Benchmark' to generate.")

st.divider()

# Service URLs
st.subheader("Service URLs")

urls = {
    "FastAPI Docs": f"{API_URL}/docs",
    "ONOS Web UI": f"http://127.0.0.1:{os.getenv('ONOS_PORT', '8181')}/onos/ui"
}

for name, url in urls.items():
    st.markdown(f"- **{name}**: [{url}]({url})")

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
