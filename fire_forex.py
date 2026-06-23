import asyncio
import httpx
import json

def unfreeze():
    try:
        with open("dynamic_risk_params.json", "r") as f:
            data = json.load(f)
        data["health_size_multiplier"] = 1.0
        with open("dynamic_risk_params.json", "w") as f:
            json.dump(data, f, indent=4)
        print("Unfroze SRE Execution.")
    except Exception as e:
        print(f"Failed to unfreeze: {e}")

async def fire():
    unfreeze()
    signals = [
        {"symbol": "USDHKD", "direction": "BUY", "conviction": 0.85, "strategy_type": "MOMENTUM", "applied_dynamic_gate": 0.50, "override_lot": 0.01, "xgb_p": 0.9, "ddqn_p": 0.9, "wasserstein_state": "TREND"},
        {"symbol": "CHFJPY", "direction": "BUY", "conviction": 0.85, "strategy_type": "MOMENTUM", "applied_dynamic_gate": 0.50, "override_lot": 0.01, "xgb_p": 0.9, "ddqn_p": 0.9, "wasserstein_state": "TREND"}
    ]
    
    url = "http://127.0.0.1:8000/execute_trade"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for sig in signals:
            try:
                resp = await client.post(url, json=sig)
                print(f"[{sig['symbol']}] Response: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"[{sig['symbol']}] Error: {e}")

if __name__ == "__main__":
    asyncio.run(fire())
