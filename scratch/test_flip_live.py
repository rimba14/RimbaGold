import MetaTrader5 as mt5
import logging
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.gold_feeder import GoldFeeder
from state.position_state import GoldPositionState
from execution.order_manager import OrderManager
from execution.flip_executor import FlipExecutor
from zone.flip_detector import should_flip_on_new_bar

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test_flip_live")

def run_flip_demo():
    if not mt5.initialize():
        log.error("MT5 init failed")
        return

    # Find an open XAUUSD position
    positions = mt5.positions_get(symbol="XAUUSD")
    if not positions:
        log.error("No active XAUUSD positions found. Cannot demonstrate flip.")
        return
        
    pos = positions[0] # Grab the first one
    ticket = pos.ticket
    direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    volume = pos.volume
    open_price = pos.price_open
    
    log.info(f"Taking control of Ticket #{ticket} ({direction} {volume} lots @ {open_price})")
    
    # Init State
    state = GoldPositionState()
    state.activate(
        ticket=ticket,
        direction=direction,
        lot_size=volume,
        open_price=open_price
    )
    
    # Init Engine Components
    feeder = GoldFeeder(symbol="XAUUSD")
    order_mgr = OrderManager(feeder)
    flip_exec = FlipExecutor(order_manager=order_mgr, account_fn=feeder.get_account_info)
    
    # Synthetically trigger a flip signal
    current_price = mt5.symbol_info_tick("XAUUSD").ask
    log.info(f"Current price is {current_price}. Generating synthetic flip signal...")
    
    flip_sig = should_flip_on_new_bar(state=state, current_price=current_price)
    
    if flip_sig:
        log.info("Flip Signal Generated. Engaging Flip Executor!")
        result = flip_exec.execute_flip(state, flip_sig, current_price)
        if result and result.success:
            log.info("DEMONSTRATION SUCCESSFUL. Positions reversed.")
        else:
            log.error("DEMONSTRATION FAILED.")
    else:
        log.error("Failed to generate flip signal.")

if __name__ == "__main__":
    run_flip_demo()
