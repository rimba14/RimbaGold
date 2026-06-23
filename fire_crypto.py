import asyncio
from binance_sniper import execute_trade, TradeSignal

async def push_trades():
    signals = [
        TradeSignal(symbol="UNIUSD", direction="SELL", conviction=0.578),
        TradeSignal(symbol="SOLUSD", direction="SELL", conviction=0.574)
    ]
    
    for sig in signals:
        try:
            res = await execute_trade(sig)
            print(f"Successfully pushed {sig.symbol}: {res}")
        except Exception as e:
            print(f"Failed to push {sig.symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(push_trades())
