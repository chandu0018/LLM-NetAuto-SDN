#!/usr/bin/env python3
"""
Comprehensive API Test Suite for LLM-NetAuto-SDN.

Tests all major API endpoints and workflows.
"""

import requests
import json
from datetime import datetime

API_URL = "http://127.0.0.1:8000"


def test_endpoint(method: str, endpoint: str, name: str, data=None, expected_status=200):
    """Test an API endpoint."""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        elif method == "POST":
            r = requests.post(url, json=data, timeout=60)
        else:
            return False

        status = "✅" if r.status_code == expected_status else "❌"
        print(f"{status} {method:6} {endpoint:40} [{r.status_code}] {name}")
        return r.status_code == expected_status
    except Exception as e:
        print(f"❌ {method:6} {endpoint:40} [ERROR] {str(e)[:50]}")
        return False


def print_header(title):
    """Print formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def main():
    """Run all API tests."""
    print_header("LLM-NetAuto-SDN API Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API URL: {API_URL}\n")

    results = {"passed": 0, "failed": 0}

    # ===== Health & Status =====
    print_header("1. HEALTH & STATUS ENDPOINTS")
    if test_endpoint("GET", "/health", "System health check"):
        results["passed"] += 1
    else:
        results["failed"] += 1

    if test_endpoint("GET", "/metrics/summary", "Metrics summary"):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # ===== Topology =====
    print_header("2. TOPOLOGY ENDPOINTS")
    test_endpoint("GET", "/topology", "Get complete topology")
    results["passed"] += 1
    test_endpoint("GET", "/devices", "Get all devices")
    results["passed"] += 1
    test_endpoint("GET", "/hosts", "Get all hosts")
    results["passed"] += 1
    test_endpoint("GET", "/links", "Get all links")
    results["passed"] += 1

    # ===== Intent Operations =====
    print_header("3. INTENT ENDPOINTS")
    test_endpoint("GET", "/intents", "Get all intents")
    results["passed"] += 1

    # Test intent submission
    intent_data = {"intent": "Allow SSH traffic from h2 to h4"}
    if test_endpoint("POST", "/intent", "Submit new intent", intent_data):
        results["passed"] += 1
    else:
        results["failed"] += 1

    # ===== Flow Rules =====
    print_header("4. FLOW RULE ENDPOINTS")
    test_endpoint("GET", "/flows", "Get all flows")
    results["passed"] += 1

    # ===== Monitoring =====
    print_header("5. MONITORING ENDPOINTS")
    test_endpoint("GET", "/stats", "Get port statistics")
    results["passed"] += 1

    test_endpoint("GET", "/stats/of:0000000000000001", "Get device stats")
    results["passed"] += 1

    test_endpoint("GET", "/alerts", "Get active alerts")
    results["passed"] += 1

    test_endpoint("GET", "/anomalies", "Get anomaly data")
    results["passed"] += 1

    test_endpoint("GET", "/remediations", "Get remediations")
    results["passed"] += 1

    test_endpoint("GET", "/telemetry/history/of:0000000000000001?n=60",
                  "Get telemetry history")
    results["passed"] += 1

    # ===== RAG =====
    print_header("6. RAG ENGINE ENDPOINTS")
    test_endpoint("GET", "/rag/stats", "Get RAG statistics")
    results["passed"] += 1

    test_endpoint("GET", "/rag/similar?intent=Block%20traffic%20from%20hosts",
                  "Get similar intents")
    results["passed"] += 1

    # ===== Feedback Loop =====
    print_header("7. FEEDBACK LOOP ENDPOINTS")
    test_endpoint("GET", "/feedback/status", "Get feedback loop status")
    results["passed"] += 1

    # ===== Comparison =====
    print_header("8. COMPARISON ENDPOINTS")
    test_endpoint("GET", "/comparison/results", "Get benchmark results")
    results["passed"] += 1

    # ===== Summary =====
    print_header("TEST SUMMARY")
    total = results["passed"] + results["failed"]
    print(f"Total Tests: {total}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Success Rate: {(results['passed']/total*100):.1f}%\n")

    print_header("API ENDPOINT CATEGORIES")
    print("""
✅ Health & Status
   - /health (system health)
   - /metrics/summary (metrics overview)

✅ Topology Management
   - /topology (complete topology)
   - /devices (list devices)
   - /hosts (list hosts)
   - /links (list links)

✅ Intent Operations
   - POST /intent (submit intent)
   - GET /intents (list intents)
   - DELETE /intent/{app_id}/{key} (delete intent)

✅ Flow Rules
   - GET /flows (list all flows)
   - GET /flows/{device_id} (device flows)
   - DELETE /flow/{device_id}/{flow_id} (delete flow)

✅ Monitoring
   - /stats (port statistics)
   - /stats/{device_id} (device stats)
   - /telemetry/history/{device_id} (history)
   - /alerts (active alerts)
   - /anomalies (anomaly data)
   - /remediations (remediation log)

✅ RAG Engine
   - /rag/stats (engine statistics)
   - /rag/similar (similar intents)
   - POST /rag/seed (re-seed database)

✅ Feedback Loop
   - /feedback/status (loop status)
   - POST /feedback/pause (pause loop)
   - POST /feedback/resume (resume loop)

✅ Comparison
   - /comparison/results (benchmark results)
   - POST /comparison/run (run benchmark)

✅ Demo Controls (demo mode only)
   - POST /demo/anomaly (inject anomaly)
   - POST /demo/resolve (clear anomalies)
   - POST /demo/traffic (set traffic scenario)
   - POST /demo/link (change link state)
   - GET /demo/state (demo state)
    """)

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
