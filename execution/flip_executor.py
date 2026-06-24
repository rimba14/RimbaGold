import logging
log = logging.getLogger("rimba_gold.flip")

class FlipExecutor:
    def __init__(self, order_manager, account_fn):
        self.order_manager = order_manager
        self.account_fn = account_fn
        
    def execute_flip(self, state, flip_signal, current_price):
        symbol = getattr(self.order_manager.feeder, 'symbol', "XAUUSD")
        log.info(f"[FLIP_EXEC] Initiating atomic flip! Reversing {state.direction} position #{state.ticket}")
        
        # 1. Close existing
        closed = self.order_manager.close_position(
            ticket=state.ticket,
            symbol=symbol,
            direction=state.direction,
            volume=state.lot_size,
            comment="RIMBA_FLIP_CLOSE"
        )
        
        if not closed:
            log.error(f"[FLIP_EXEC] CRITICAL: Failed to close #{state.ticket} during flip maneuver!")
            return None
            
        # 2. Open reverse
        new_plan = flip_signal.new_plan
        # Maintain identical lot size for symmetric flip
        new_lot = state.lot_size 
        
        log.info(f"[FLIP_EXEC] Close confirmed. Opening opposite trade ({new_plan.direction})")
        out = self.order_manager.enter_trade(new_plan, new_lot)
        
        if out.success:
            log.info(f"[FLIP_EXEC] Atomic flip complete. New Ticket: #{out.ticket}")
            # Update state
            state.activate(
                direction=out.direction,
                lot_size=out.lot_size,
                ticket=out.ticket,
                open_price=out.open_price,
            )
            state.flip_pending = False
            state.persist()
            return out
        else:
            log.error("[FLIP_EXEC] DISASTER: Closed old position but failed to open new position!")
            state.deactivate("FLIP_ENTRY_FAILED")
            state.persist()
            return None
