class TradePlan:
    def __init__(self, direction="BUY", entry=0.0, sl=0.0, tp_ladder=None):
        self.direction = direction
        self.entry_mid = entry
        self.sl_price = sl
        self.tp_prices = tp_ladder if tp_ladder else []
    def display(self) -> str:
        return f"RIMBA TARGET MATRIX -> ENTRY: {self.entry_mid} | SL: {self.sl_price}"

def calculate_trade_plan(active_zone) -> TradePlan:
    width = active_zone.width
    # Guard against 0 width zones
    if width <= 0:
        width = 1.0 
        
    if active_zone.zone_type.value == "DEMAND":
        # BUY Plan
        entry = active_zone.high
        # Dynamic SL: placed 2x zone width below the zone's low boundary
        sl = active_zone.low - (2.0 * width)
        
        # Calculate point risk for dynamic TP
        risk_pts = entry - sl
        
        # TP ladder based on Risk multiples
        tp_ladder = [
            entry + (risk_pts * 0.5), # TP 1
            entry + (risk_pts * 1.0), # TP 2
            entry + (risk_pts * 1.5), # TP 3
            entry + (risk_pts * 2.0), # TP 4
            entry + (risk_pts * 3.0)  # TP 5
        ]
        return TradePlan(direction="BUY", entry=entry, sl=sl, tp_ladder=tp_ladder)
    else:
        # SELL Plan
        entry = active_zone.low
        # Dynamic SL: placed 2x zone width above the zone's high boundary
        sl = active_zone.high + (2.0 * width)
        
        # Calculate point risk for dynamic TP
        risk_pts = sl - entry
        
        # TP ladder based on Risk multiples
        tp_ladder = [
            entry - (risk_pts * 0.5), # TP 1
            entry - (risk_pts * 1.0), # TP 2
            entry - (risk_pts * 1.5), # TP 3
            entry - (risk_pts * 2.0), # TP 4
            entry - (risk_pts * 3.0)  # TP 5
        ]
        return TradePlan(direction="SELL", entry=entry, sl=sl, tp_ladder=tp_ladder)

def adjust_tp_for_spread(plan, spread_pts) -> TradePlan:
    # Spread is in points. For dynamic wide TP, spread adjustment is less critical, but we can return it safely.
    return plan
