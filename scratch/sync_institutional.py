import MetaTrader5 as mt5
import json
import logging
import numpy as np

import config as cfg
from zone.zone_detector import build_zones
from zone.tp_calculator import calculate_trade_plan

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sync_institutional")

def run():
    if not mt5.initialize():
        log.error("MT5 init failed")
        return

    pos = mt5.positions_get(symbol="XAUUSD")
    if not pos:
        log.error("No active trades found in MT5!")
        return

    p = pos[0]
    ticket = p.ticket
    direction = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
    entry_price = p.price_open
    lot_size = p.volume

    log.info(f"Evaluating orphaned ticket #{ticket} ({direction} @ {entry_price}) against NEW Institutional Bounds.")

    # 1. Pull market data
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 500)
    if rates is None or len(rates) < 100:
        log.error("Failed to get MT5 rates")
        return
        
    times = np.array([r['time'] for r in rates])
    opens = np.array([r['open'] for r in rates])
    highs = np.array([r['high'] for r in rates])
    lows = np.array([r['low'] for r in rates])
    closes = np.array([r['close'] for r in rates])

    d1_atr = 25.0
    
    # 2. Detect zones using the NEW config (which has ZONE_MIN_W_ATR=0.15)
    all_zones = build_zones(times=times, opens=opens, highs=highs, lows=lows, closes=closes, d1_atr=d1_atr, tf="M5")
    
    target_type = "DEMAND" if direction == "BUY" else "SUPPLY"
    target_zones = [z for z in all_zones if z.zone_type.value == target_type]
    
    if not target_zones:
        log.warning(f"No institutional {target_type} zones detected! Defaulting to massive proxy zone.")
        zone_width = d1_atr * cfg.ZONE_MIN_W_ATR
        if direction == "SELL":
            zone_edge = entry_price + (zone_width / 2.0)
        else:
            zone_edge = entry_price - (zone_width / 2.0)
    else:
        target_zones.sort(key=lambda z: abs(z.high - entry_price) if direction == "BUY" else abs(z.low - entry_price))
        active_zone = target_zones[0]
        zone_width = active_zone.width
        zone_edge = active_zone.low if direction == "BUY" else active_zone.high
        log.info(f"Detected Institutional {target_type} Zone: Width = {zone_width:.2f}")

    # 3. Calculate SL (2x Zone Width beyond edge)
    if direction == "SELL":
        sl = zone_edge + (2.0 * zone_width)
        risk_pts = sl - entry_price
        if risk_pts <= 0: risk_pts = 10.0
        tp_ladder = [entry_price - (risk_pts * m) for m in cfg.TP_MULTIPLES]
    else:
        sl = zone_edge - (2.0 * zone_width)
        risk_pts = entry_price - sl
        if risk_pts <= 0: risk_pts = 10.0
        tp_ladder = [entry_price + (risk_pts * m) for m in cfg.TP_MULTIPLES]

    log.info(f"New Institutional SL: {sl:.2f}")
    log.info(f"New Institutional TP Ladder: {[round(x, 2) for x in tp_ladder]}")
    
    tick = mt5.symbol_info_tick("XAUUSD")
    
    # To avoid "Invalid stops", ensure TP is valid
    valid_tp = tp_ladder[0]
    if direction == "SELL":
        for tp in tp_ladder:
            if tp < tick.ask - 0.5:
                valid_tp = tp
                break
    else:
        for tp in tp_ladder:
            if tp > tick.bid + 0.5:
                valid_tp = tp
                break

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "XAUUSD",
        "position": ticket,
        "sl": float(sl),
        "tp": float(valid_tp),
    }
    
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"Successfully synced MT5 SL/TP to Institutional Bounds!")
    else:
        err = res.comment if res else "Unknown"
        log.error(f"Failed to update MT5: {err}")

    # Update python state
    state_obj = {
        "is_active": True,
        "ticket": ticket,
        "direction": direction,
        "lot_size": lot_size,
        "open_price": entry_price,
        "sl_price": sl,
        "tp_prices": tp_ladder,
        "tp_index": 0,
        "flip_pending": False,
        "floating_pnl": 0.0
    }
    with open("state/gold_position_state.json", "w") as f:
        json.dump(state_obj, f)
    with open("gold_position_state.json", "w") as f:
        json.dump(state_obj, f)

if __name__ == "__main__":
    run()
