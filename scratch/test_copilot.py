import requests
import json

BASE_URL = "http://localhost:8000"

def test_copilot():
    print("🚀 Test: Querying the AI Copilot Chat API with exact user questions...\n")
    url = f"{BASE_URL}/copilot/chat"
    
    questions = [
        "Tell me which hosts are connected to s3",
        "How can I isolate s2?",
        "What active alerts do we have?"
    ]
    
    for q in questions:
        print(f"👉 Question: '{q}'")
        payload = {
            "message": q,
            "history": []
        }
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                res = r.json()
                print(f"💬 Answer:\n{res.get('response')}\n")
                print("-" * 50)
            else:
                print(f"❌ Error: HTTP {r.status_code}\n")
        except Exception as e:
            print(f"❌ Exception: {e}\n")

if __name__ == "__main__":
    test_copilot()
