import MetaTrader5 as mt5
from arcticdb import Arctic

mt5.initialize()
store = Arctic('lmdb://C:/Sentinel_Project/data/arctic_cache')
lib = store['oracle_cache']

assets = []
fx_currencies = {'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF', 'HKD', 'SGD', 'TRY'}

for sym in lib.list_symbols():
    if sym.endswith('_meta'):
        base_sym = sym.replace('_meta', '')
        
        if len(base_sym) != 6 or base_sym[:3] not in fx_currencies or base_sym[3:] not in fx_currencies:
            continue
        
        data = lib.read(sym).data
        if not data.empty:
            row = data.iloc[-1]
            p_val = float(row.get('meta_conviction', row.get('xgb_p', 0.5)))
            hmm_state = str(row.get('wasserstein_state', 'RANGE')).upper()
            
            if p_val == 0.0 or p_val == 0.5 or 'STAGNANT' in hmm_state or 'CLOSED' in hmm_state or 'QUARANTINE' in hmm_state:
                continue
                
            direction = 'BUY' if p_val >= 0.5 else 'SELL'
            conviction = p_val if direction == 'BUY' else (1.0 - p_val)
            
            assets.append({
                'symbol': base_sym,
                'direction': direction,
                'conviction': conviction,
                'hmm': hmm_state
            })

assets = sorted(assets, key=lambda x: x['conviction'], reverse=True)[:5]
for a in assets:
    print(f"{a['symbol']} | {a['direction']} | {a['conviction']:.3f} | {a['hmm']}")
