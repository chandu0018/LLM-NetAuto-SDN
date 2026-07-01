"""
Realtime Monitor Page for LLM-NetAuto-SDN.

Live network telemetry, anomaly detection, and alerts.
"""

import os
import sys
import requests
from datetime import datetime

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
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
            r = requests.post(url, json=data, timeout=10)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def format_bytes(b: float) -> str:
    """Format bytes into human readable dynamic string."""
    if b >= 1e9:
        return f"{b/1e9:.2f} GB"
    elif b >= 1e6:
        return f"{b/1e6:.2f} MB"
    elif b >= 1e3:
        return f"{b/1e3:.2f} KB"
    else:
        return f"{b:.0f} Bytes"


# Page config
st.set_page_config(page_title="Realtime Monitor - LLM-NetAuto", page_icon="📊", layout="wide")

st.title("📊 Real-Time Network Monitor")

# Get alerts
alerts = api_request("/alerts")
active_alerts = alerts.get("active", []) if "error" not in alerts else []

# Alert banner
if active_alerts:
    for alert in active_alerts[:3]:
        severity = alert.get("severity", "warning")
        if severity == "critical":
            st.error(f"🚨 **CRITICAL**: {alert.get('title', 'Unknown alert')}")
        else:
            st.warning(f"⚠️ **WARNING**: {alert.get('title', 'Unknown alert')}")

# Auto-refresh
col1, col2 = st.columns([4, 1])
with col2:
    auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)

# Top metrics
st.subheader("Network Metrics")

stats = api_request("/stats")
anomalies = api_request("/anomalies")
remediations = api_request("/remediations")

col1, col2, col3, col4 = st.columns(4)

if "error" not in stats:
    statistics = stats.get("statistics", [])
    total_rx = sum(
        sum(p.get("bytesReceived", 0) for p in s.get("ports", []))
        for s in statistics
    )
    total_tx = sum(
        sum(p.get("bytesSent", 0) for p in s.get("ports", []))
        for s in statistics
    )

    with col1:
        st.metric("Total Bytes RX", format_bytes(total_rx))
    with col2:
        st.metric("Total Bytes TX", format_bytes(total_tx))

with col3:
    anomaly_count = len(anomalies.get("history", [])) if "error" not in anomalies else 0
    st.metric("Anomalies Today", anomaly_count)

with col4:
    rem_count = len(remediations.get("history", [])) if "error" not in remediations else 0
    st.metric("Remediations", rem_count)

st.divider()

# Live charts
st.subheader("Traffic Visualization")

# Device selector — fetched live from ONOS
devices_resp = api_request("/devices")
devices = [
    d.get("id") for d in devices_resp.get("devices", [])
    if d.get("id")
] if "error" not in devices_resp else []

if not devices:
    st.warning("⚠️ No devices found — check that ONOS is running and Mininet switches are connected.")
    st.stop()

selected_device = st.selectbox(
    "Select Device:",
    devices,
    format_func=lambda x: x  # show full ONOS device ID
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Bytes RX/TX Over Time**")

    history = api_request(f"/telemetry/history/{selected_device}?n=60")

    if "error" not in history and history.get("history"):
        hist_data = history["history"]

        df_data = []
        for h in hist_data:
            rates = h.get("rates", {})
            df_data.append({
                "Time": h.get("timestamp", "")[:19],
                "RX Rate (MB/s)": rates.get("bytes_rx_rate", 0) / 1e6,
                "TX Rate (MB/s)": rates.get("bytes_tx_rate", 0) / 1e6
            })

        if df_data:
            df = pd.DataFrame(df_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["Time"], y=df["RX Rate (MB/s)"],
                name="RX Rate", line=dict(color="blue")
            ))
            fig.add_trace(go.Scatter(
                x=df["Time"], y=df["TX Rate (MB/s)"],
                name="TX Rate", line=dict(color="green")
            ))
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Collecting data...")
    else:
        st.info("No telemetry data available yet")

with col2:
    st.markdown("**Packet Drop Rate**")

    if "error" not in history and history.get("history"):
        df_data = []
        for h in history["history"]:
            rates = h.get("rates", {})
            df_data.append({
                "Time": h.get("timestamp", "")[:19],
                "Drop Rate (%)": rates.get("drop_rate", 0) * 100
            })

        if df_data:
            df = pd.DataFrame(df_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["Time"], y=df["Drop Rate (%)"],
                name="Drop Rate", line=dict(color="red")
            ))
            # Threshold line
            fig.add_hline(y=5, line_dash="dash", line_color="orange",
                         annotation_text="Warning (5%)")
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available")

st.divider()

# Anomaly status per device
st.subheader("Anomaly Detection Status")

anomaly_status = anomalies.get("status", {}) if "error" not in anomalies else {}
anomaly_history = anomalies.get("history", []) if "error" not in anomalies else []

if devices:
    # Render in rows of 4 columns to avoid index overflow and accommodate arbitrary scales (2-8)
    cols_per_row = 4
    for row_idx in range(0, len(devices), cols_per_row):
        row_devices = devices[row_idx:row_idx + cols_per_row]
        cols = st.columns(len(row_devices))
        for j, device_id in enumerate(row_devices):
            with cols[j]:
                # Get latest score for this device
                device_anomalies = [
                    a for a in anomaly_history
                    if a.get("device_id") == device_id
                ]
                latest_score = device_anomalies[-1].get("score", 0) if device_anomalies else 0
                is_anomaly = any(
                    a.get("is_anomaly") for a in device_anomalies[-5:]
                ) if device_anomalies else False

                st.metric(
                    f"s{device_id[-1]} Status",
                    "Anomaly" if is_anomaly else "Normal",
                    f"Score: {latest_score:.2f}",
                    delta_color="inverse" if is_anomaly else "normal"
                )

st.divider()

# Anomaly history table
st.subheader("Recent Anomalies")

if anomaly_history:
    recent = anomaly_history[-10:]
    anomaly_table = []
    for a in reversed(recent):
        anomaly_table.append({
            "Timestamp": a.get("timestamp", "")[:19],
            "Device": f"s{a.get('device_id', '')[-1:]}",
            "Score": f"{a.get('score', 0):.3f}",
            "Status": "🔴 Anomaly" if a.get("is_anomaly") else "🟢 Normal",
            "Type": a.get("type", "N/A")
        })
    st.dataframe(anomaly_table, use_container_width=True, hide_index=True)
else:
    is_trained = anomaly_status.get("is_trained", False)
    if is_trained:
        st.success("🟢 No anomalies detected yet. The network is healthy and monitored.")
    else:
        st.info("ℹ️ No anomalies detected yet. The model is currently training on baseline data.")

st.divider()

# Manual Anomaly Injector Panel
st.subheader("🧪 Manual Anomaly Injector")
with st.expander("⚠️ Inject Simulated Telemetry Anomaly (For Testing Self-Healing)", expanded=False):
    col_inj1, col_inj2, col_inj3 = st.columns(3)
    with col_inj1:
        inj_device = st.selectbox("Target Switch:", devices, key="inj_dev")
    with col_inj2:
        inj_type = st.selectbox(
            "Anomaly Type:",
            ["traffic_spike", "ddos_sim", "bandwidth_hog", "packet_drop", "error_spike"],
            format_func=lambda x: x.replace("_", " ").title(),
            key="inj_type"
        )
    with col_inj3:
        inj_duration = st.slider("Duration (seconds):", 10, 300, 60, step=10, key="inj_dur")
        
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚀 Trigger Anomaly", type="primary", use_container_width=True):
            res = api_request("/demo/anomaly", method="POST", data={
                "device_id": inj_device,
                "anomaly_type": inj_type,
                "duration_seconds": inj_duration
            })
            if "error" not in res:
                st.success(f"Successfully injected '{inj_type}' on '{inj_device}'!")
                st.rerun()
            else:
                st.error(f"Failed to inject: {res['error']}")
    with col_btn2:
        if st.button("🟢 Clear All Injections", type="secondary", use_container_width=True):
            res = api_request("/demo/resolve", method="POST")
            if "error" not in res:
                st.success("Successfully cleared all injected anomalies!")
                st.rerun()
            else:
                st.error(f"Failed to clear: {res['error']}")

st.divider()

# Remediation log
st.subheader("Remediation Log")

col1, col2 = st.columns([3, 1])
with col2:
    feedback_status = api_request("/feedback/status")
    if "error" not in feedback_status:
        is_running = feedback_status.get("running", False)
        is_paused = feedback_status.get("paused", False)

        if is_paused:
            if st.button("▶️ Resume Feedback Loop"):
                api_request("/feedback/resume", method="POST")
                st.rerun()
        else:
            if st.button("⏸️ Pause Feedback Loop"):
                api_request("/feedback/pause", method="POST")
                st.rerun()

rem_history = remediations.get("history", []) if "error" not in remediations else []

if rem_history:
    rem_table = []
    for r in reversed(rem_history[-10:]):
        rem_table.append({
            "Timestamp": r.get("timestamp", "")[:19],
            "Device": f"s{r.get('device_id', '')[-1:]}",
            "Anomaly": r.get("anomaly_type", "N/A"),
            "Action": r.get("action_type", "N/A"),
            "Result": "✅ Success" if r.get("success") else "❌ Failed"
        })
    st.dataframe(rem_table, use_container_width=True, hide_index=True)
else:
    st.info("No remediations performed yet.")

# Auto-refresh
if auto_refresh:
    import time
    time.sleep(5)
    st.rerun()

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
