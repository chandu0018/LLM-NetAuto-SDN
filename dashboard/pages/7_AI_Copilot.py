"""
AI Copilot & Visual Path Tracer Page for LLM-NetAuto-SDN.

Contains the Interactive conversational SDN chatbot and visual path routing tracer.
"""

import os
import sys
import json
import requests
import networkx as nx
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

API_URL = f"http://127.0.0.1:{os.getenv('FASTAPI_PORT', '8000')}"


def api_request(endpoint, method="GET", data=None):
    """Make API request to the backend."""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        else:
            r = requests.post(url, json=data, timeout=30)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Page config
st.set_page_config(page_title="AI Copilot & Tracer - LLM-NetAuto", page_icon="🤖", layout="wide")

st.title("🤖 AI Network Copilot & Visual Path Tracer")
st.markdown("Interact with your SDN network conversational chatbot and plan/trace active routing paths visually.")

# Check API backend availability
backend_status = api_request("/flows")
if "error" in backend_status and "Connection" in backend_status["error"]:
    st.error("❌ Backend server is not running. Please launch the SDN controller and backend first!")
    st.stop()

# Layout: Left column is the AI Chatbot, Right column is the Path Tracer
col_chat, col_trace = st.columns([1, 1], gap="large")

# ==========================================
# Left Column: Interactive Chatbot
# ==========================================
with col_chat:
    st.subheader("💬 AI Network Copilot Chat")
    st.caption("Ask questions about switch statuses, anomalies, active rules, or how to configure rules.")

    # Initialize chat session history
    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = [
            {
                "role": "assistant",
                "content": "👋 Welcome! I am your SDN AI Copilot. I have live access to active switches, hosts, links, flow rules, and system alert logs. How can I help you manage your network today?"
            }
        ]

    # Chat history container
    chat_container = st.container(height=520, border=True)
    with chat_container:
        for msg in st.session_state.copilot_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Quick chat ideas
    st.caption("💡 Try asking: *'Tell me which hosts are connected to s3'*, *'What active alerts do we have?'*, or *'How can I isolate s2?'*")

    # Chat input
    if prompt := st.chat_input("Ask anything about your network..."):
        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
        st.session_state.copilot_messages.append({"role": "user", "content": prompt})

        # Request response from chatbot backend
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    res = api_request("/copilot/chat", "POST", {
                        "message": prompt,
                        "history": st.session_state.copilot_messages[:-1]
                    })
                    if "error" in res:
                        response_text = f"⚠️ Could not complete LLM query: {res['error']}"
                    else:
                        response_text = res.get("response", "No response received.")
                    st.markdown(response_text)
        st.session_state.copilot_messages.append({"role": "assistant", "content": response_text})
        st.rerun()

# ==========================================
# Right Column: Visual Path Tracer
# ==========================================
with col_trace:
    st.subheader("🔍 Visual Path Tracer & Routing Planner")
    st.caption("Select source and destination endpoints to compute and trace traffic routing on the live topology graph.")

    # Fetch topology elements
    devices = api_request("/devices").get("devices", [])
    hosts = api_request("/hosts").get("hosts", [])
    links = api_request("/links").get("links", [])

    if not devices or not hosts:
        st.info("ℹ️ No switches or hosts found. Please verify Mininet is running and hosts are discovered.")
    else:
        # Build options list
        host_options = []
        host_map = {}
        for h in hosts:
            mac = h.get("mac", "")
            ips = h.get("ipAddresses", [])
            ip = ips[0] if ips else "N/A"
            name = h.get("name", mac[:8])
            label = f"{name} ({ip})"
            host_options.append(label)
            host_map[label] = f"host_{mac}"

        # Controls card
        with st.container(border=True):
            col_src, col_dst = st.columns(2)
            with col_src:
                src_label = st.selectbox("Source Host:", host_options, key="trace_src")
            with col_dst:
                dst_label = st.selectbox("Destination Host:", host_options, key="trace_dst")

            trace_button = st.button("🚀 Trace Traffic Routing Path", use_container_width=True, type="primary")

        # Compute Path using NetworkX fallback
        calculated_path = []
        path_str = ""

        if trace_button and src_label and dst_label:
            src_node = host_map.get(src_label)
            dst_node = host_map.get(dst_label)

            if src_node == dst_node:
                st.warning("⚠️ Source and destination hosts must be different!")
            else:
                # Build networkx graph
                G = nx.Graph()
                for d in devices:
                    G.add_node(d.get("id"))
                for h in hosts:
                    mac = h.get("mac", "")
                    loc = h.get("locations", [{}])[0]
                    switch = loc.get("elementId", "")
                    if switch:
                        h_id = f"host_{mac}"
                        G.add_node(h_id)
                        G.add_edge(h_id, switch)
                for l in links:
                    src = l.get("src", {}).get("device", "")
                    dst = l.get("dst", {}).get("device", "")
                    if src and dst:
                        G.add_edge(src, dst)

                try:
                    calculated_path = nx.shortest_path(G, src_node, dst_node)
                    # Convert to user-friendly path summary representation
                    path_steps = []
                    for idx, node in enumerate(calculated_path):
                        if node.startswith("host_"):
                            mac_part = node.replace("host_", "")
                            matching_host = next((h for h in hosts if h.get("mac") == mac_part), None)
                            name = matching_host.get("name", mac_part[:8]) if matching_host else mac_part[:8]
                            path_steps.append(f"🟢 **{name}**")
                        else:
                            switch_name = node[-2:]
                            path_steps.append(f" s{switch_name} ")
                    path_str = " ➡️ ".join(path_steps)
                except Exception as e:
                    st.error(f"❌ Could not calculate path: {e}")

        # Render visual graph HTML inside iframe
        # Generate Vis.js network representation
        nodes = []
        edges = []

        # Determine path nodes & edges for highlighting
        path_set = set(calculated_path)
        path_edges = set()
        if len(calculated_path) > 1:
            for idx in range(len(calculated_path) - 1):
                node_a = calculated_path[idx]
                node_b = calculated_path[idx + 1]
                path_edges.add(tuple(sorted([node_a, node_b])))

        # Add switches
        for d in devices:
            d_id = d.get("id", "")
            name = d.get("annotations", {}).get("name", d_id[-2:])
            is_on_path = d_id in path_set

            nodes.append({
                "id": d_id,
                "label": name,
                "color": "#00B0FF" if is_on_path else "#2196F3",
                "shape": "box",
                "size": 35 if is_on_path else 30,
                "shadow": {"enabled": is_on_path, "color": "#00B0FF", "size": 15},
                "font": {"color": "white", "size": 16 if is_on_path else 14, "bold": is_on_path}
            })

        # Add hosts
        for h in hosts:
            mac = h.get("mac", "")
            ips = h.get("ipAddresses", [])
            ip = ips[0] if ips else "N/A"
            name = h.get("name", mac[:8])
            h_id = f"host_{mac}"
            is_on_path = h_id in path_set

            nodes.append({
                "id": h_id,
                "label": f"{name}\n{ip}",
                "color": "#00E676" if is_on_path else "#4CAF50",
                "shape": "dot",
                "size": 25 if is_on_path else 20,
                "shadow": {"enabled": is_on_path, "color": "#00E676", "size": 15},
                "font": {"color": "black", "size": 13, "bold": is_on_path}
            })

            # Connect host to switch
            loc = h.get("locations", [{}])[0]
            switch = loc.get("elementId", "")
            if switch:
                edge_key = tuple(sorted([h_id, switch]))
                is_edge_on_path = edge_key in path_edges
                edges.append({
                    "from": h_id,
                    "to": switch,
                    "color": "#00E676" if is_edge_on_path else "#90CAF9",
                    "width": 5 if is_edge_on_path else 1,
                    "arrows": {"to": {"enabled": is_edge_on_path}} if is_edge_on_path else {},
                    "dashes": True if is_edge_on_path else False
                })

        # Add switch-to-switch links
        seen = set()
        for l in links:
            src = l.get("src", {}).get("device", "")
            dst = l.get("dst", {}).get("device", "")
            if not src or not dst:
                continue

            edge_key = tuple(sorted([src, dst]))
            if edge_key in seen:
                continue
            seen.add(edge_key)

            is_edge_on_path = edge_key in path_edges
            edges.append({
                "from": src,
                "to": dst,
                "color": "#00B0FF" if is_edge_on_path else "#666666",
                "width": 6 if is_edge_on_path else 3,
                "dashes": True if is_edge_on_path else False,
                "arrows": {"to": {"enabled": is_edge_on_path}} if is_edge_on_path else {}
            })

        # Render vis.js script
        nodes_json = json.dumps(nodes)
        edges_json = json.dumps(edges)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
            <style>
                #network {{
                    width: 100%;
                    height: 480px;
                    background-color: #F8F9FA;
                    border: 1px solid #E2E8F0;
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
                    nodes: {{
                        font: {{ face: 'Inter, sans-serif' }},
                        borderWidth: 2
                    }},
                    edges: {{
                        smooth: {{ type: 'cubicBezier', forceDirection: 'none', roundness: 0.5 }}
                    }},
                    physics: {{
                        forceAtlas2Based: {{
                            gravitationalConstant: -50,
                            centralGravity: 0.01,
                            springLength: 95,
                            springConstant: 0.08
                        }},
                        solver: 'forceAtlas2Based',
                        stabilization: {{ iterations: 150 }}
                    }}
                }};
                var network = new vis.Network(container, data, options);
            </script>
        </body>
        </html>
        """

        # Display route roadmap if computed
        if path_str:
            st.success("🟢 Active Traffic Route Found!")
            st.markdown(f"**Route Roadmap**: {path_str}")

        # Render graph
        components.html(html_content, height=500)
