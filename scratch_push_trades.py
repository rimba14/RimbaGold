import requests
import os
import time
from dotenv import load_dotenv

load_dotenv(r"C:\Users\ADMIN\.antigravity\rimba-trading\.env")

api_key = os.getenv("SENTINEL_API_KEY")
headers = {"X-API-Key": api_key} if api_key else {}

trades = [
    # Binance (8002)
    {"target": "binance", "url": "http://127.0.0.1:8002/execute_trade", "payload": {"symbol": "BTCUSD", "direction": "BUY", "conviction": 0.671, "override_lot": 0.01}},
    {"target": "binance", "url": "http://127.0.0.1:8002/execute_trade", "payload": {"symbol": "ETHUSD", "direction": "BUY", "conviction": 0.667, "override_lot": 0.25}},
    
    # MT5 (8000)
    {"target": "mt5", "url": "http://127.0.0.1:8000/execute_trade", "payload": {"symbol": "GBPJPY", "direction": "SELL", "conviction": 0.659, "override_lot": 0.01}},
    {"target": "mt5", "url": "http://127.0.0.1:8000/execute_trade", "payload": {"symbol": "USDSGD", "direction": "SELL", "conviction": 0.658, "override_lot": 0.02}},
]

for t in trades:
    print(f"Pushing {t['payload']['symbol']} to {t['target']}...")
    try:
        resp = requests.post(t["url"], json=t["payload"], headers=headers)
        if resp.status_code == 200:
            print(f"[SUCCESS] {t['payload']['symbol']} dispatched. Response: {resp.json()}")
        else:
            print(f"[REJECTED] {t['payload']['symbol']} failed with HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[ERROR] {t['payload']['symbol']} connection failed: {e}")
    time.sleep(1)
