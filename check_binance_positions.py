import asyncio
import os
import ccxt.async_support as ccxt_async
from dotenv import load_dotenv

load_dotenv()

async def get_exchange():
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    
    exchange = ccxt_async.binanceusdm({
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    for k, v in exchange.urls['api'].items():
        if isinstance(v, str):
            exchange.urls['api'][k] = v.replace('fapi.binance.com', 'testnet.binancefuture.com').replace('api.binance.com', 'testnet.binancefuture.com').replace('sapi.binance.com', 'testnet.binancefuture.com')
    
    return exchange

async def check():
    exchange = await get_exchange()
    try:
        balance = await exchange.fetch_balance()
        positions = balance.get('info', {}).get('positions', [])
        
        active = []
        for p in positions:
            if float(p.get('positionAmt', 0)) != 0:
                active.append(p['symbol'])
        
        print(f"Active Binance positions: {active}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check())
