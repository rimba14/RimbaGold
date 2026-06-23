import os
import sys
import json
import time
import argparse
import logging
import re
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [HITL_PUSH] %(message)s")
logger = logging.getLogger("HITL_Push")

PENDING_PATH = Path("C:/Sentinel_Project/pending_approvals.json")
LEDGER_PATH = Path("C:/Sentinel_Project/simulated_ledger.csv")

def prune_stale_trades():
    if not PENDING_PATH.exists():
        return []
    try:
        with open(PENDING_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return []
            trades = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to read staging file: {e}")
        return []
        
    now = time.time()
    active_trades = []
    updated = False
    for t in trades:
        ts = t.get("Timestamp", 0)
        # 15 minutes staleness limit (900 seconds)
        if now - ts > 900:
            logger.warning(f"Trade {t.get('Trade_ID')} for {t.get('Asset')} has expired and marked as STALE.")
            updated = True
        else:
            active_trades.append(t)
            
    if updated:
        try:
            with open(PENDING_PATH, "w") as f:
                json.dump(active_trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write updated queue: {e}")
            
    return active_trades

def push_trade_to_mt5(trade):
    import MetaTrader5 as mt5
    
    asset = trade.get("Asset")
    direction = trade.get("Direction")
    sl_val = float(trade.get("Stop_Loss", 0.0))
    tp_val = float(trade.get("Take_Profit", 0.0))
    conviction = float(trade.get("Conviction_Score", 0.5))
    payload = trade.get("Original_Payload", {})
    
    logger.info(f"Initializing MT5 connection to execute Trade {trade.get('Trade_ID')} ({asset} {direction})...")
    if not mt5.initialize():
        logger.error("MT5 Initialization failed.")
        return False
        
    try:
        # Check if the symbol exists and is visible
        info = mt5.symbol_info(asset)
        if not info:
            logger.error(f"Symbol {asset} not found in MT5.")
            return False
            
        if not info.visible:
            if not mt5.symbol_select(asset, True):
                logger.error(f"Failed to select symbol {asset}.")
                return False
                
        # Check for duplicate open positions
        positions = mt5.positions_get(symbol=asset)
        if positions:
            logger.warning(f"[DUPLICATE_GUARD] Position already exists for symbol {asset}. Execution cancelled.")
            return False
            
        tick = mt5.symbol_info_tick(asset)
        if not tick:
            logger.error(f"Failed to get current price quote for {asset}.")
            return False
            
        # Determine execution price and order type
        if direction.upper() == "BUY":
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        elif direction.upper() == "SELL":
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL
        else:
            logger.error(f"Invalid direction: {direction}")
            return False
            
        # Determine volume size
        # Try to use size_multiplier from original payload, otherwise default to min volume
        size_mult = float(payload.get("size_multiplier", 1.0))
        # Default standard Kelly lot size calculation or baseline
        volume = max(info.volume_min, round(size_mult * 0.01 / info.volume_step) * info.volume_step)
        volume = min(info.volume_max, volume)
        
        # Round stops to symbol digits
        digits = info.digits
        price = round(price, digits)
        sl_val = round(sl_val, digits) if sl_val > 0 else 0.0
        tp_val = round(tp_val, digits) if tp_val > 0 else 0.0
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": asset,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl_val),
            "tp": float(tp_val),
            "deviation": 20,
            "magic": 142, # MAGIC_NUMBER
            "comment": f"HITL_Push_{trade.get('Trade_ID')}"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        logger.info(f"Sending trade request to MT5: {asset} {direction} {volume} lots at {price} (SL: {sl_val}, TP: {tp_val})...")
        res = mt5.order_send(request)
        
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[SUCCESS] Executed manual trade on {asset} (Ticket: {res.order})")
            
            # Write to shadow ledger (Directive: Flawless Logic Audit)
            try:
                ledger_exists = LEDGER_PATH.exists()
                with open(LEDGER_PATH, "a", encoding='utf-8') as lf:
                    if not ledger_exists:
                        lf.write("timestamp,symbol,direction,lots,price,sl,conviction,hmm_regime\n")
                    # Extract regime or default to RANGE
                    regime = payload.get("wasserstein_state", "RANGE")
                    lf.write(f"{datetime.now().isoformat()},{asset},{direction},{volume},{price},{sl_val},{conviction},{regime}\n")
                logger.info("[LEDGER] Written ledger entry to simulated_ledger.csv")
            except Exception as le:
                logger.error(f"Failed to write shadow ledger entry: {le}")
                
            return True
        else:
            logger.error(f"[FAIL] MT5 order rejected. Retcode: {res.retcode if res else 'None'} | Comment: {res.comment if res else 'No response'}")
            return False
            
    except Exception as e:
        logger.error(f"Error executing trade on MT5: {e}")
        return False
    finally:
        mt5.shutdown()

def process_trade_by_id(trade_id):
    active_trades = prune_stale_trades()
    
    target_trade = None
    remaining_trades = []
    for t in active_trades:
        if t.get("Trade_ID") == trade_id:
            target_trade = t
        else:
            remaining_trades.append(t)
            
    if not target_trade:
        logger.error(f"Trade ID {trade_id} not found or is STALE.")
        return False
        
    # Attempt to execute
    success = push_trade_to_mt5(target_trade)
    
    if success:
        # Prune from queue by writing remaining trades
        try:
            with open(PENDING_PATH, "w") as f:
                json.dump(remaining_trades, f, indent=2)
            logger.info(f"Pruned Trade {trade_id} from approvals queue.")
        except Exception as e:
            logger.error(f"Failed to update queue file: {e}")
    else:
        logger.error(f"Execution failed for Trade {trade_id}. Leaving in queue.")
        
    return success

def run_interactive_loop():
    logger.info("Entering interactive HITL operator command console.")
    logger.info("Type 'Push Trade <ID> to MT5' to execute, 'list' to view pending setups, or 'exit' to quit.")
    
    while True:
        try:
            cmd = input("\nHITL-Operator> ").strip()
            if not cmd:
                continue
                
            if cmd.lower() in ['exit', 'quit', 'q']:
                logger.info("Exiting command loop.")
                break
                
            elif cmd.lower() == 'list':
                active = prune_stale_trades()
                if not active:
                    print("No pending trade approvals in queue.")
                else:
                    print("\n--- PENDING TRADE APPROVALS ---")
                    for t in active:
                        print(f"ID: {t['Trade_ID']} | {t['Asset']} {t['Direction']} | SL: {t['Stop_Loss']} | TP: {t['Take_Profit']} | Conviction: {t['Conviction_Score']}")
                    print("--------------------------------")
                    
            else:
                # Regex match for command: "Push Trade 001 to MT5" or just "push 001"
                match_push = re.search(r'(?:push\s+trade\s+|push\s+)(\d+)', cmd, re.IGNORECASE)
                if match_push:
                    trade_id = f"{int(match_push.group(1)):03d}"
                    process_trade_by_id(trade_id)
                else:
                    print("Unknown command. Supported commands: 'list', 'Push Trade <ID> to MT5', 'exit'")
        except KeyboardInterrupt:
            print()
            logger.info("Interrupt received. Exiting.")
            break
        except Exception as e:
            logger.error(f"Error in console loop: {e}")

def main():
    parser = argparse.ArgumentParser(description="Human-in-the-Loop MT5 Trade Executor")
    parser.add_argument("-t", "--trade", type=str, help="ID of the pending trade to execute (e.g. 001)")
    parser.add_argument("raw_cmd", type=str, nargs="*", help="Raw command (e.g. Push Trade 001 to MT5)")
    args = parser.parse_args()
    
    if args.trade:
        trade_id = f"{int(args.trade):03d}"
        process_trade_by_id(trade_id)
    elif args.raw_cmd:
        cmd_str = " ".join(args.raw_cmd)
        match_push = re.search(r'(?:push\s+trade\s+|push\s+)(\d+)', cmd_str, re.IGNORECASE)
        if match_push:
            trade_id = f"{int(match_push.group(1)):03d}"
            process_trade_by_id(trade_id)
        else:
            logger.error(f"Unrecognized command arguments: {cmd_str}")
    else:
        run_interactive_loop()

if __name__ == "__main__":
    main()
