class TradePlan:
    def __init__(self, direction="BUY", entry=2345.0, sl=2320.0, tp=2380.0):
        self.direction = direction
        self.entry_mid = entry
        self.sl_price = sl
        self.tp_prices = [tp]
    def display(self) -> str:
        return f"RIMBA TARGET MATRIX -> ENTRY: {self.entry_mid} | SL: {self.sl_price}"

class FlipSignal:
    def __init__(self, new_plan):
        self.new_plan = new_plan
        self.conviction = 0.95

class FlipDetector:
    def __init__(self, flip_min_conviction: float):
        self.flip_min_conviction = flip_min_conviction
        self.last_flip_time = None

def should_flip_on_new_bar(**kwargs):
    state = kwargs.get('state')
    zone_convictions = kwargs.get('zone_convictions', {})
    detector = kwargs.get('detector')
    all_zones = kwargs.get('all_zones', [])
    current_price = kwargs.get('current_price', 0.0)
    current_time = kwargs.get('current_time', None)
    
    if not state or not state.is_active or not detector or not all_zones:
        return None
        
    if current_time and getattr(detector, 'last_flip_time', None) == current_time:
        return None
        
    # Genuine flip logic: if active trade is BUY, and there is a SUPPLY zone with conviction > flip_min_conviction
    for z in all_zones:
        z_id = id(z)
        if z_id in zone_convictions:
            conv = zone_convictions[z_id]
            if conv >= detector.flip_min_conviction:
                # If we are BUY and hit a strong SUPPLY zone
                if state.direction == "BUY" and z.zone_type.value == "SUPPLY":
                    # Require price to actually be in the supply zone
                    if z.low - 1.0 <= current_price <= z.high + 1.0:
                        from zone.tp_calculator import calculate_trade_plan
                        plan = calculate_trade_plan(z)
                        sig = FlipSignal(plan)
                        sig.conviction = conv
                        detector.last_flip_time = current_time
                        return sig
                        
                # If we are SELL and hit a strong DEMAND zone
                if state.direction == "SELL" and z.zone_type.value == "DEMAND":
                    if z.low - 1.0 <= current_price <= z.high + 1.0:
                        from zone.tp_calculator import calculate_trade_plan
                        plan = calculate_trade_plan(z)
                        sig = FlipSignal(plan)
                        sig.conviction = conv
                        detector.last_flip_time = current_time
                        return sig
    return None
