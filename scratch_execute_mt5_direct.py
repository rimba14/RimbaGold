import sys
import logging
import MetaTrader5 as mt5
import math

sys.path.append(r"C:\Sentinel_Project")
from fastapi_sniper import (
    calculate_atr_and_swing, 
    atomic_sl_tp_modification,
    get_broker_adapter
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ManualPush")

def execute_direct(symbol, direction, lot_size, conviction):
    path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    if not mt5.initialize(path=path):
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return

    info = mt5.symbol_info(symbol)
    if not info:
        logger.error(f"Symbol info for {symbol} not found.")
        return

    logger.info(f"Executing manual override order of {lot_size} lots on {symbol}...")

    adapter = get_broker_adapter(symbol)
    ticket_id_str = adapter.execute_market_order(
        symbol=symbol,
        lots=lot_size,
        direction=direction,
        comment=f"MANUAL_OVERRIDE_{symbol}"
    )
    
    if ticket_id_str == "ERROR_TICKET_FAILED" or not ticket_id_str.isdigit():
        logger.error(f"Failed to execute order for {symbol}.")
        return
        
    ticket_id = int(ticket_id_str)
    logger.info(f"Market order executed successfully. Ticket: {ticket_id}")

    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if direction == "BUY" else tick.bid
    digits = info.digits
    
    current_atr, _ = calculate_atr_and_swing(symbol, direction, lookback=20)
    final_sl_dist = max(3.0 * current_atr, info.trade_stops_level * info.point)
    
    sl_price = round(price - final_sl_dist if direction == "BUY" else price + final_sl_dist, digits)

    p_entry = max(conviction, 0.60)
    normalized_p = (p_entry - 0.60) / 0.40
    tp_multiplier = 2.0 + 2.0 * math.log10(1 + 9 * normalized_p)
    tp_dist = current_atr * tp_multiplier
    
    tp_price = round(price + tp_dist if direction == "BUY" else price - tp_dist, digits)

    positions = mt5.positions_get(ticket=ticket_id)
    if not positions:
        logger.error(f"Could not retrieve filled position for Ticket {ticket_id}.")
        return
        
    pos = positions[0]
    success = atomic_sl_tp_modification(pos, sl_price, tp_price)
    
    if success:
        print(f"[SUCCESS] {symbol} {direction} {lot_size} lots. Ticket: {ticket_id} | SL: {sl_price} | TP: {tp_price}")
    else:
        print(f"[PARTIAL SUCCESS] {symbol} executed but stops modification failed.")

if __name__ == "__main__":
    execute_direct("GBPJPY", "SELL", 0.01, 0.659)
    execute_direct("USDSGD", "SELL", 0.02, 0.658)
