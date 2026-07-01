"""
Flow Manager Page for LLM-NetAuto-SDN.

View and manage flow rules and intents.
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
        elif method == "DELETE":
            r = requests.delete(url, timeout=10)
        else:
            r = requests.post(url, json=data, timeout=10)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Page config
st.set_page_config(page_title="Flow Manager - LLM-NetAuto", page_icon="📋", layout="wide")

# Live mode only; no demo banners

st.title("📋 Flow Manager")

# Refresh / auto-refresh
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

auto_refresh = st.checkbox("Auto-refresh (5s)", value=True)

# Tabs
tab1, tab2 = st.tabs(["🎯 Active Intents", "📜 Flow Rules"])

# ==========================================
# Intents Tab
# ==========================================
with tab1:
    st.subheader("Intent Submission History")

    # Show last refresh time
    st.markdown(f"_Last updated: {datetime.now().strftime('%H:%M:%S')}_")

    # Try to get history first (always fresh)
    history_data = api_request("/intent/history")
    history = history_data.get("history", [])

    if history:
        st.info(f"📊 Total submissions: {len(history)}")

        # Display history
        for i, entry in enumerate(history):
            status_icon = "✅" if entry.get("success") else "❌"
            timestamp = entry.get("timestamp", "Unknown")
            intent = entry.get("intent", "Unknown")[:60]
            latency = entry.get("latency_ms", 0)

            with st.expander(f"{status_icon} {intent}... ({latency:.0f}ms)"):
                st.markdown(f"**Time**: {timestamp}")
                st.markdown(f"**Intent**: {entry.get('intent', 'N/A')}")
                st.markdown(f"**Status**: {'✅ Success' if entry.get('success') else '❌ Failed'}")
                st.markdown(f"**Latency**: {latency:.1f}ms")
                st.markdown(f"**Method**: {entry.get('deployment_method', 'unknown')}")
                if entry.get('summary'):
                    st.info(f"**Summary**: {entry.get('summary')}")
    else:
        st.info("No intent submissions yet. Submit one from the Intent Control page.")

    st.divider()
    st.subheader("🎯 Active Network Intents")

    # We load active user intents directly from the successful history entries, 
    # since this represents all user-injected natural language intents (both flow_rule and intent_framework)
    active_user_intents = [h for h in history if h.get("success")]

    if not active_user_intents:
        st.info("🟢 No active custom intents on the network. Submit a new intent in the Intent Control panel to secure or route your network!")
    else:
        st.success(f"Active intents: {len(active_user_intents)}")

        for entry in active_user_intents:
            intent_text = entry.get("intent", "Custom Intent")
            hist_id = entry.get("id")
            method = entry.get("deployment_method", "flow_rule")
            timestamp = entry.get("timestamp", "N/A")
            summary = entry.get("summary", "No details available")

            # Determine implementation badge
            if method == "flow_rule":
                badge = "⚡ Direct Flow Rules (Switch-by-Switch)"
                color = "blue"
            else:
                badge = "🎯 ONOS Intent Framework"
                color = "green"

            with st.expander(f"⚙️ :{color}[Active] - {intent_text} ({badge})"):
                st.markdown(f"**Submitted**: {timestamp}")
                st.markdown(f"**Description**: {intent_text}")
                st.markdown(f"**Summary**: {summary}")
                st.markdown(f"**Implementation**: {badge}")

                # Retrieve details of the installed rules
                onos_response = entry.get("onos_response")
                if isinstance(onos_response, list) and method == "flow_rule":
                    st.markdown("**Installed Flow Rules:**")
                    flow_table = []
                    for resp in onos_response:
                        if isinstance(resp, dict):
                            dev_id = resp.get("deviceId", "N/A")[-1:]
                            flow_id = resp.get("id", "N/A")[:8]
                            flow_table.append(f"- Switch `s{dev_id}` (Flow ID: `{flow_id}`)")
                    st.markdown("\n".join(flow_table))
                elif isinstance(onos_response, dict) and method == "intent_framework":
                    key = onos_response.get("key", "N/A")
                    app_id = onos_response.get("appId", "N/A")
                    st.markdown(f"- ONOS Intent Key: `{key}` (App: `{app_id}`)")

                # Delete Button
                if st.button("🗑️ Remove Intent & Clean Up Rules", key=f"remove_intent_{hist_id}"):
                    result = api_request(f"/intent/history/{hist_id}", "DELETE")
                    if not result.get("error"):
                        st.success("✅ Intent successfully removed and flow rules purged from switches!")
                        st.rerun()
                    else:
                        st.error(f"Failed to remove intent: {result.get('error', 'Unknown')}")


# ==========================================
# Flow Rules Tab
# ==========================================
with tab2:
    st.subheader("Flow Rules")

    # Live Telemetry Demonstration Traffic Generator Button
    col_lbl, col_gen, col_stop = st.columns([2, 1, 1])
    with col_lbl:
        st.markdown("💡 *Trigger real-time cross-switch ping traffic to immediately watch packet/byte counters increment*")
    with col_gen:
        if st.button("⚡ Generate Traffic", use_container_width=True, type="primary"):
            traffic_res = api_request("/topology/generate-traffic", "POST")
            if traffic_res.get("success"):
                st.toast("⚡ Background traffic launched!", icon="🔥")
                st.success(traffic_res.get("message"))
            else:
                st.error(traffic_res.get("error", "Failed to trigger traffic"))
    with col_stop:
        if st.button("🛑 Stop Traffic", use_container_width=True):
            stop_res = api_request("/topology/stop-traffic", "POST")
            if stop_res.get("success"):
                st.toast("🛑 Background traffic stopped!", icon="🛑")
                st.success(stop_res.get("message"))
            else:
                st.error(stop_res.get("error", "Failed to stop traffic"))

    st.write("") # spacing

    # Device filter
    devices_data = api_request("/devices")
    all_devices = devices_data.get("devices", [])
    # Filter to only AVAILABLE (live) devices so stale ONOS cache entries are hidden
    devices = [d for d in all_devices if d.get("available", False)]
    available_ids = {d.get("id") for d in devices}

    device_options = ["All Devices"] + [
        d.get("annotations", {}).get("name", d.get("id", ""))
        for d in devices
    ]
    device_ids = {
        d.get("annotations", {}).get("name", d.get("id", "")): d.get("id", "")
        for d in devices
    }

    selected_device = st.selectbox("Filter by Device:", device_options)

    # Get flows
    if selected_device == "All Devices":
        flows_data = api_request("/flows")
    else:
        device_id = device_ids.get(selected_device, "")
        flows_data = api_request(f"/flows/{device_id}")

    if flows_data.get("error"):
        st.error(f"Failed to load flows: {flows_data['error']}")
    else:
        all_flows = flows_data.get("flows", [])
        
        # Filter flows: only keep flows belonging to live (available) switches
        flows = [f for f in all_flows if f.get("deviceId") in available_ids]

        if not flows:
            st.info("No flow rules found.")
        else:
            # Sort by priority
            flows = sorted(flows, key=lambda x: x.get("priority", 0), reverse=True)

            # Diagnostic checkbox to see system rules, off by default
            show_system_flows = st.checkbox("Show system flow rules (diagnostic)", value=False)

            # Filter rules
            filtered_flows = []
            for flow in flows:
                app_id = flow.get("appId", "")
                priority = flow.get("priority", 0)
                SYSTEM_APP_IDS = {"org.onosproject.core", "org.onosproject.fwd"}
                is_system = app_id in SYSTEM_APP_IDS

                if show_system_flows:
                    filtered_flows.append(flow)
                else:
                    if not is_system:
                        filtered_flows.append(flow)

            if not filtered_flows:
                st.success("🟢 No custom user flow rules active on the network. Submit an intent in the Intent Control panel to inject custom rules!")
            else:
                # Display
                flow_table = []
                for flow in filtered_flows:
                    flow_id = flow.get("id", "N/A")
                    device = flow.get("deviceId", "N/A")[-1:] if flow.get("deviceId") else "N/A"
                    priority = flow.get("priority", 0)
                    state = flow.get("state", "UNKNOWN")
                    app_id = flow.get("appId", "N/A")

                    # Parse selector into premium human-readable string
                    selector = flow.get("selector", {}).get("criteria", [])
                    match_parts = []
                    for c in selector:
                        c_type = c.get("type", "")
                        if c_type == "ETH_SRC":
                            match_parts.append(f"Src MAC: {c.get('mac', '')}")
                        elif c_type == "ETH_DST":
                            match_parts.append(f"Dst MAC: {c.get('mac', '')}")
                        elif c_type == "IPV4_SRC":
                            match_parts.append(f"Src IP: {c.get('ip', '')}")
                        elif c_type == "IPV4_DST":
                            match_parts.append(f"Dst IP: {c.get('ip', '')}")
                        elif c_type == "IP_PROTO":
                            proto_map = {1: "ICMP", 6: "TCP", 17: "UDP"}
                            match_parts.append(f"Proto: {proto_map.get(c.get('protocol', 0), c.get('protocol', ''))}")
                        elif c_type == "TCP_DST" or c_type == "UDP_DST":
                            match_parts.append(f"Port: {c.get('tcpPort') or c.get('udpPort', '')}")
                        elif c_type == "ETH_TYPE":
                            # Ignore IPv4 type to keep it clean, show others
                            eth = c.get("ethType", "")
                            if eth != "0x0800":
                                match_parts.append(f"Eth: {eth}")
                    match_str = ", ".join(match_parts) if match_parts else "Any Traffic"

                    # Parse treatment into premium human-readable actions
                    treatment = flow.get("treatment", {}).get("instructions", [])
                    action_types = [t.get("type", "") for t in treatment]
                    if not treatment or "NOACTION" in action_types:
                        action_str = "🚫 DROP (Block)"
                    else:
                        action_str = ", ".join(action_types[:2])
                        action_str = action_str.replace("OUTPUT", "➡️ FORWARD")
                        action_str = action_str.replace("QUEUE", "⚡ PRIORITIZE (QoS)")
                        action_str = action_str.replace("METER", "⏳ RATE LIMIT")

                    # Determine rule type
                    is_system = app_id in {"org.onosproject.core", "org.onosproject.fwd"}
                    rule_type = "🔒 System" if is_system else "👤 Custom User"

                    flow_table.append({
                        "ID": str(flow_id)[:8],
                        "Device": f"s{device}",
                        "Priority": priority,
                        "Type": rule_type,
                        "Match": match_str,
                        "Action": action_str,
                        "Bytes": flow.get("bytes", 0),
                        "Packets": flow.get("packets", 0)
                    })

                st.dataframe(flow_table, use_container_width=True, hide_index=True)

            # Delete flow
            st.divider()
            st.subheader("Flow Rule Deletion")

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                del_device = st.selectbox(
                    "Device:",
                    [d.get("id", "") for d in devices],
                    format_func=lambda x: x[-1:] if x else "N/A"
                )
            with col2:
                del_flow_id = st.text_input("Flow ID:")
            with col3:
                st.write("")  # spacing
                st.write("")  # spacing
                if st.button("🗑️ Delete Flow", use_container_width=True):
                    if del_device and del_flow_id:
                        result = api_request(f"/flow/{del_device}/{del_flow_id}", "DELETE")
                        if "error" not in result and result.get("success"):
                            st.success("Flow deleted")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {result.get('error', 'Unknown')}")
                    else:
                        st.warning("Please enter device and flow ID")

            st.divider()
            if st.button("🧹 Clear All User Intents & Flow Rules", type="primary", use_container_width=True):
                with st.spinner("Clearing all custom rules..."):
                    result = api_request("/intent/clear-all", "POST")
                    if "error" not in result and result.get("success"):
                        st.success("All intents and flow rules successfully cleared!")
                        st.rerun()
                    else:
                        st.error(f"Failed to clear: {result.get('error', 'Unknown')}")

            st.caption(f"Total: {len(flows)} flow rules")

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

if auto_refresh:
    import time
    time.sleep(5)
    st.rerun()
