import MetaTrader5 as mt5

def execute_simple(symbol, direction, lot_size, sl, tp):
    if not mt5.initialize():
        print("MT5 init failed")
        return
    info = mt5.symbol_info(symbol)
    if not info:
        print(f"Info not found for {symbol}")
        return
        
    mt5.symbol_select(symbol, True)
    
    action = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if direction == "BUY" else tick.bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": action,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 234567,
        "comment": "MANUAL_PUSH",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(request)
    print(f"Order for {symbol}: {res}")

if __name__ == "__main__":
    execute_simple("GBPJPY", "SELL", 0.01, 216.138, 213.086)
    execute_simple("USDSGD", "SELL", 0.02, 1.28928, 1.27441)
