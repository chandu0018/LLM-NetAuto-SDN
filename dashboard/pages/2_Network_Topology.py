"""
Network Topology Page for LLM-NetAuto-SDN.

Displays interactive network topology visualization.
"""

import os
import sys
import requests
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
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


def create_topology_html(devices, hosts, links, intents=None):
    """Create vis.js network visualization HTML."""
    nodes = []
    edges = []
    intents = intents or []

    # Map affected devices -> intent types for coloring
    device_intent_map = {}
    for it in intents:
        # defensive: skip non-dict entries
        if not isinstance(it, dict):
            continue
        itype = (it.get('type') or it.get('intent_type') or '').lower()
        affected = it.get('affected_devices', []) or []
        for d in affected:
            device_intent_map.setdefault(d, []).append(itype)

    # Add switch nodes
    for d in devices:
        device_id = d.get("id", "")
        name = d.get("annotations", {}).get("name", device_id[-2:])
        available = d.get("available", True)
        # Color by any affecting intent (block=red, allow=green, prioritize=yellow)
        color = "#2196F3" if available else "#F44336"
        intents_here = device_intent_map.get(device_id, [])
        if intents_here:
            if any('block' in t for t in intents_here):
                color = "#F44336"
            elif any('priorit' in t or 'rate' in t for t in intents_here):
                color = "#FFEB3B"
            elif any('allow' in t for t in intents_here):
                color = "#4CAF50"

        nodes.append({
            "id": device_id,
            "label": name,
            "title": f"Device: {device_id}\\nStatus: {'Available' if available else 'Down'}",
            "color": color,
            "shape": "box",
            "size": 30,
            "font": {"color": "black" if color == '#FFEB3B' else "white"}
        })

    # Add host nodes
    for h in hosts:
        mac = h.get("mac", "")
        name = h.get("name", mac[:8])
        ips = h.get("ipAddresses", [])
        ip = ips[0] if ips else "N/A"
        location = h.get("locations", [{}])[0]
        switch = location.get("elementId", "")

        host_id = f"host_{mac}"
        nodes.append({
            "id": host_id,
            "label": f"{name}\\n{ip}",
            "title": f"Host: {name}\\nIP: {ip}\\nMAC: {mac}\\nSwitch: {switch}",
            "color": "#4CAF50",
            "shape": "dot",
            "size": 20
        })

        # Edge to switch
        if switch:
            edges.append({
                "from": host_id,
                "to": switch,
                "color": "#90CAF9",
                "width": 1
            })

    # Add switch-switch links
    seen = set()
    for l in links:
        src = l.get("src", {}).get("device", "")
        dst = l.get("dst", {}).get("device", "")
        state = l.get("state", "ACTIVE")

        key = tuple(sorted([src, dst]))
        if key in seen:
            continue
        seen.add(key)

        # If either endpoint affected by a blocking intent, make edge red
        edge_color = "#666" if state == "ACTIVE" else "#F44336"
        if src in device_intent_map or dst in device_intent_map:
            dev_types = (device_intent_map.get(src, []) + device_intent_map.get(dst, []))
            if any('block' in t for t in dev_types):
                edge_color = "#F44336"
            elif any('priorit' in t or 'rate' in t for t in dev_types):
                edge_color = "#FFEB3B"
            elif any('allow' in t for t in dev_types):
                edge_color = "#4CAF50"

        edges.append({
            "from": src,
            "to": dst,
            "color": edge_color,
            "width": 3,
            "dashes": state != "ACTIVE"
        })

    import json
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
        <style>
            #network {{
                width: 100%;
                height: 500px;
                border: 1px solid #ddd;
                border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        <div id="network"></div>
        <script>
            var nodes = new vis.DataSet({nodes_json});
            var edges = new vis.DataSet({edges_json});

            var container = document.getElementById('network');
            var data = {{ nodes: nodes, edges: edges }};
            var options = {{
                physics: {{
                    stabilization: true,
                    barnesHut: {{
                        gravitationalConstant: -2000,
                        springLength: 150
                    }}
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 100
                }}
            }};

            var network = new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """
    return html


# Page config
st.set_page_config(page_title="Network Topology - LLM-NetAuto", page_icon="🗺️", layout="wide")

st.title("🗺️ Network Topology")

# ──────────────────────────────────────────────────────────────────────────────
# ⚙️  Configure Topology
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("⚙️ Configure Topology (Switches & Hosts)", expanded=False):
    # Fetch current config from API
    cfg_resp = api_request("/topology/config")
    cur_sw  = cfg_resp.get("n_switches", 3)       if "error" not in cfg_resp else 3
    cur_hps = cfg_resp.get("hosts_per_switch", 2) if "error" not in cfg_resp else 2

    # Mininet status badge
    mn_status = api_request("/topology/mininet-status")
    if "error" not in mn_status:
        if mn_status.get("running"):
            st.success(f"🟢 Mininet is **running** (PID {mn_status.get('pid')}) — "
                       f"{mn_status.get('n_switches')} switches, "
                       f"{mn_status.get('hosts_per_switch')} hosts/switch")
        else:
            st.warning("🔴 Mininet is **not running**. Start it below or manually with "
                       "`sudo python3 topology/mininet_topo.py`.")

    st.divider()
    col_sw, col_hps, col_ip, col_port = st.columns([2, 2, 2, 1])
    with col_sw:
        new_sw = st.slider(
            "Number of Switches",
            min_value=2, max_value=8, value=cur_sw, step=1,
            help="OVS switches connected in a ring (2–8)"
        )
    with col_hps:
        new_hps = st.slider(
            "Hosts per Switch",
            min_value=1, max_value=4, value=cur_hps, step=1,
            help="Hosts attached to each switch (1–4)"
        )
    with col_ip:
        ctrl_ip = st.text_input("ONOS Controller IP", value="127.0.0.1")
    with col_port:
        ctrl_port = st.number_input("OF Port", value=6653, step=1)

    total_hosts_preview = new_sw * new_hps
    st.caption(
        f"📊 Preview: **{new_sw} switches**, **{total_hosts_preview} hosts** "
        f"({new_hps}/switch) — ring topology"
    )

    col_btn1, col_btn2, col_info = st.columns([2, 2, 3])
    with col_btn1:
        save_only = st.button(
            "💾 Save Config (no restart)",
            use_container_width=True,
            help="Persist the new switch/host counts to .env without restarting Mininet"
        )
    with col_btn2:
        save_and_launch = st.button(
            "🚀 Apply & Launch Mininet",
            type="primary",
            use_container_width=True,
            help="Save config, kill any existing Mininet, and start a fresh topology"
        )
    with col_info:
        st.info(
            "⚠️ **Requires sudo.** The FastAPI process must be started with sudo "
            "(or have passwordless sudo for python3) for Mininet launch to work. "
            "Alternatively save the config and run the topology manually:"
            "\n```\nsudo python3 topology/mininet_topo.py "
            f"--n-switches={new_sw} --hosts-per-switch={new_hps}\n```"
        )

    if save_only or save_and_launch:
        payload = {
            "n_switches": new_sw,
            "hosts_per_switch": new_hps,
            "launch_mininet": bool(save_and_launch),
            "controller_ip": ctrl_ip,
            "controller_port": int(ctrl_port),
        }
        with st.spinner("Saving topology configuration…"):
            resp = api_request("/topology/config", method="POST", data=payload)

        if "error" in resp:
            st.error(f"❌ Failed: {resp['error']}")
        else:
            if save_and_launch:
                st.success(
                    f"✅ Config saved — Mininet launching in the background "
                    f"({resp['n_switches']} switches, {resp['total_hosts']} hosts). "
                    "Wait 15–20 seconds then refresh to see the updated topology."
                )
                # Re-seed RAG in background
                with st.spinner("Re-seeding RAG with new topology…"):
                    api_request("/rag/seed", method="POST")
            else:
                st.success(
                    f"✅ Config saved: {resp['n_switches']} switches, "
                    f"{resp['total_hosts']} hosts. Restart Mininet manually to apply."
                )
                # Still re-seed so the LLM knows about the new config
                with st.spinner("Re-seeding RAG…"):
                    api_request("/rag/seed", method="POST")
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Auto-refresh toggle
# ──────────────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([4, 1])
with col2:
    auto_refresh = st.checkbox("Auto-refresh (5s)", value=True)

# Get topology
topo = api_request("/topology")

if topo.get("error"):
    st.error(f"Failed to load topology: {topo['error']}")
    st.stop()

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

# Get active intents (enriched)
intents_resp = api_request("/intents")
intents = intents_resp.get("intents", []) if isinstance(intents_resp, dict) else []

# Deduplicate links (ONOS reports each link in both directions)
seen_link_pairs = set()
unique_link_count = 0
for l in links:
    pair = tuple(sorted([l.get("src", {}).get("device", ""), l.get("dst", {}).get("device", "")]))
    if pair not in seen_link_pairs:
        seen_link_pairs.add(pair)
        unique_link_count += 1

# Top metrics
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Switches", len(devices))
with col2:
    st.metric("Hosts", len(hosts))
with col3:
    st.metric("Links", unique_link_count)

# Get flows — only count flows on available devices
flows_resp = api_request("/flows")
all_flows = flows_resp.get("flows", []) if isinstance(flows_resp, dict) else []
live_flows = [f for f in all_flows if f.get("deviceId") in available_ids]
with col4:
    st.metric("Active Flows", len(live_flows))
with col5:
    st.metric("Active Intents", len(intents))

if len(all_devices) > len(devices):
    st.caption(f"ℹ️ Showing {len(devices)} available switches out of {len(all_devices)} total in ONOS cache. "
               f"Unavailable devices from previous sessions are hidden.")

st.divider()

# Topology visualization + side panel
st.subheader("Network Graph")
col_main, col_side = st.columns([3, 1])
with col_main:
    html = create_topology_html(devices, hosts, links, intents=intents)
    components.html(html, height=520)

with col_side:
    st.subheader("Active Intents")
    if not intents:
        st.info("No active intents")
    else:
        for it in intents:
            if not isinstance(it, dict):
                continue
            state_label = it.get('state', it.get('status', 'UNKNOWN'))
            itype = it.get('type') or it.get('intent_type') or 'N/A'
            affected = it.get('affected_devices', [])
            st.markdown(f"**{it.get('key', it.get('id', ''))[:16]}**\n - Type: {itype}\n - State: {state_label}\n - Affected: {', '.join(affected) if affected else 'N/A'}")


st.divider()

# Details tables
col1, col2 = st.columns(2)

with col1:
    st.subheader("📦 Devices")
    device_data = []
    for d in devices:
        device_data.append({
            "ID": d.get("id", ""),
            "Name": d.get("annotations", {}).get("name", "N/A"),
            "Type": d.get("type", "SWITCH"),
            "Status": "✅ Available" if d.get("available") else "❌ Down"
        })
    if device_data:
        st.dataframe(device_data, use_container_width=True, hide_index=True)
    else:
        st.info("No devices found. Is ONOS running and Mininet connected?")

with col2:
    st.subheader("🖥️ Hosts")
    host_data = []
    for h in hosts:
        ips = h.get("ipAddresses", [])
        location = h.get("locations", [{}])[0]
        host_data.append({
            "Name": h.get("name", "N/A"),
            "IP": ips[0] if ips else "N/A",
            "MAC": h.get("mac", "N/A"),
            "Switch": location.get("elementId", "N/A"),
            "Port": location.get("port", "N/A")
        })
    if host_data:
        st.dataframe(host_data, use_container_width=True, hide_index=True)
    else:
        st.info("No hosts found. Run pingall in Mininet CLI to make hosts visible to ONOS.")

# Auto-refresh
if auto_refresh:
    import time
    time.sleep(5)
    st.rerun()

st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
