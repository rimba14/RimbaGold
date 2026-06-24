import numpy as np
from enum import Enum

class ZoneType(Enum):
    DEMAND = "DEMAND"
    SUPPLY = "SUPPLY"

class StructuralZone:
    def __init__(self, low, high, zone_type):
        self.low = low
        self.high = high
        self.width = high - low
        self.zone_type = zone_type

def build_zones(**kwargs) -> list:
    highs = kwargs.get("highs")
    lows = kwargs.get("lows")
    
    if highs is None or lows is None or len(highs) < 20:
        return []
        
    zones = []
    # Very simple recent pivot high / pivot low calculation
    recent_high = np.max(highs[-20:])
    recent_low = np.min(lows[-20:])
    
    # Create a Supply Zone around the recent high
    zones.append(StructuralZone(recent_high - 2.0, recent_high + 1.0, ZoneType.SUPPLY))
    # Create a Demand Zone around the recent low
    zones.append(StructuralZone(recent_low - 1.0, recent_low + 2.0, ZoneType.DEMAND))
    
    return zones

def find_active_zone(all_zones, current_price) -> StructuralZone:
    # Find a zone that the current price is inside or very near
    for z in all_zones:
        if z.low - 1.5 <= current_price <= z.high + 1.5:
            return z
            
    # Default to nearest
    if all_zones:
        return min(all_zones, key=lambda z: min(abs(current_price - z.low), abs(current_price - z.high)))
        
    return None
