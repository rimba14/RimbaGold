class DrawdownState:
    def __init__(self):
        self.daily_pnl_usd = 0.0

class DrawdownGuard:
    def __init__(self):
        self.state = DrawdownState()
    def update_equity(self, equity, balance, daily_pnl=0.0):
        pass
    def can_trade(self) -> tuple[bool, str]:
        return True, "Clear Parameters"
    def add_closed_pnl(self, pnl: float):
        pass
    def apply_scale(self, lot_size: float) -> float:
        return lot_size
