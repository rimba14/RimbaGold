import MetaTrader5 as mt5
import json
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sync_orphaned")

def run():
    if not mt5.initialize():
        log.error("MT5 init failed")
        return

    pos = mt5.positions_get(symbol="XAUUSD")
    if not pos:
        log.error("No active trades found in MT5!")
        return

    # Take the first open XAUUSD position
    p = pos[0]
    ticket = p.ticket
    direction = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
    entry_price = p.price_open
    lot_size = p.volume

    log.info(f"Found orphaned ticket #{ticket} ({direction} @ {entry_price}).")

    # Let's calculate a proxy zone width from recent D1 or H1 ATR, or just use 10.0 points
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 20)
    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    recent_high = max(highs)
    recent_low = min(lows)
    
    if direction == "SELL":
        # Supply zone was probably around recent high
        zone_high = recent_high + 1.0
        zone_low = recent_high - 2.0
        zone_width = zone_high - zone_low
        if zone_width <= 0: zone_width = 3.0
        
        sl = zone_high + (2.0 * zone_width)
        risk_pts = sl - entry_price
        if risk_pts <= 0: risk_pts = 5.0
        
        tp_ladder = [
            entry_price - (risk_pts * 0.5),
            entry_price - (risk_pts * 1.0),
            entry_price - (risk_pts * 1.5),
            entry_price - (risk_pts * 2.0),
            entry_price - (risk_pts * 3.0)
        ]
    else:
        # BUY
        zone_low = recent_low - 1.0
        zone_high = recent_low + 2.0
        zone_width = zone_high - zone_low
        if zone_width <= 0: zone_width = 3.0
        
        sl = zone_low - (2.0 * zone_width)
        risk_pts = entry_price - sl
        if risk_pts <= 0: risk_pts = 5.0
        
        tp_ladder = [
            entry_price + (risk_pts * 0.5),
            entry_price + (risk_pts * 1.0),
            entry_price + (risk_pts * 1.5),
            entry_price + (risk_pts * 2.0),
            entry_price + (risk_pts * 3.0)
        ]

    log.info(f"Calculated New Dynamic SL: {sl}")
    log.info(f"Calculated New Dynamic TP Ladder: {tp_ladder}")

    # Update MT5 physical SL and TP1
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "XAUUSD",
        "position": ticket,
        "sl": sl,
        "tp": tp_ladder[0],
    }
    
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"Successfully updated physical MT5 SL/TP for #{ticket}")
    else:
        err = res.comment if res else "Unknown Error"
        log.error(f"Failed to update MT5 SL/TP: {err}")

    # Reclaim state in JSON so background engine picks it up
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
        
    # Also write to root directory just in case it's looking there
    with open("gold_position_state.json", "w") as f:
        json.dump(state_obj, f)
        
    log.info("Reclaimed state in gold_position_state.json! Background engine will now manage the new TP ladder.")

if __name__ == "__main__":
    run()
