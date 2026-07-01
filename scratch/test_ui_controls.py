import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(method, path, data=None):
    url = f"{BASE_URL}{path}"
    print(f"\n🚀 Testing {method} {path}...")
    try:
        if method == "POST":
            r = requests.post(url, json=data)
        else:
            r = requests.get(url)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.json()}")
        return r.json()
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# 1. Test clear all initial
test_endpoint("POST", "/intent/clear-all")

# 2. Test generate traffic
gen_res = test_endpoint("POST", "/topology/generate-traffic")
if gen_res and gen_res.get("success"):
    print("✅ Generate traffic works perfectly!")
else:
    print("❌ Generate traffic failed!")

time.sleep(2)

# 3. Test stop traffic
stop_res = test_endpoint("POST", "/topology/stop-traffic")
if stop_res and stop_res.get("success"):
    print("✅ Stop traffic works perfectly!")
else:
    print("❌ Stop traffic failed!")

# 4. Test clear all final
clear_res = test_endpoint("POST", "/intent/clear-all")
if clear_res and clear_res.get("success"):
    print("✅ Clear all intents works perfectly!")
else:
    print("❌ Clear all intents failed!")
