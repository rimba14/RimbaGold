class ZoneRegistry:
    def __init__(self):
        self._cooldown_zones = {}

    def is_zone_cooled_down(self, zone_id: str, current_time: float) -> bool:
        if zone_id in self._cooldown_zones:
            if current_time < self._cooldown_zones[zone_id]:
                return True
            del self._cooldown_zones[zone_id]
        return False

    def lock_zone_profile(self, zone_id: str, cooldown_minutes: float):
        import time
        self._cooldown_zones[zone_id] = time.time() + (cooldown_minutes * 60)

    def update(self, all_zones, timeframe, current_price, now):
        pass
    def mark_zone_entered(self, zone_id: str):
        pass
    def _persist(self):
        pass
