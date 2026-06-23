import MetaTrader5 as mt5
from arcticdb import Arctic
import math

mt5.initialize()
store = Arctic("lmdb://C:/Sentinel_Project/data/arctic_cache")
lib = store["oracle_cache"]

# Known non-forex bases to filter out
non_forex_keys = {"BTC", "ETH", "SOL", "AVAX", "LINK", "LTC", "BCH", "XRP", "ADA", "DOT", "MATIC", "DOGE", "UNI", "ATOM", "TRX", "XAU", "XAG", "US30", "NAS100", "SPX", "US2000", "GER40", "HK50", "GOLD", "SILVER", "OIL", "FRA40", "EU50", "UK100", "JPN225", "AUS200"}

assets = []
for sym in lib.list_symbols():
    if sym.endswith("_meta"):
        base_sym = sym.replace("_meta", "")
        
        # Filter for forex only
        if any(k in base_sym.upper() for k in non_forex_keys) or len(base_sym) > 6:
            continue
            
        data = lib.read(sym).data
        if not data.empty:
            row = data.iloc[-1]
            p_val = float(row.get("meta_conviction", row.get("xgb_p", 0.5)))
            
            hmm_state = str(row.get("wasserstein_state", "RANGE")).upper()
            if p_val == 0.0 or p_val == 0.5 or "STAGNANT" in hmm_state or "CLOSED" in hmm_state or "QUARANTINE" in hmm_state:
                continue
                
            direction = "BUY" if p_val >= 0.5 else "SELL"
            conviction = p_val if direction == "BUY" else (1.0 - p_val)
            
            if conviction >= 0.5:
                assets.append({
                    "symbol": base_sym,
                    "direction": direction,
                    "conviction": conviction,
                    "hmm": row.get("wasserstein_state", "RANGE")
                })

assets = sorted(assets, key=lambda x: x["conviction"], reverse=True)[:5]

if len(assets) == 0:
    print("No ready Forex trades found.")
else:
    print("\n--- TOP 5 READY FOREX TRADES ---")
    for a in assets:
        print(f"Asset: {a['symbol']}")
        print(f"Thesis: {a['hmm']} | Direction: {a['direction']} | Conviction: {a['conviction']:.3f}")
        print("---------------------------------")
