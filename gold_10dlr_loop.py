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

def calculate_rsi(rates, period=14):
    if len(rates) < period + 1:
        return 50.0
    changes = []
    for i in range(1, len(rates)):
        changes.append(rates[i]['close'] - rates[i-1]['close'])
    
    gains = [c if c > 0 else 0.0 for c in changes]
    losses = [-c if c < 0 else 0.0 for c in changes]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def run_loop():
    print("Initializing MT5 Loop...")
    while not mt5.initialize():
        print(f"Init failed. Error: {mt5.last_error()}. Retrying in 5s...")
        time.sleep(5)
    print("MT5 Initialized!")
    
    account_info = mt5.account_info()
    if not account_info:
        print("Failed to get account info.")
        return
        
    if account_info.login != 25653715:
        print(f"CRITICAL ERROR: Connected to account {account_info.login}, but expected 25653715! Aborting.")
        return
        
    print(f"Verified connected to Gold Account: {account_info.login}")
        
    import psutil
    import os
    import pandas as pd
    
    current_pid = os.getpid()
    parent_pid = psutil.Process(current_pid).ppid()
    running_count = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in p.info['name'].lower() and p.info['cmdline']:
                if 'gold_10dlr_loop.py' in ' '.join(p.info['cmdline']):
                    if p.info['pid'] != current_pid and p.info['pid'] != parent_pid:
                        running_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if running_count > 0:
        print(f"CRITICAL ERROR: Another instance of gold_10dlr_loop.py is already running. Shutting down to prevent duplicate trades!")
        return
        
    symbol = "XAUUSD+"
    lot_sizes = [0.03]
    target_profits = {0.03: 15.0}
    last_direction = "SELL" # User clarified the last trade was a SELL
    
    mt5.symbol_select(symbol, True)
    
    while True:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 50)
        
        if not tick or not info or rates is None or len(rates) < 50:
            print("Failed to get symbol info or rates. Retrying in 5s...")
            time.sleep(5)
            continue
            
        sma50 = sum([r['close'] for r in rates]) / 50.0
        last_closed_candle = rates[-2]
        rsi_14 = calculate_rsi(rates[:-1], period=14)
        
        if last_closed_candle['close'] > sma50 and rsi_14 > 50:
            current_direction = "BUY"
        elif last_closed_candle['close'] < sma50 and rsi_14 < 50:
            current_direction = "SELL"
        else:
            current_direction = last_direction
            
        existing_positions = mt5.positions_get(symbol=symbol)
        
        if existing_positions and len(existing_positions) > 0:
            pos_direction = "BUY" if existing_positions[0].type == mt5.ORDER_TYPE_BUY else "SELL"
            
            # --- M15 20 EMA STRUCTURAL EXIT ---
            m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
            
            macro_exit = False
            if m15_rates is not None and len(m15_rates) >= 25:
                # ONLY evaluate the last fully closed candle, which is index -2 in MT5 array
                # (The active forming candle is index -1)
                closed_rates = m15_rates[:-1]
                closes = [r['close'] for r in closed_rates]
                
                # Calculate 20 EMA using pandas
                ema20 = pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1]
                last_closed = closes[-1]
                
                if pos_direction == "BUY" and last_closed < ema20:
                    macro_exit = True
                elif pos_direction == "SELL" and last_closed > ema20:
                    macro_exit = True
                    
            if macro_exit:
                print(f"M15 20 EMA STRUCTURAL BREAK DETECTED! Emergency closing {pos_direction} and neutralizing state!")
                for p in existing_positions:
                    p_dir = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    close_position(p.ticket, symbol, p.volume, p_dir)
                # No Auto-Reversal: Set last_direction to pos_direction to force neutral wait state
                last_direction = pos_direction
                time.sleep(1)
                continue
                
            # --- INDEPENDENT PROFIT TRACKING ---
            all_closed = True
            log_str = f"Holding {pos_direction}... "
            
            for p in existing_positions:
                target = target_profits.get(round(p.volume, 2), 15.0) # default to $15 if undefined
                if p.profit >= target:
                    print(f"Independent target hit for ticket #{p.ticket} ({p.volume} lots)! Profit: ${p.profit:.2f} >= ${target:.2f}. Closing...")
                    p_dir = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    close_position(p.ticket, symbol, p.volume, p_dir)
                else:
                    all_closed = False
                    log_str += f"[Vol {p.volume}: ${p.profit:.2f}/${target:.2f}] "
                    
            if all_closed:
                print("All individual profit targets have been hit and positions closed! Waiting for next cycle...")
                last_direction = pos_direction
                time.sleep(1)
                continue
            else:
                log_str += f"| RSI: {rsi_14:.2f} | Close: {last_closed_candle['close']:.2f}"
                print(log_str)
                time.sleep(1)
                continue
                
        if last_direction == current_direction:
            print(f"Waiting for confirmed opposing signal. (Last Trade: {last_direction}) | RSI: {rsi_14:.2f} | Close: {last_closed_candle['close']:.2f} | SMA50: {sma50:.2f}")
            time.sleep(1)
            continue
            
        order_type = mt5.ORDER_TYPE_BUY if current_direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if current_direction == "BUY" else tick.bid
        
        print(f"\n--- NEW OPPOSING CYCLE ---")
        print(f"Trend (SMA50): {sma50:.2f} | Current Bid: {tick.bid:.2f}")
        print(f"Shooting {symbol} {current_direction} with sizes {lot_sizes}...")
        
        tickets = []
        for vol in lot_sizes:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(vol),
                "type": order_type,
                "price": round(price, info.digits),
                "deviation": 20,
                "magic": 999,
                "comment": f"Loop {current_direction}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                tickets.append(res.order)
            else:
                print(f"Failed to open position {vol} lots: {res.comment if res else mt5.last_error()}")
            time.sleep(0.1)
            
        if not tickets:
            print("Failed to open any positions.")
            time.sleep(5)
            continue
            
        last_direction = current_direction
        print(f"Success! Tickets: {tickets}. Direction: {current_direction}. Monitoring asynchronously...")
        time.sleep(1)
                
if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        print("Loop stopped.")
    finally:
        mt5.shutdown()
