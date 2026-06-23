import os
import asyncio
import numpy as np
import ccxt.async_support as ccxt_async
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ZetaEnforcer')

load_dotenv()

async def get_exchange():
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    exchange = ccxt_async.binanceusdm({
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    for k, v in exchange.urls['api'].items():
        if isinstance(v, str):
            exchange.urls['api'][k] = v.replace('fapi.binance.com', 'testnet.binancefuture.com').replace('api.binance.com', 'testnet.binancefuture.com').replace('sapi.binance.com', 'testnet.binancefuture.com')
    return exchange

async def main():
    exchange = await get_exchange()
    try:
        positions = await exchange.fapiPrivateV2GetPositionRisk()
        active = [p for p in positions if float(p['positionAmt']) != 0]
        
        for p in active:
            sym = p['symbol']
            amt = float(p['positionAmt'])
            entry = float(p['entryPrice'])
            side = 'BUY' if amt > 0 else 'SELL'
            inv_side = 'sell' if side == 'BUY' else 'buy'
            abs_amt = abs(amt)
            
            logger.info(f"Processing {sym} ({side} {amt})")
            
            try:
                await exchange.fapiPrivateDeleteAllOpenOrders({'symbol': sym})
                logger.info(f"  [{sym}] Cancelled existing orders.")
            except Exception as e:
                logger.warning(f"  [{sym}] Could not cancel orders: {e}")
                
            try:
                ohlcv = await exchange.fetch_ohlcv(sym, '1d', limit=15)
                highs = np.array([candle[2] for candle in ohlcv])
                lows = np.array([candle[3] for candle in ohlcv])
                closes = np.array([candle[4] for candle in ohlcv])
                
                tr1 = highs[1:] - lows[1:]
                tr2 = np.abs(highs[1:] - closes[:-1])
                tr3 = np.abs(lows[1:] - closes[:-1])
                tr = np.maximum(tr1, np.maximum(tr2, tr3))
                atr = np.mean(tr)
            except Exception as e:
                logger.warning(f"  [{sym}] Fetching ATR failed: {e}. Using 5% default.")
                atr = entry * 0.05
                
            floor_dist = max(entry * 0.002, atr * 3.5)
            sl_dist = floor_dist
            tp_dist = floor_dist * 1.5
            
            if side == 'BUY':
                sl = entry - sl_dist
                tp = entry + tp_dist
            else:
                sl = entry + sl_dist
                tp = entry - tp_dist
                
            # Clamp TP to ensure it's strictly positive and valid
            if tp <= 0:
                tp = 0.0001
                
            sl_price = float(exchange.price_to_precision(sym, sl))
            tp_price = float(exchange.price_to_precision(sym, tp))
            
            logger.info(f"  [{sym}] Setting Bracket -> SL: {sl_price} | TP: {tp_price}")
            
            sl_params = {'reduceOnly': True, 'stopPrice': sl_price}
            tp_params = {'reduceOnly': True, 'stopPrice': tp_price}
            
            try:
                await exchange.create_order(sym, 'stop_market', inv_side, abs_amt, None, sl_params)
                logger.info(f"  [{sym}] SL order placed.")
            except Exception as e:
                logger.error(f"  [{sym}] Failed to place SL: {e}")
                
            try:
                await exchange.create_order(sym, 'take_profit_market', inv_side, abs_amt, None, tp_params)
                logger.info(f"  [{sym}] TP order placed.")
            except Exception as e:
                logger.error(f"  [{sym}] Failed to place TP: {e}")

    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(main())
