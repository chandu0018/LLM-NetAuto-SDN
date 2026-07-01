import os
from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import OllamaLLM
llm = OllamaLLM(
    model="llama3.2:1b",
    base_url="http://127.0.0.1:11434",
    temperature=0.1
)

ctx = (
    "LIVE NETWORK TELEMETRY CONTEXT:\n"
    "- Active Switches (3): s1 (🟢 Available), s2 (🟢 Available), s3 (🟢 Available)\n"
    "- Hosts Discovered (6): 10.0.0.6 (MAC: 00:00:00:00:00:06) ➡️ s3, 10.0.0.5 (MAC: 00:00:00:00:00:05) ➡️ s3, 10.0.0.3 (MAC: 00:00:00:00:00:03) ➡️ s2, 10.0.0.4 (MAC: 00:00:00:00:00:04) ➡️ s2, 10.0.0.1 (MAC: 00:00:00:00:00:01) ➡️ s1, 10.0.0.2 (MAC: 00:00:00:00:00:02) ➡️ s1\n"
    "- Topology Links (6): s1 ➡️ s2, s2 ➡️ s3, s3 ➡️ s1\n"
    "- Alert Manager active alerts: No active alerts (Network Healthy 🟢)\n"
    "- Anomaly Detector state: No anomalies detected\n"
)

prompt = (
    f"You are an SDN AI Copilot, a highly intelligent conversational network assistant for LLM-NetAuto-SDN.\n"
    f"Use the following dynamic system status to answer the user's question accurately.\n\n"
    f"{ctx}\n\n"
    f"CRITICAL GUIDELINES:\n"
    f"1. Be extremely brief, concise, and specific. Keep your entire response under 2 sentences.\n"
    f"2. If asked which hosts are connected to s3, simply list only the hosts that are explicitly connected to s3 in the context (10.0.0.5 and 10.0.0.6).\n"
    f"3. Do not ramble, do not list other hosts, and do not explain the network.\n\n"
    f"User: Tell me which hosts are connected to s3\n"
    f"Assistant:"
)

import time
start = time.time()
print("Invoking llama3.2:1b with hyper-brief prompt...")
res = llm.invoke(prompt)
end = time.time()
print("Response:\n", res)
print(f"\nTime taken: {end - start:.2f} seconds")
