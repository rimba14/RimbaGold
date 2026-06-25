import os
import sys
import math
import logging
from arcticdb import Arctic
import MetaTrader5 as mt5

sys.path.append("C:/Sentinel_Project")
try:
    from tp_placement_engine import TPPlacementEngine, StructuralLevelResolver

    class MT5OracleWrapper:
        def get_bars(self, symbol, timeframe, count):
            import MetaTrader5 as mt5
            tf = mt5.TIMEFRAME_D1 if timeframe == "D1" else mt5.TIMEFRAME_H4
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None: return []
            return [{"high": r[2], "low": r[3], "close": r[4]} for r in rates]

        def get_atr(self, symbol, timeframe, period, max_age_seconds):
            import MetaTrader5 as mt5
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, period + 1)
            if rates is None or len(rates) < 2: return 0.0
            highs = [r[2] for r in rates]
            lows = [r[3] for r in rates]
            closes = [r[4] for r in rates]
            atr = sum([
                max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                for i in range(1, len(rates))
            ]) / (len(rates) - 1)
            return atr

    oracle_wrapper = MT5OracleWrapper()
    level_resolver = StructuralLevelResolver(oracle_wrapper)
    tp_engine = TPPlacementEngine(oracle_wrapper, level_resolver)
except ImportError:
    print("[WARNING] Could not load tp_placement_engine. ZETA validation might fail.")
    tp_engine = None

ARCTIC_URI = "lmdb://C:/Sentinel_Project/data/arctic_cache"
MAGIC_NUMBER = 777777

if not mt5.initialize():
    print("MT5 initialization failed")
    quit()

store = Arctic(ARCTIC_URI)
lib   = store["oracle_cache"]
acc   = mt5.account_info()

target_symbols = ["GBPUSD", "GBPJPY", "EURGBP"]
assets = []

for sym in lib.list_symbols():
    if not sym.endswith("_meta"):
        continue
    base_sym = sym.replace("_meta", "")
    if base_sym not in target_symbols:
        continue

    data = lib.read(sym).data
    if data.empty:
        continue
        
    row = data.iloc[-1]
    p_val = float(row.get("meta_conviction", row.get("xgb_p", 0.5)))
    hmm_state = str(row.get("wasserstein_state", "RANGE")).upper()

    direction  = "BUY" if p_val >= 0.5 else "SELL"
    conviction = p_val if direction == "BUY" else (1.0 - p_val)

    assets.append({
        "symbol":    base_sym,
        "direction": direction,
        "conviction": conviction,
        "hmm":       row.get("wasserstein_state", "RANGE"),
        "atr":       float(row.get("atr", 0.0)),
    })

print(f"\n--- MANUAL EXECUTION FOR ZETA COMPLIANT TRADES ---")
for a in assets:
    sym       = a["symbol"]
    direction = a["direction"]
    conviction = a["conviction"]

    if not mt5.symbol_select(sym, True):
        print(f"[SKIP] {sym}: symbol not available in terminal")
        continue

    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if not info or not tick:
        print(f"[SKIP] {sym}: no tick data")
        continue

    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 16)
    if rates is None or len(rates) < 2:
        print(f"[SKIP] {sym}: insufficient rate history")
        continue

    highs  = [r[2] for r in rates]
    lows   = [r[3] for r in rates]
    closes = [r[4] for r in rates]
    atr    = sum([
        max(highs[i] - lows[i],
            abs(highs[i]  - closes[i-1]),
            abs(lows[i]   - closes[i-1]))
        for i in range(1, len(rates))
    ]) / (len(rates) - 1)

    mult = 6.0
    sl_dist = atr * mult
    tp_dist = sl_dist * 1.5

    price  = tick.ask if direction == "BUY" else tick.bid
    digits = info.digits
    sl     = round(price - sl_dist if direction == "BUY" else price + sl_dist, digits)
    tp     = round(price + tp_dist if direction == "BUY" else price - tp_dist, digits)

    spread = tick.ask - tick.bid
    if direction == "BUY" and (tick.ask - sl) < spread * 1.5:
        sl = round(tick.ask - spread * 1.5, digits)
        tp = round(tick.ask + spread * 2.5, digits)
    elif direction == "SELL" and (sl - tick.bid) < spread * 1.5:
        sl = round(tick.bid + spread * 1.5, digits)
        tp = round(tick.bid - spread * 2.5, digits)

    dir_int = 1 if direction == "BUY" else -1
    
    val_res = tp_engine.validate_tp_placement(
        symbol=sym,
        entry=price,
        sl=sl,
        proposed_tp=tp,
        direction=dir_int
    )
    if not val_res.is_valid:
        print(f"[ZETA REJECT] {sym} {direction} - {val_res.rejection_reason}")
        continue
    if val_res.final_tp is not None:
        tp = round(val_res.final_tp, digits)
        print(f"[ZETA OK] {sym} TP set structurally to {tp}")

    sl_dist_points = sl_dist / (info.point + 1e-12)
    point_val      = info.trade_tick_value / (info.trade_tick_size / info.point + 1e-12)
    risk_usd       = acc.balance * 0.02 * 0.5
    raw_lot        = risk_usd / (sl_dist_points * point_val + 1e-12)
    lot            = math.floor(raw_lot / info.volume_step) * info.volume_step
    if lot <= 0:
        lot = info.volume_min

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action":      mt5.TRADE_ACTION_DEAL,
        "symbol":      sym,
        "volume":      lot,
        "type":        order_type,
        "price":       price,
        "sl":          sl,
        "tp":          tp,
        "deviation":   20,
        "magic":       MAGIC_NUMBER,
        "comment":     f"Sentinel|{conviction:.2f}",
        "type_time":   mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[FAILED]  {sym} {direction} | retcode={result.retcode} | {result.comment}")
    else:
        print(f"[SUCCESS] {sym} {direction} | entry={price} | SL={sl} | TP={tp} | lot={lot} | conviction={conviction:.3f}")

mt5.shutdown()
print("\n--- EXECUTION COMPLETE ---")
