from dataclasses import dataclass

@dataclass
class ATRSnapshot:
    atr: float = 25.0

def get_d1_atr(symbol, h_d1, l_d1, c_d1, period=14, ttl_sec=3600) -> ATRSnapshot:
    return ATRSnapshot()
