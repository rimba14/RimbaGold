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
        "magic": 999999,
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
    last_direction = None
    print("Entering monitoring loop...")
    while not mt5.initialize(path=r"C:\Program Files\MetaTrader 5 - Scalper\terminal64.exe"):
        print(f"Init failed. Error: {mt5.last_error()}. Retrying in 5s...")
        time.sleep(5)
    print("MT5 Initialized!")
    
    TARGET_ACCOUNT = 2563715
    mt5.login(TARGET_ACCOUNT, password="Thisisthierry@1", server="VantageInternational-Demo")
    
    account_info = mt5.account_info()
    if not account_info:
        print("Failed to get account info.")
        return
        
    TARGET_ACCOUNT = 2563715
    MAGIC_NUMBER = 888888
    if account_info.login != TARGET_ACCOUNT:
        print(f"CRITICAL ERROR: Connected to account {account_info.login}, but expected {TARGET_ACCOUNT}! Aborting.")
        return
        
    print(f"Verified connected to Gold Account: {account_info.login}")
        
    import psutil
    import os
    
    current_pid = os.getpid()
    parent_pid = psutil.Process(current_pid).ppid()
    running_count = 0
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in p.info['name'].lower() and p.info['cmdline']:
                if 'scalp_executor_loop.py' in ' '.join(p.info['cmdline']):
                    if p.info['pid'] != current_pid and p.info['pid'] != parent_pid:
                        running_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if running_count > 0:
        print(f"CRITICAL ERROR: Another instance of scalp_executor_loop.py is already running. Shutting down to prevent duplicate trades!")
        return
        
    symbol = "XAUUSD"
    if mt5.symbol_info("XAUUSD+") is not None:
        symbol = "XAUUSD+"
        
    print(f"Broker symbol auto-detected as: {symbol}")
    
    lot_sizes = [0.01]
    target_profits = {0.01: 3.0}
    last_direction = "BUY" # The bot is currently holding a BUY, so next must be SELL
    
    mt5.symbol_select(symbol, True)
    
    while True:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 50)
        rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
        
        if not tick or not info or rates is None or len(rates) < 50 or rates_m15 is None or len(rates_m15) < 50 or rates_h1 is None or len(rates_h1) < 50 or rates_h4 is None or len(rates_h4) < 50:
            print("Failed to get symbol info or MTF rates. Retrying in 5s...")
            time.sleep(5)
            continue
            
        sma50 = sum([r['close'] for r in rates]) / 50.0
        last_closed_candle = rates[-2]
        rsi_14 = calculate_rsi(rates[:-1], period=14)
        
        sma50_m15 = sum([r['close'] for r in rates_m15]) / 50.0
        last_closed_m15 = rates_m15[-2]
        sma50_h1 = sum([r['close'] for r in rates_h1]) / 50.0
        last_closed_h1 = rates_h1[-2]
        sma50_h4 = sum([r['close'] for r in rates_h4]) / 50.0
        last_closed_h4 = rates_h4[-2]
        
        if last_closed_candle['close'] > sma50 and rsi_14 > 50:
            current_direction = "BUY"
        elif last_closed_candle['close'] < sma50 and rsi_14 < 50:
            current_direction = "SELL"
        else:
            current_direction = last_direction
            
        existing_positions = mt5.positions_get(symbol=symbol)
        
        if existing_positions and len(existing_positions) > 0:
            pos_direction = "BUY" if existing_positions[0].type == mt5.ORDER_TYPE_BUY else "SELL"
            
            # --- DOLLAR TAKE PROFIT TRACKING ---
            all_closed = True
            log_str = f"Holding {pos_direction}... "
                
            for p in existing_positions:
                target = target_profits.get(round(p.volume, 2), 15.0)
                stop_loss = -6.00
                if p.profit >= target:
                    print(f"Target hit for ticket #{p.ticket}! Profit: ${p.profit:.2f} >= ${target:.2f}. Closing...")
                    p_dir = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    close_position(p.ticket, symbol, p.volume, p_dir)
                elif p.profit <= stop_loss:
                    print(f"HARD STOP LOSS HIT for ticket #{p.ticket}! Loss: ${p.profit:.2f} <= ${stop_loss:.2f}. Closing to protect account...")
                    p_dir = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    close_position(p.ticket, symbol, p.volume, p_dir)
                elif time.time() - p.time > 900:
                    print(f"Time decay exit (15m) triggered for ticket #{p.ticket}! Time held: {time.time() - p.time:.0f}s. Closing...")
                    p_dir = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    close_position(p.ticket, symbol, p.volume, p_dir)
                else:
                    all_closed = False
                    log_str += f"[Vol {p.volume}: ${p.profit:.2f}/${target:.2f}] "
                    
            if all_closed:
                print("All dollar targets hit! Waiting for opposing cycle...")
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
            
        PAUSE_ENTRIES = False
        if PAUSE_ENTRIES:
            print(f"MANUAL OVERRIDE ACTIVE: Position closed. Holding fire on new entries. Awaiting user instruction... | RSI: {rsi_14:.2f} | Close: {last_closed_candle['close']:.2f}")
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
                "magic": 999999,
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
