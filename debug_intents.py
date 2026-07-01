#!/usr/bin/env python3
"""Debug script to test intent submission and retrieval."""

import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

API_URL = f"http://127.0.0.1:{os.getenv('FASTAPI_PORT', '8000')}"

def test_intent_flow():
    """Test the full intent submission and retrieval flow."""
    print("=" * 60)
    print("INTENT DEBUG TEST")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Health Check:")
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        print(f"   Status: {r.status_code}")
        print(f"   Demo Mode: {r.json().get('demo_mode')}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test 2: Check initial intents
    print("\n2. Initial Intents:")
    r = requests.get(f"{API_URL}/intents", timeout=5)
    intents = r.json().get('intents', [])
    print(f"   Count: {len(intents)}")
    print(f"   Intents: {json.dumps(intents, indent=2)}")
    
    # Test 3: Check initial history
    print("\n3. Initial History:")
    r = requests.get(f"{API_URL}/intent/history", timeout=5)
    history = r.json().get('history', [])
    print(f"   Count: {len(history)}")
    print(f"   History: {json.dumps(history, indent=2)}")
    
    # Test 4: Submit an intent
    print("\n4. Submit Intent:")
    intent_text = "Block all traffic from 10.0.0.1"
    print(f"   Intent: {intent_text}")
    
    r = requests.post(
        f"{API_URL}/intent",
        json={"intent": intent_text},
        timeout=30
    )
    
    print(f"   Status: {r.status_code}")
    response = r.json()
    print(f"   Success: {response.get('success')}")
    print(f"   Deployment Method: {response.get('deployment_method')}")
    print(f"   Summary: {response.get('summary')}")
    print(f"   Full Response: {json.dumps(response, indent=2)}")
    
    # Test 5: Check updated history
    print("\n5. Updated History:")
    r = requests.get(f"{API_URL}/intent/history", timeout=5)
    history = r.json().get('history', [])
    print(f"   Count: {len(history)}")
    print(f"   History: {json.dumps(history, indent=2)}")
    
    # Test 6: Check updated intents
    print("\n6. Updated ONOS Intents:")
    r = requests.get(f"{API_URL}/intents", timeout=5)
    intents = r.json().get('intents', [])
    print(f"   Count: {len(intents)}")
    print(f"   Intents: {json.dumps(intents, indent=2)}")
    
    print("\n" + "=" * 60)
    print("END DEBUG TEST")
    print("=" * 60)

if __name__ == "__main__":
    test_intent_flow()
