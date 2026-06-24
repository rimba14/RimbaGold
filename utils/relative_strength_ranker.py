import numpy as np
from typing import Dict, List, Optional

def compute_interval_return(prices: np.ndarray, period: int) -> float:
    """Computes the percentage return over a given period."""
    if len(prices) <= period or prices[-period-1] == 0:
        return 0.0
    return (prices[-1] / prices[-period-1]) - 1.0

def rank_relative_strength(
    asset_closes: Dict[str, np.ndarray], 
    benchmark_closes: np.ndarray, 
    top_percentile: float = 0.20
) -> List[str]:
    """
    Computes cross-sectional relative strength for a universe of tickers against a base benchmark.
    Tracks performance over 60-day, 20-day, and 5-day sliding windows.
    Returns the top N% strongest instruments.
    """
    if len(benchmark_closes) < 61:
        # Fallback if benchmark data is insufficient
        return list(asset_closes.keys())
        
    bm_60 = compute_interval_return(benchmark_closes, 60)
    bm_20 = compute_interval_return(benchmark_closes, 20)
    bm_5  = compute_interval_return(benchmark_closes, 5)
    
    rs_scores = {}
    
    for symbol, closes in asset_closes.items():
        if len(closes) < 61:
            rs_scores[symbol] = -999.0
            continue
            
        ret_60 = compute_interval_return(closes, 60)
        ret_20 = compute_interval_return(closes, 20)
        ret_5  = compute_interval_return(closes, 5)
        
        # RS is the difference between asset return and benchmark return
        rs_60 = ret_60 - bm_60
        rs_20 = ret_20 - bm_20
        rs_5  = ret_5 - bm_5
        
        # Composite score weighting: 40% (60d), 40% (20d), 20% (5d)
        composite_score = (0.4 * rs_60) + (0.4 * rs_20) + (0.2 * rs_5)
        rs_scores[symbol] = composite_score
        
    # Rank assets by composite score
    sorted_assets = sorted(rs_scores.items(), key=lambda item: item[1], reverse=True)
    
    # Select the top 20th percentile
    cutoff_index = max(1, int(len(sorted_assets) * top_percentile))
    top_assets = [item[0] for item in sorted_assets[:cutoff_index]]
    
    return top_assets
