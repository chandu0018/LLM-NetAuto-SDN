import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_mirror():
    print("🚀 Test 1: Posting 'Mirror all traffic on s1 to port 5' to /intent API...")
    url = f"{BASE_URL}/intent"
    payload = {"intent": "Mirror all traffic on s1 to port 5"}
    
    try:
        r = requests.post(url, json=payload)
        print(f"Status Code: {r.status_code}")
        res = r.json()
        print("Response JSON:")
        print(json.dumps(res, indent=2))
        
        if res.get("success"):
            print("✅ Mirror intent parsed and deployed successfully!")
            
            # Wait for ONOS to register the flow rule
            print("\n⏳ Sleeping 3 seconds for ONOS to register flow rule...")
            time.sleep(3)
            
            # Fetch active flows to verify the rule exists
            print("\n🚀 Test 2: Fetching active flows from backend...")
            flows_res = requests.get(f"{BASE_URL}/flows").json()
            flows = flows_res.get("flows", [])
            mirror_flows = [f for f in flows if f.get("appId") == "org.onosproject.cli"]
            
            if mirror_flows:
                print(f"✅ Discovered {len(mirror_flows)} active custom mirror flows:")
                for f in mirror_flows:
                    print(f"  - Device: {f.get('deviceId')}, FlowID: {f.get('id')}, Action: {f.get('treatment', {}).get('instructions', [])}")
                
                # Check if it targets s1 (of:0000000000000001)
                s1_flows = [f for f in mirror_flows if "0000000000000001" in f.get("deviceId", "")]
                if len(s1_flows) == len(mirror_flows):
                    print("✅ Perfect! Mirror rule targeted ONLY switch s1!")
                else:
                    print("❌ Warning: Mirror rule targeted other switches too!")
            else:
                print("❌ No mirror flows found on switches!")
                
            # Clean up
            print("\n🚀 Test 3: Purging mirror rules via /intent/clear-all...")
            clear_res = requests.post(f"{BASE_URL}/intent/clear-all").json()
            print(f"Clear All Response: {clear_res}")
        else:
            print(f"❌ Failed to deploy mirror intent: {res.get('error')}")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_mirror()
