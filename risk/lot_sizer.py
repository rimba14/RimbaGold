from dataclasses import dataclass

@dataclass
class SizingOutput:
    lot_size: float = 0.01

def compute_lot_size(**kwargs) -> SizingOutput:
    return SizingOutput()

def scale_down_for_drawdown(lot, *args):
    return lot
