"""
alpha_compare_mcp.py

MCP Tool for Alpha Zoo & Statistical Validation (Vibe-Trading Integration v38.0)
Calculates Information Coefficient (IC) mean/std, Information Ratio (IR), and IC-positive ratio
for custom formulaic alphas.
"""

import numpy as np
import pandas as pd
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s [ALPHA_COMPARE] %(message)s')

def calculate_ic(predictions, forward_returns):
    """
    Calculates the Information Coefficient (Spearman Rank Correlation).
    """
    # Ensure aligned Series
    df = pd.DataFrame({'pred': predictions, 'fwd_ret': forward_returns}).dropna()
    if len(df) < 2:
        return 0.0
    return df['pred'].corr(df['fwd_ret'], method='spearman')

def compare_alphas(alpha_data_dict):
    """
    Pits multiple formulaic alphas against each other.
    alpha_data_dict: dict of format:
        {
            "alpha_name": {
                "predictions": list/array of signal values,
                "forward_returns": list/array of forward period returns
            }
        }
    Returns ranked dictionary based on Information Ratio (IR).
    """
    results = []
    
    for name, data in alpha_data_dict.items():
        try:
            preds = pd.Series(data.get('predictions', []))
            fwd_rets = pd.Series(data.get('forward_returns', []))
            
            # Group into chunks (e.g., daily) if time index is provided, else we calculate rolling or global IC
            # For this MCP tool, we will calculate rolling IC over arbitrary chunks to get mean/std
            chunk_size = min(len(preds) // 10, 60) # Simulate 60-day or 10 chunks
            if chunk_size < 5:
                chunk_size = len(preds)
                
            ics = []
            for i in range(0, len(preds), chunk_size):
                p_chunk = preds.iloc[i:i+chunk_size]
                r_chunk = fwd_rets.iloc[i:i+chunk_size]
                ic_val = calculate_ic(p_chunk, r_chunk)
                ics.append(ic_val)
                
            ics = np.array(ics)
            ic_mean = np.mean(ics) if len(ics) > 0 else 0.0
            ic_std = np.std(ics) if len(ics) > 0 and np.std(ics) > 0 else 1e-6
            ir = ic_mean / ic_std
            
            ic_positive_ratio = np.sum(ics > 0) / len(ics) if len(ics) > 0 else 0.0
            
            results.append({
                "alpha_name": name,
                "ic_mean": float(ic_mean),
                "ic_std": float(ic_std),
                "ir": float(ir),
                "ic_positive_ratio": float(ic_positive_ratio)
            })
            logging.info(f"Evaluated {name}: IC={ic_mean:.4f}, IR={ir:.4f}, IC+={ic_positive_ratio:.1%}")
            
        except Exception as e:
            logging.error(f"Error evaluating alpha {name}: {e}")
            
    # Rank by IR
    results.sort(key=lambda x: x["ir"], reverse=True)
    return {"status": "success", "rankings": results}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Generate mock data to test MCP tool
        np.random.seed(42)
        fwd = np.random.randn(1000)
        
        mock_data = {
            "XGBoost_Baseline": {
                "predictions": fwd + np.random.randn(1000) * 2,
                "forward_returns": fwd
            },
            "StockFormer_V2": {
                "predictions": fwd + np.random.randn(1000) * 1.5, # Slightly better
                "forward_returns": fwd
            },
            "Decaying_Alpha": {
                "predictions": np.random.randn(1000), # Random noise
                "forward_returns": fwd
            }
        }
        
        import json
        print(json.dumps(compare_alphas(mock_data), indent=2))
