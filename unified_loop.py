import time
import builtins
import MetaTrader5 as mt5

print = lambda *args, **kwargs: builtins.print(*args, **kwargs, flush=True)

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

def run_unified_loop():
    print("Initializing MT5 Unified Loop...")
    while not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        err = mt5.last_error()
        print(f"Init failed. Error: {err}. Retrying in 5s...")
        time.sleep(5)

    print("MT5 Initialized!")
        
    configs = [
        {"symbol": "XAUUSD", "lot_size": 0.05, "target_profit": 10.0},
        {"symbol": "NAS100", "lot_size": 0.05, "target_profit": 20.0}
    ]
    
    last_heartbeat = time.time()
    trailing_state = {}  # Format: {ticket: {'peak': float, 'active': bool}}
    last_elastic_print = {}
    
    while True:
        current_profits = {}
        for cfg in configs:
            symbol = cfg["symbol"]
            lot_size = cfg["lot_size"]
            target_profit = cfg["target_profit"]
            
            tick = mt5.symbol_info_tick(symbol)
            info = mt5.symbol_info(symbol)
            
            if not tick or not info:
                continue
                
            actual_lot = float(max(lot_size, info.volume_min))
                
            # Check for existing loop positions for this symbol
            positions = mt5.positions_get(symbol=symbol)
            loop_pos = None
            if positions:
                for p in positions:
                    if p.magic == 999:
                        loop_pos = p
                        break
                        
            if loop_pos:
                ticket = loop_pos.ticket
                current_profit = loop_pos.profit
                current_profits[symbol] = current_profit
                
                # Initialize trailing state for this ticket
                if ticket not in trailing_state:
                    trailing_state[ticket] = {'peak': current_profit, 'active': False}
                    
                # Update peak profit
                if current_profit > trailing_state[ticket]['peak']:
                    trailing_state[ticket]['peak'] = current_profit
                    
                # Check activation
                if not trailing_state[ticket]['active'] and current_profit >= target_profit:
                    print(f"[{symbol}] Trailing Profit ACTIVATED at ${current_profit} (Target: ${target_profit})")
                    trailing_state[ticket]['active'] = True
                    
                # Check for pullback if trailing is active
                if trailing_state[ticket]['active']:
                    peak = trailing_state[ticket]['peak']
                    pullback_amount = 2.0  # Fixed $2 trailing step
                    if current_profit <= peak - pullback_amount:
                        print(f"[{symbol}] Trailing Profit triggered! Peak: ${peak}, Closed at: ${current_profit}. Closing #{ticket}...")
                        direction = "BUY" if loop_pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                        if close_position(ticket, symbol, loop_pos.volume, direction):
                            del trailing_state[ticket]
            else:
                current_profits[symbol] = "None"
                # No active position, shoot a new one
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
                if rates is None or len(rates) < 50:
                    continue
                    
                # Calculate ATR (Average True Range) over last 14 periods for elasticity filter
                tr_list = []
                for i in range(1, 15):
                    idx = -i
                    high = rates[idx]['high']
                    low = rates[idx]['low']
                    prev_close = rates[idx-1]['close']
                    tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                    tr_list.append(tr)
                atr = sum(tr_list) / len(tr_list)
                
                sma50 = sum([r['close'] for r in rates]) / 50.0
                
                # Elasticity Check: Prevent entering if price is > 1.5x ATR from SMA50
                distance_to_sma = abs(tick.bid - sma50)
                if atr > 0 and distance_to_sma > (1.5 * atr):
                    if time.time() - last_elastic_print.get(symbol, 0) > 60:
                        print(f"[{symbol}] Elasticity Filter Triggered: Distance to SMA ({distance_to_sma:.2f}) > 1.5x ATR ({(1.5*atr):.2f}). Waiting for pullback...")
                        last_elastic_print[symbol] = time.time()
                    continue
                    
                direction = "BUY" if tick.bid > sma50 else "SELL"
                order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                price = tick.ask if direction == "BUY" else tick.bid
                
                print(f"\n--- NEW {symbol} CYCLE ---")
                print(f"Trend (SMA50): {sma50:.2f} | Current Bid: {tick.bid:.2f} | ATR: {atr:.2f}")
                print(f"Shooting {symbol} {direction} {actual_lot} lots...")
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(actual_lot),
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
                    print(f"[{symbol}] Failed to open position: {res.comment if res else mt5.last_error()}")
                else:
                    print(f"[{symbol}] Success! Ticket: {res.order}. Monitoring for ${target_profit} profit (with $2 trail)...")
                    
        if time.time() - last_heartbeat >= 60:
            print(f"[HEARTBEAT] Active floating profits: {current_profits}")
            last_heartbeat = time.time()
            
        # Sleep slightly to avoid blasting the terminal
        time.sleep(1.0)

if __name__ == "__main__":
    try:
        run_unified_loop()
    except KeyboardInterrupt:
        print("Loop stopped.")
    finally:
        mt5.shutdown()
