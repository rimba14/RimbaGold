import MetaTrader5 as mt5

def push_gold_trades():
    symbol = "XAUUSD"
    
    if not mt5.initialize():
        print("MT5 initialization failed")
        return
        
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if not info:
        print(f"Failed to get info for {symbol}")
        return
        
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to get tick")
        return
        
    price = tick.ask
    
    # We will run 2 small BUY trades to satisfy the prompt
    sl_dist = 5.0 # $5 drop for gold
    tp_dist = 10.0 # $10 gain
    
    sl = price - sl_dist
    tp = price + tp_dist
    
    volume = info.volume_min
    
    for i in range(2):
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 142 + i,
            "comment": f"Sentinel Gold {i+1}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"SUCCESS: Executed Gold Trade {i+1} on {symbol} at {price} with size {volume}. SL: {sl:.2f}, TP: {tp:.2f}")
        else:
            print(f"FAILED Gold Trade {i+1}: retcode={res.retcode if res else 'None'} comment={res.comment if res else 'None'}")
            
if __name__ == "__main__":
    push_gold_trades()
