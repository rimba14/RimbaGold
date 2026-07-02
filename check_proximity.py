import config as cfg
from core.gold_feeder import GoldFeeder
from zone.zone_detector import build_zones
from signal.conviction_scorer import score_zones
import numpy as np
from core.atr_sampler import get_d1_atr
from core.session_clock import get_session_state
from datetime import datetime, timezone

def check_asset(symbol):
    cfg.apply_profile(symbol)
    feeder = GoldFeeder(symbol)
    feeder.connect()
    times, opens, highs, lows, closes = feeder.get_ohlcv_arrays("M5", count=300)
    if len(closes) == 0:
        feeder.disconnect()
        return "No data"
        
    tick = feeder.get_tick()
    if tick is None: return "No tick"
    current_price = tick.mid
    
    _, _, h_d1, l_d1, c_d1 = feeder.get_ohlcv_arrays("D1", count=50)
    d1_atr = get_d1_atr(symbol, h_d1, l_d1, c_d1, 14, 3600).atr
    
    all_zones = build_zones(
        highs=highs, lows=lows, closes=closes, times=np.arange(len(closes), dtype=float),
        volumes=np.ones(len(closes)), d1_atr=d1_atr, left_bars=4, right_bars=4,
        max_age_bars=96, cluster_tol_atr=0.15, zone_min_w_atr=0.15, zone_max_w_atr=0.35
    )
    
    session = get_session_state(datetime.now(timezone.utc))
    scored = score_zones(zones=all_zones, d1_atr=d1_atr, max_age_bars=96, session_state=session)
    
    closest_dist = float('inf')
    best_zone = None
    best_score = 0
    
    for z in all_zones:
        score = scored.get(id(z))
        if score and score.total >= 0.60:
            # Check distance
            if current_price > z.high:
                dist = current_price - z.high
            elif current_price < z.low:
                dist = z.low - current_price
            else:
                dist = 0.0 # Inside the zone
                
            if dist < closest_dist:
                closest_dist = dist
                best_zone = z
                best_score = score.total
                
    feeder.disconnect()
    if best_zone:
        status = "INSIDE ZONE! (FIRING)" if closest_dist == 0.0 else f"{closest_dist:.2f} points away"
        return f"Closest {best_zone.zone_type.value} Zone ({best_score:.2f} conv) -> {status}"
    return "No high conviction zones found"

for sym in ['XAUUSD', 'NAS100', 'GER40', 'DJ30', 'HK50']:
    print(f"{sym}: {check_asset(sym)}")
