import asyncio
import ccxt.async_support as ccxt_async

async def test():
    ex = ccxt_async.binanceusdm({'enableRateLimit': True})
    ex.set_sandbox_mode(True)
    try:
        await ex.load_markets()
        print('success')
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await ex.close()

if __name__ == '__main__':
    asyncio.run(test())
