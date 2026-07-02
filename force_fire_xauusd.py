import MetaTrader5 as mt5

def force_execute():
    print("Initializing MT5...")
    if not mt5.initialize():
        print(f"MT5 Init Failed. Error: {mt5.last_error()}")
        return
        
    symbol = "XAUUSD"
    print(f"Selecting symbol {symbol}...")
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select {symbol}!")
        
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Failed to get symbol_info for {symbol} - Is it in the Market Watch?")
        mt5.shutdown()
        return

    print("Fetching tick data...")
    tick = mt5.symbol_info_tick(symbol)
    
    if not tick:
        print("Failed to get tick")
        mt5.shutdown()
        return
        
    direction = "SELL"
    price = tick.bid
    order_type = mt5.ORDER_TYPE_SELL
    
    sl_points = 2.0
    tp_points = 4.0
    
    sl_val = round(price + sl_points, info.digits)
    tp_val = round(price - tp_points, info.digits)
    
    volume = 0.05
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "sl": float(sl_val),
        "tp": float(tp_val),
        "deviation": 20,
        "magic": 142,
        "comment": "NY Session Forced",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print(f"Sending order for {volume} lots of {symbol} at {price}...")
    res = mt5.order_send(request)
    
    if res is None:
        print(f"order_send returned None. Error: {mt5.last_error()}")
    elif res.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"IOC Failed. Retcode: {res.retcode}. Trying FOK...")
        request["type_filling"] = mt5.ORDER_FILLING_FOK
        res2 = mt5.order_send(request)
        if res2 is None:
            print(f"FOK returned None. Error: {mt5.last_error()}")
        elif res2.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed via FOK. Retcode: {res2.retcode}")
            print(res2._asdict())
        else:
            print(f"Success (FOK). Ticket: {res2.order}")
    else:
        print(f"Success (IOC). Ticket: {res.order}")
        
    mt5.shutdown()
    print("Done.")

if __name__ == "__main__":
    force_execute()
