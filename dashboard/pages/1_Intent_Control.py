"""
Intent Control Page for LLM-NetAuto-SDN.

Submit natural language intents to configure the network.
"""

import os
import sys
import json
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
            r = requests.post(url, json=data, timeout=30)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Backend not running"}
    except Exception as e:
        return {"error": str(e)}


# Page config
st.set_page_config(page_title="Intent Control - LLM-NetAuto", page_icon="🎯", layout="wide")

# No demo banners — live mode only

st.title("🎯 Network Intent Control Panel")
st.markdown("Submit natural language intents to configure your SDN network.")

# Refresh button
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# Example Intents
with st.expander("📝 Example Intents (click to use)", expanded=True):
    examples = [
        "Block all traffic from 10.0.0.1",
        "Allow only HTTP traffic from h1 to h3",
        "Prioritize VoIP traffic on UDP port 5060",
        "Drop all ICMP packets on all switches",
        "Rate limit h5 to 10 Mbps",
        "Isolate switch s2 from the network",
        "Mirror all traffic on s1 to port 5",
        "Allow only SSH between h2 and h4",
        "Remove all custom flow rules",
        "Block traffic between h1 and h5"
    ]

    cols = st.columns(2)
    for i, example in enumerate(examples):
        col = cols[i % 2]
        if col.button(example, key=f"ex_{i}", use_container_width=True):
            st.session_state.selected_intent = example

# Intent Input
st.subheader("Submit Intent")

with st.form(key="intent_form"):
    default_intent = st.session_state.get("selected_intent", "")
    intent_text = st.text_area(
        "Enter your network intent in natural language:",
        value=default_intent,
        height=100,
        placeholder="e.g., Block all traffic from 10.0.0.1"
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        submit = st.form_submit_button("🚀 Submit Intent", type="primary", use_container_width=True)

# Process intent
if submit and intent_text:
    with st.spinner("Processing intent... This may take 1-4 seconds"):
        result = api_request("/intent", "POST", {"intent": intent_text})
    st.session_state.submit_result = result
    # Clear selected intent after successful processing so it does not linger
    st.session_state.pop("selected_intent", None)
    # After submission, refresh history immediately
    st.rerun()

# Display result from session state if present
if "submit_result" in st.session_state:
    result = st.session_state.submit_result
    if not result.get("error"):
        # Display result in expander
        with st.container(border=True):
            st.subheader("📊 Submitted Intent Result Details")
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Latency", f"{result.get('latency_ms', 0):.1f} ms")
            with col2:
                status = "Success" if result.get("success") else "Failed"
                st.metric("Status", status)
            with col3:
                st.metric("Method", result.get("deployment_method", "none"))

            # Summary
            if result.get("summary"):
                st.info(f"**Summary**: {result.get('summary')}")

            # Parsed Rule
            with st.expander("📋 Parsed Rule JSON"):
                st.json(result.get("parsed_rule", {}))

            # Validation
            with st.expander("✅ Validation Details"):
                validation = result.get("validation", {})
                if validation.get("valid"):
                    st.success("Rule passed validation")
                else:
                    st.warning("Validation issues found")
                    for issue in validation.get("issues", []):
                        st.markdown(f"- {issue}")

            # Similar Intents
            with st.expander("🔍 Similar Past Intents"):
                similar = result.get("similar_past_intents", [])
                if similar:
                    for s in similar:
                        st.markdown(f"- {s.get('intent', 'N/A')} ({s.get('type', 'unknown')})")
                else:
                    st.info("No similar intents found")
    else:
        st.error(f"❌ Error: {result.get('error')}")

    if st.button("Dismiss Details", type="secondary"):
        del st.session_state.submit_result
        st.rerun()

# Intent History
st.divider()
st.subheader("📜 Intent History")

# Controls: Refresh and Clear All
col_a, col_b = st.columns([3, 1])
with col_b:
    if st.button("🧹 Clear All Intents & Flows", use_container_width=True, type="primary"):
        with st.spinner("Clearing all flows and intents..."):
            r = api_request("/intent/clear-all", method="POST")
            if "error" not in r:
                st.success("Successfully cleared all intents and flow rules!")
                st.rerun()
            else:
                st.error(f"Failed to clear: {r['error']}")

# Auto-refresh indicator
st.markdown(f"_Last updated: {datetime.now().strftime('%H:%M:%S')}_")

# Fetch history from backend (newest first)
history_data = api_request("/intent/history")
backend_history = history_data.get("history", [])

if backend_history:
    st.info(f"📊 Total submissions: {len(backend_history)}")

    for entry in backend_history:
        status_icon = "✅" if entry.get("success") else "❌"
        title = entry.get('intent', '')
        with st.expander(f"{status_icon} {title[:80]}"):
            st.markdown(f"**Time**: {entry.get('timestamp')}")
            st.markdown(f"**Intent**: {entry.get('intent')}")
            st.markdown(f"**Type**: {entry.get('intent_type', 'N/A')}")
            st.markdown(f"**Status**: {'✅ Success' if entry.get('success') else '❌ Failed'}")
            st.markdown(f"**Latency**: {entry.get('latency_ms', 0):.1f}ms")
            st.markdown(f"**Method**: {entry.get('deployment_method', 'unknown')}")
            if entry.get('deployment_time'):
                st.markdown(f"**Deployment Time**: {entry.get('deployment_time')}")
            if entry.get('affected_devices'):
                st.markdown(f"**Affected Devices**: {', '.join(entry.get('affected_devices'))}")
            if entry.get('summary'):
                st.info(f"**Summary**: {entry.get('summary')}")

            # Action buttons: Delete this intent history (and ONOS intent if present)
            if st.button("🗑️ Delete Intent", key=f"del_hist_{entry.get('id')}"):
                hid = entry.get('id')
                resp = api_request(f"/intent/history/{hid}", method="DELETE")
                if resp.get('success'):
                    st.success("Deleted intent and removed ONOS intent if present")
                    st.rerun()
                else:
                    st.error("Failed to delete intent history")
else:
    st.info("No intents submitted yet. Try one of the examples above!")
