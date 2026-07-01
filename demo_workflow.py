#!/usr/bin/env python3
"""
Comprehensive Demo of LLM-NetAuto-SDN End-to-End Workflow.

Demonstrates:
1. Natural language intent submission
2. LLM parsing via Ollama
3. Intent validation
4. RAG similarity matching
5. ONOS deployment
6. Result tracking
"""

import requests
import json
import time
from typing import Any, Dict
from datetime import datetime

# Configuration
API_URL = "http://127.0.0.1:8000"
DEMO_INTENTS = [
    "Block all traffic from 10.0.0.1",
    "Allow HTTP traffic from h1 to h3",
    "Prioritize VoIP traffic on UDP port 5060",
    "Drop all ICMP packets on s2",
    "Rate limit h5 to 10 Mbps",
    "Isolate switch s2 from the network",
    "Mirror all traffic on s1 to port 5",
    "Allow only SSH between h2 and h4"
]


def print_header(title: str):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_section(title: str):
    """Print formatted section."""
    print(f"\n▶ {title}")
    print("-" * 70)


def check_backend():
    """Check if backend is healthy."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=30)
        data = r.json()
        print_section("Backend Health Check")
        print(f"Status: {data.get('status')}")
        print(f"Mode: {'Demo' if data.get('demo_mode') else 'Live'}")
        print(f"Uptime: {data.get('uptime_seconds', 0):.1f}s")
        return True
    except Exception as e:
        print(f"❌ Backend not responding: {e}")
        return False


def get_topology():
    """Get current network topology."""
    try:
        r = requests.get(f"{API_URL}/topology", timeout=30)
        data = r.json()
        print_section("Network Topology")
        print(f"Devices: {len(data.get('devices', []))}")
        print(f"Hosts: {len(data.get('hosts', []))}")
        print(f"Links: {len(data.get('links', []))}")
        return data
    except Exception as e:
        print(f"❌ Failed to get topology: {e}")
        return {}


def submit_intent(intent_text: str) -> Dict[str, Any]:
    """Submit an intent to the system."""
    try:
        print_section(f"Submitting Intent: {intent_text}")

        start_time = time.time()
        r = requests.post(
            f"{API_URL}/intent",
            json={"intent": intent_text},
            timeout=60
        )
        elapsed = (time.time() - start_time) * 1000

        if r.status_code == 200:
            result = r.json()

            # Display results
            print(f"✅ Status: {'SUCCESS' if result.get('success') else 'FAILED'}")
            print(f"⏱️  Latency: {result.get('latency_ms', elapsed):.0f}ms")
            print(f"📋 Method: {result.get('deployment_method', 'none')}")

            # Summary
            if result.get('summary'):
                print(f"📝 Summary: {result.get('summary')}")

            # Validation
            if result.get('validation'):
                val = result.get('validation')
                print(f"✓ Validation: {'PASSED' if val.get('valid') else 'FAILED'}")

            # Parsed rule
            if result.get('parsed_rule'):
                print(f"📊 Parsed Rule:")
                rule = result.get('parsed_rule')
                for key, value in rule.items():
                    if key not in ['metadata', 'actions']:
                        print(f"   - {key}: {value}")

            # Similar intents from RAG
            similar = result.get('similar_past_intents', [])
            if similar:
                print(f"🔍 Similar Intents Found:")
                for i, sim in enumerate(similar[:3], 1):
                    print(f"   {i}. {sim.get('intent', 'N/A')} (type: {sim.get('type', 'unknown')})")

            return result
        else:
            print(f"❌ Error: HTTP {r.status_code}")
            print(f"   {r.text[:200]}")
            return {"error": r.text, "success": False}

    except Exception as e:
        print(f"❌ Failed to submit intent: {e}")
        return {"error": str(e), "success": False}


def get_rag_stats():
    """Get RAG engine statistics."""
    try:
        r = requests.get(f"{API_URL}/rag/stats", timeout=10)
        data = r.json()
        print_section("RAG Engine Statistics")

        if "error" not in data:
            print(f"Total Intents Indexed: {data.get('total_intents', 0)}")
            print(f"Collections: {data.get('collections', 0)}")
            print(f"Embeddings Cached: {data.get('embeddings_cached', 0)}")
        else:
            print(f"Could not retrieve RAG stats: {data.get('error')}")
        return data
    except Exception as e:
        print(f"❌ Failed to get RAG stats: {e}")
        return {}


def get_service_status():
    """Get status of all services."""
    print_section("Service Status")

    services = {
        "FastAPI": f"{API_URL}/health",
        "ONOS": "http://127.0.0.1:8181/onos/v1/cluster",
        "ChromaDB": "http://127.0.0.1:8001/api/v2/heartbeat",
        "Ollama": "http://127.0.0.1:11434/api/tags",
        "Prometheus": "http://127.0.0.1:9090/-/healthy",
        "Grafana": "http://127.0.0.1:3000/api/health"
    }

    for name, url in services.items():
        try:
            if name == "ONOS":
                r = requests.get(url, auth=('onos', 'rocks'), timeout=2)
            else:
                r = requests.get(url, timeout=2)
            status = "✅" if r.status_code == 200 else "❌"
        except:
            status = "❌"
        print(f"{status} {name}")


def run_demo():
    """Run complete demonstration."""
    print_header("LLM-NetAuto-SDN: Complete Workflow Demo")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check backend
    if not check_backend():
        print("\n❌ Backend is not responding. Please start the services first.")
        return

    # Get service status
    get_service_status()

    # Get RAG stats (initial)
    get_rag_stats()

    # Get topology
    get_topology()

    # Submit demo intents
    print_header("Intent Submission Examples")
    print(f"Submitting {len(DEMO_INTENTS)} sample intents...")

    results = []
    for i, intent in enumerate(DEMO_INTENTS[:3], 1):  # First 3 for demo
        print(f"\n[{i}/{len(DEMO_INTENTS[:3])}]")
        result = submit_intent(intent)
        results.append({
            "intent": intent,
            "result": result,
            "success": result.get("success", False)
        })
        time.sleep(1)  # Rate limiting

    # Summary
    print_header("Demo Summary")
    successful = sum(1 for r in results if r["success"])
    print(f"Total Intents Submitted: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")

    # Get final RAG stats
    print("\n")
    get_rag_stats()

    # Instructions
    print_header("Next Steps")
    print("""
1. Dashboard:
   - Open http://localhost:8501
   - Go to "Intent Control" page
   - Submit your own intents in natural language

2. API Testing:
   - Open http://localhost:8000/docs
   - Test endpoints interactively
   - Submit custom intents via /intent endpoint

3. Monitoring:
   - View metrics in Grafana: http://localhost:3000
   - Check Prometheus: http://localhost:9090

4. System Configuration:
   - Edit .env for different settings
   - Use demo mode for simulation
   - Switch to live mode with real ONOS

5. About LLM:
   - System uses Ollama + llama3 for intent parsing
   - Intents are stored in ChromaDB for RAG similarity
   - Each intent goes through LLM -> Rule Parser -> ONOS Deployment
    """)

    print_header("Demo Complete")
    print(f"Ended at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    run_demo()
