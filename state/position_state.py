import json
import os

class GoldPositionState:
    def __init__(self):
        self.is_active = False
        self.flip_pending = False
        self.direction = "BUY"
        self.lot_size = 0.01
        self.ticket = 999999
        self.floating_pnl = 0.0

    @classmethod
    def load(cls):
        return cls()

    def update_floating_pnl(self, price: float):
        pass

    def deactivate(self, reason: str):
        self.is_active = False

    def activate(self, **kwargs):
        self.is_active = True
        if "ticket" in kwargs: self.ticket = kwargs["ticket"]
        if "direction" in kwargs: self.direction = kwargs["direction"]
        if "lot_size" in kwargs: self.lot_size = kwargs["lot_size"]

    def persist(self):
        with open("gold_position_state.json", "w") as f:
            json.dump({"active": self.is_active}, f)
