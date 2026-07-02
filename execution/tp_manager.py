import logging
from dataclasses import dataclass
import config as cfg

log = logging.getLogger("rimba_gold.tp_mgr")

@dataclass
class TPEvent:
    level: int
    price: float
    close_volume: float
    profit_pts: float

class TPManager:
    def __init__(self, order_manager):
        self.order_mgr = order_manager

    def check_and_execute(self, state, current_price) -> list:
        if not state.is_active or not hasattr(state, 'tp_prices') or not state.tp_prices:
            return []
            
        events = []
        symbol = self.order_mgr.feeder.symbol
        
        while state.tp_index < len(state.tp_prices):
            next_tp = state.tp_prices[state.tp_index]
            hit = False
            
            if state.direction == "BUY" and current_price >= next_tp:
                hit = True
                profit_pts = next_tp - state.open_price
            elif state.direction == "SELL" and current_price <= next_tp:
                hit = True
                profit_pts = state.open_price - next_tp
                
            if hit:
                remaining_tps = len(state.tp_prices) - state.tp_index
                close_vol = max(cfg.MIN_LOT, round(state.lot_size / remaining_tps, 2))
                
                if close_vol >= state.lot_size:
                    close_vol = state.lot_size
                    
                log.info(f"[TP_MGR] Tier {state.tp_index+1} hit at {next_tp}! Scaling out {close_vol} lots.")
                
                success = self.order_mgr.close_position(
                    ticket=state.ticket,
                    symbol=symbol,
                    direction=state.direction,
                    volume=close_vol,
                    comment=f"TP_{state.tp_index+1}_SCALE"
                )
                
                if success:
                    events.append(TPEvent(
                        level=state.tp_index+1,
                        price=next_tp,
                        close_volume=close_vol,
                        profit_pts=profit_pts
                    ))
                    
                    state.tp_index += 1
                    state.lot_size = round(state.lot_size - close_vol, 2)
                    
                    if state.lot_size > 0:
                        # Advance SL to BE on first TP hit
                        if state.tp_index == 1:
                            new_sl = state.open_price
                            state.sl_price = new_sl
                            log.info(f"[TP_MGR] Moving SL to Breakeven: {new_sl}")
                            
                        # Set physical TP to the next ladder level
                        next_physical_tp = state.tp_prices[state.tp_index]
                        self.order_mgr.modify_sl_tp(
                            ticket=state.ticket,
                            symbol=symbol,
                            sl=state.sl_price,
                            tp=next_physical_tp
                        )
                        state.persist()
                    else:
                        log.info(f"[TP_MGR] Position #{state.ticket} fully scaled out!")
                        state.deactivate("TP_LADDER_COMPLETE")
                        state.persist()
                        break
                else:
                    log.error(f"[TP_MGR] Failed to execute partial close for Tier {state.tp_index+1}")
                    break
            else:
                break
                
        return events
