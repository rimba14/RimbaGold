import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from typing import Optional
import ccxt
import requests as _requests
import math
from dotenv import load_dotenv

load_dotenv()

# Use the existing ATR logic from the main framework
from fastapi_sniper import calculate_structural_atr_d1, get_structural_multiplier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [BINANCE] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Sentinel Binance Execution Bridge")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    expected_key = os.getenv("SENTINEL_API_KEY")
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid API Key")

class TradeSignal(BaseModel):
    symbol: str
    direction: str
    conviction: Optional[float] = 0.80
    xgb_p: float = 0.5
    ddqn_p: float = 0.5
    wasserstein_state: str = "HIGH-VOL MEAN REVERSION"
    timestamp: Optional[int] = None
    reasoning: str = ""
    vpin: float = 0.0
    signal_type: str = "UNKNOWN"
    rsi: Optional[float] = None
    data_quality_flag: str = "PRISTINE"
    alpha_features: Optional[dict] = None
    vrs: Optional[float] = 1.0
    applied_dynamic_gate: Optional[float] = None
    strategy_type: Optional[str] = "MOMENTUM"
    sl: Optional[float] = 0.0
    tp: Optional[float] = 0.0
    size_multiplier: Optional[float] = 1.0
    override_lot: Optional[float] = 0.0
    tag: Optional[str] = ""

def map_symbol(oracle_sym: str) -> str:
    """Translates BTCUSD to BTC/USDT:USDT (CCXT linear futures unified symbol)"""
    base = oracle_sym.replace("USD", "")
    return f"{base}/USDT:USDT"

def get_exchange():
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    if not api_key or not secret:
        raise HTTPException(status_code=400, detail="BINANCE_API_KEY and BINANCE_SECRET must be set in .env")
        
    exchange = ccxt.binanceusdm({
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        },
        'options': {
            'defaultType': 'future'
        }
    })
    # Bypass CCXT sandbox deprecation block by overriding all endpoints
    for k, v in exchange.urls['api'].items():
        if isinstance(v, str):
            exchange.urls['api'][k] = v.replace('fapi.binance.com', 'testnet.binancefuture.com').replace('api.binance.com', 'testnet.binancefuture.com')
    
    return exchange

@app.post("/execute_trade", dependencies=[Depends(verify_api_key)])
async def execute_trade(signal: TradeSignal):
    logger.info(f"Received Binance execution signal for {signal.symbol} | Dir: {signal.direction}")
    
    binance_sym = map_symbol(signal.symbol)
    exchange = get_exchange()
    
    try:
        # Bypass load_markets() crash on testnet
        # await exchange.load_markets()
        exchange.markets = {
            binance_sym: {
                'id': binance_sym.split('/')[0] + binance_sym.split('/')[1].split(':')[0], 
                'symbol': binance_sym, 
                'limits': {'amount': {'min': 0.001}, 'price': {'min': 0.01}, 'cost': {'min': 0.0}}, 
                'precision': {'amount': 0.001, 'price': 0.01, 'base': 8, 'quote': 8}, 
                'contractSize': 1, 
                'linear': True, 
                'type': 'future', 
                'spot': False,
                'tierBased': False,
                'percentage': True,
                'maker': 0.0002,
                'taker': 0.0004
            }
        }
        
        if binance_sym not in exchange.markets:
            raise HTTPException(status_code=400, detail=f"Symbol {binance_sym} not tradeable on Binance Futures")
            
        market = exchange.markets[binance_sym]
        
        # Fetch live price via raw REST (bypass CCXT parse which needs full market metadata)
        _base_sym = binance_sym.split('/')[0] + 'USDT'  # BTC/USDT:USDT -> BTCUSDT
        _ticker_resp = _requests.get(
            f'https://testnet.binancefuture.com/fapi/v1/ticker/bookTicker',
            params={'symbol': _base_sym}, timeout=10
        )
        _ticker_resp.raise_for_status()
        _ticker_data = _ticker_resp.json()
        ask_price = float(_ticker_data.get('askPrice', 0))
        bid_price = float(_ticker_data.get('bidPrice', 0))
        current_price = ask_price if signal.direction == 'BUY' else bid_price
        if current_price == 0:
            current_price = float(_ticker_data.get('lastPrice', 0))
        logger.info(f"[{binance_sym}] Live price: ask={ask_price} bid={bid_price} -> using {current_price}")
        # 1. Structural ATR & SL/TP
        structural_atr = calculate_structural_atr_d1(signal.symbol, period=14)
        if structural_atr is None:
            logger.warning(f"MT5 could not resolve {signal.symbol} ATR. Fetching natively via Binance CCXT.")
            ohlcv = exchange.fetch_ohlcv(binance_sym, timeframe='1d', limit=15)
            if ohlcv and len(ohlcv) >= 14:
                tr_list = []
                for i in range(1, len(ohlcv)):
                    h, l, prev_c = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
                    tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                    tr_list.append(tr)
                structural_atr = sum(tr_list[-14:]) / 14.0
            else:
                structural_atr = current_price * 0.05  # 5% fallback
                
        multiplier = get_structural_multiplier(signal.symbol) or 1.0
        
        dynamic_sl_dist = structural_atr * multiplier
        daily_atr_floor = structural_atr * 1.0
        percentage_floor = current_price * 0.002
        
        final_sl_dist = max(dynamic_sl_dist, daily_atr_floor, percentage_floor)
        
        sl_price = current_price - final_sl_dist if signal.direction == 'BUY' else current_price + final_sl_dist
        tp_dist = final_sl_dist * 1.5 # Fixed symmetric T/P for simplicity unless Conviction allows more
        
        # Dynamic TP
        p_entry = signal.conviction if signal.direction == 'BUY' else (1.0 - signal.conviction)
        p_entry = max(abs(p_entry - 0.5) + 0.5, 0.60)
        normalized_p = (p_entry - 0.60) / 0.40
        tp_multiplier = 2.0 + 2.0 * math.log10(1 + 9 * normalized_p)
        conviction_tp_dist = structural_atr * tp_multiplier
        tp_dist = max(conviction_tp_dist, tp_dist)
        
        tp_price = current_price + tp_dist if signal.direction == 'BUY' else current_price - tp_dist
        
        sl_price = round(sl_price, 2)
        tp_price = round(tp_price, 2)
        
        # 2. Risk Sizing via raw REST balance fetch
        import time, hmac, hashlib, urllib.parse
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        BASE = 'https://testnet.binancefuture.com'
        
        def signed_get(path, params=None):
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = 10000
            query = urllib.parse.urlencode(params)
            sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            return _requests.get(f"{BASE}{path}?{query}&signature={sig}",
                                 headers={'X-MBX-APIKEY': api_key}, timeout=10)
        
        def signed_post(path, params=None):
            params = params or {}
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = 10000
            query = urllib.parse.urlencode(params)
            sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            return _requests.post(f"{BASE}{path}",
                                  data=f"{query}&signature={sig}",
                                  headers={'X-MBX-APIKEY': api_key,
                                           'Content-Type': 'application/x-www-form-urlencoded'},
                                  timeout=10)
        
        usdt_free = 10000.0
        try:
            bal_resp = signed_get('/fapi/v2/balance')
            if bal_resp.ok:
                for asset in bal_resp.json():
                    if asset.get('asset') == 'USDT':
                        usdt_free = float(asset.get('availableBalance', 10000.0))
                        break
        except Exception as e:
            logger.warning(f"Balance fetch failed: {e}. Using $10,000 mock.")
            
        if signal.override_lot > 0:
            final_lot = signal.override_lot
        else:
            dollar_risk = usdt_free * 0.02
            raw_lot = dollar_risk / final_sl_dist
            final_lot = round(raw_lot, 3)
            
        final_lot = float(final_lot)
        if final_lot < 0.001:
            logger.warning(f"Calculated lot {final_lot} < minimum 0.001. Clamping.")
            final_lot = 0.001

        # 3. Execution via raw signed REST
        _base_sym_order = binance_sym.split('/')[0] + 'USDT'
        side = 'BUY' if signal.direction == 'BUY' else 'SELL'
        inv_side = 'SELL' if side == 'BUY' else 'BUY'
        
        logger.info(f"[{binance_sym}] Executing {side} {final_lot} at {current_price} | SL: {sl_price}")
        
        # Market Order
        order_params = {
            'symbol': _base_sym_order,
            'side': side,
            'type': 'MARKET',
            'quantity': final_lot,
        }
        order_resp = signed_post('/fapi/v1/order', order_params)
        if not order_resp.ok:
            raise HTTPException(status_code=500, detail=f"Order failed: {order_resp.text}")
        order_data = order_resp.json()
        order_id = order_data.get('orderId', 'unknown')
        logger.info(f"[{binance_sym}] Market order placed. ID: {order_id}")
        
        # SL Stop-Market
        try:
            sl_params_req = {
                'symbol': _base_sym_order,
                'side': inv_side,
                'type': 'STOP_MARKET',
                'stopPrice': sl_price,
                'quantity': final_lot,
                'reduceOnly': 'true',
                'workingType': 'MARK_PRICE'
            }
            sl_resp = signed_post('/fapi/v1/order', sl_params_req)
            if sl_resp.ok:
                logger.info(f"[{binance_sym}] SL bracket attached at {sl_price}")
            else:
                logger.warning(f"[{binance_sym}] SL bracket failed: {sl_resp.text}")
        except Exception as e:
            logger.error(f"[{binance_sym}] SL bracket error: {e}")
            
        return {"status": "success", "main_order": order_id}
        
    except Exception as e:
        logger.error(f"Execution Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    # finally:
        # exchange.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("binance_sniper:app", host="127.0.0.1", port=8002, reload=False)
