import time
import builtins
import MetaTrader5 as mt5

print = lambda *args, **kwargs: builtins.print(*args, **kwargs, flush=True)




def cancel_pending_order(ticket, symbol):
    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
        "symbol": symbol
    }
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[{symbol}] Successfully cancelled pending limit order #{ticket}")
        return True
    else:
        print(f"[{symbol}] Failed to cancel order #{ticket}: {res.comment if res else mt5.last_error()}")
        return False

def close_position(ticket, symbol, lot_size, direction, comment="Loop Profit Close"):
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
        "comment": comment[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Successfully closed #{ticket}: {comment}")
        return True
    else:
        print(f"Failed to close #{ticket}. Error: {res.comment if res else mt5.last_error()}")
        return False


def move_sl_to_breakeven(position):
    if position.sl == position.price_open:
        return True
        
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": position.ticket,
        "sl": position.price_open,
        "tp": position.tp,
    }
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    else:
        print(f"[{position.symbol}] Failed to move SL to BE for #{position.ticket}: {res.comment if res else mt5.last_error()}")
        return False


def get_atr_usd(symbol, atr_points, volume):
    tick = mt5.symbol_info_tick(symbol)
    if not tick: 
        return atr_points * volume * 100
        
    val = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, symbol, volume, tick.bid, tick.bid + 1.0)
    if val is None:
        info = mt5.symbol_info(symbol)
        val = (1.0 / info.trade_tick_size) * info.trade_tick_value * volume
        
    return atr_points * val


def run_unified_loop():
    print("Initializing MT5 Unified Loop...")
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        print("MT5 initialization failed")
        return
        
    account_info = mt5.account_info()
    if account_info is None or account_info.login != 25653715:
        print(f"CRITICAL: Unified loop is locked to Gold Account 25653715. Current account: {account_info.login if account_info else 'None'}. Halting.")
        mt5.shutdown()
        return

    print("MT5 Initialized and locked to Gold Account 25653715!")
        
    configs = {
        "XAUUSD": {"lot_size": 0.10, "tp_usd": 10.00}
    }
    
    last_heartbeat = time.time()
    last_elastic_print = {}
    

    while True:
        # Cross-Account Safety Check
        account_info = mt5.account_info()
        if account_info is None or account_info.login != 25653715:
            print(f"CRITICAL SECURITY ABORT: Terminal switched to {account_info.login if account_info else 'None'}. Halting Gold bot to prevent cross-account trading.")
            mt5.shutdown()
            return
            
        current_profits = {}
        for symbol, cfg in configs.items():
            lot_size = cfg["lot_size"]
            
            tick = mt5.symbol_info_tick(symbol)
            info = mt5.symbol_info(symbol)
            
            if not tick or not info:
                continue
                
            actual_lot = float(max(lot_size, info.volume_min))
                
            positions = mt5.positions_get(symbol=symbol)
            loop_pos = None
            if positions:
                for p in positions:
                    if p.magic == 999:
                        loop_pos = p
                        break
                        
            # Calculate ATR for trail sizing & elasticity check
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 50)
            if rates is None or len(rates) < 50:
                continue
                
            tr_list = []
            for i in range(1, 15):
                idx = -i
                high = rates[idx]['high']
                low = rates[idx]['low']
                prev_close = rates[idx-1]['close']
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
            atr_points = sum(tr_list) / len(tr_list)
            
            sma50 = sum([r['close'] for r in rates]) / 50.0
            

            
            if loop_pos:
                ticket = loop_pos.ticket
                current_profit = loop_pos.profit
                current_profits[symbol] = current_profit
                
                # Check for cut-and-reverse
                current_pos_dir = "BUY" if loop_pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                
                target_profit = cfg.get("tp_usd", 10.00)
                if current_profit >= target_profit:
                    print(f"[{symbol}] Hard Target Reached! Securing ${target_profit} Profit.")
                    close_position(ticket, symbol, loop_pos.volume, current_pos_dir, comment="Take Profit")
                    continue
                    
            else:
                current_profits[symbol] = "None"
                
                direction = "BUY" if tick.bid > sma50 else "SELL"
                order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                price = tick.ask if direction == "BUY" else tick.bid
                
                print(f"\n--- NEW {symbol} CYCLE ---")
                print(f"Trend (SMA50): {sma50:.2f} | Current Bid: {tick.bid:.2f} | ATR: {atr_points:.2f}")
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
                    print(f"[{symbol}] Success! Ticket: {res.order}.")
                    
        if time.time() - last_heartbeat >= 60:
            print(f"[HEARTBEAT] Active floating profits: {current_profits}")
            last_heartbeat = time.time()
            
        time.sleep(10.0)

if __name__ == "__main__":
    try:
        run_unified_loop()
    except KeyboardInterrupt:
        print("Loop stopped.")
    finally:
        mt5.shutdown()
