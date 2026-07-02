MIN_CONVICTION = 0.62

class ConvictionBreakdown:
    def __init__(self):
        self.total = 0.85

def score_zones(zones, **kwargs) -> dict:
    return {id(z): ConvictionBreakdown() for z in zones}
