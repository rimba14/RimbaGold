import time
import MetaTrader5 as mt5

def close_position(ticket, symbol, lot_size, direction):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[{symbol}] Failed to get tick to close #{ticket}")
        return False
        
    action_type = mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY
    price = tick.bid if direction == "BUY" else tick.ask
        
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": action_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 999,
        "comment": "Loop Profit Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Successfully closed #{ticket} at profit!")
        return True
    else:
        print(f"Failed to close #{ticket}. Error: {res.comment if res else mt5.last_error()}")
        return False

def run_loop():
    print("Initializing MT5 Loop...")
    while not mt5.initialize():
        print(f"Init failed. Error: {mt5.last_error()}. Retrying in 5s...")
        time.sleep(5)
    print("MT5 Initialized!")
        
    symbol = "NAS100"
    lot_size = 0.05
    target_profit = 5.0
    
    while True:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
        
        if not tick or not info or rates is None or len(rates) < 50:
            print("Failed to get symbol info or rates. Retrying in 5s...")
            time.sleep(5)
            continue
            
        sma50 = sum([r['close'] for r in rates]) / 50.0
        direction = "BUY" if tick.bid > sma50 else "SELL"
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if direction == "BUY" else tick.bid
        
        print(f"\n--- NEW CYCLE ---")
        print(f"Trend (SMA50): {sma50:.2f} | Current Bid: {tick.bid:.2f}")
        print(f"Shooting {symbol} {direction} {lot_size} lots...")
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": round(price, info.digits),
            "deviation": 20,
            "magic": 999,
            "comment": f"Loop {direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        res = mt5.order_send(request)
        if not res or res.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to open position: {res.comment if res else mt5.last_error()}")
            time.sleep(5)
            continue
            
        ticket = res.order
        print(f"Success! Ticket: {ticket}. Monitoring for ${target_profit} profit...")
        
        while True:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                print(f"Position #{ticket} no longer exists. Did you close it manually?")
                break
                
            pos = positions[0]
            if pos.profit >= target_profit:
                print(f"Profit target hit! Current profit: ${pos.profit}. Closing...")
                if close_position(ticket, symbol, lot_size, direction):
                    break # Break inner loop to shoot again
                else:
                    time.sleep(1) # Retry close
            else:
                time.sleep(0.5)
                
if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        print("Loop stopped.")
    finally:
        mt5.shutdown()
