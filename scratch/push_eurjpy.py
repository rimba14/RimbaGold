import MetaTrader5 as mt5

def push_eurjpy():
    symbol = "EURJPY"
    direction = "BUY"
    conviction = 0.575
    
    if not mt5.initialize():
        print("MT5 initialization failed")
        return
        
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if not info:
        print(f"Failed to get info for {symbol}")
        return
        
    acc = mt5.account_info()
    equity = acc.equity if acc else 1000.0
    
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to get tick")
        return
        
    price = tick.ask if direction == "BUY" else tick.bid
    
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 20)
    if rates is not None and len(rates) > 0:
        highs = [r['high'] for r in rates]
        lows = [r['low'] for r in rates]
        closes = [r['close'] for r in rates]
        tr_list = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(rates))]
        atr = sum(tr_list) / len(tr_list) if tr_list else 0.0010
    else:
        atr = 0.0010
        
    atr = max(atr, 0.0020 * price)
    
    sl_dist = 3.5 * atr
    tp_dist = 5.25 * atr
    
    sl = price - sl_dist if direction == "BUY" else price + sl_dist
    tp = price + tp_dist if direction == "BUY" else price - tp_dist
    
    # Medallion Sizing Approximation
    p = conviction
    q = 1.0 - p
    b = 1.5
    f_raw = max(0.0, p - (q / b))
    f_kelly = f_raw * 0.25
    
    atr_scalar = min(2.0, 0.01 / atr) if atr > 0 else 1.0
    f_kelly *= atr_scalar
    
    risk_dollars = equity * min(f_kelly, 0.02)
    
    tick_value = info.trade_tick_value
    point = info.point
    
    if tick_value > 0 and point > 0:
        sl_points = sl_dist / point
        volume = risk_dollars / (sl_points * tick_value)
    else:
        volume = 0.01
        
    volume = max(info.volume_min, round(volume / info.volume_step) * info.volume_step)
    volume = min(info.volume_max, volume)
    
    print(f"Action: {direction} | Symbol: {symbol} | Price: {price}")
    print(f"Calculated Volume: {volume} (Risk: ${risk_dollars:.2f}, SL dist: {sl_dist:.3f})")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": round(sl, info.digits),
        "tp": round(tp, info.digits),
        "deviation": 20,
        "magic": 142,
        "comment": "Sentinel Exec",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(request)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"SUCCESS: Executed {direction} on {symbol} at {price} with size {volume}. SL: {sl:.3f}, TP: {tp:.3f}")
    else:
        print(f"FAILED: retcode={res.retcode if res else 'None'} comment={res.comment if res else 'None'}")
        
if __name__ == "__main__":
    push_eurjpy()
