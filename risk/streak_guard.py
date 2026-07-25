import time
from datetime import datetime

class StreakCooldownGuard:
    def __init__(self, max_consecutive_losses=2, cooldown_minutes=15, recovery_ladder=[0.50, 0.75, 1.00]):
        self.max_losses = max_consecutive_losses
        self.cooldown_seconds = cooldown_minutes * 60
        self.recovery_ladder = recovery_ladder
        
        # State tracking
        self.consecutive_losses = 0
        self.cooldown_active_until = None
        self.ladder_index = 0
        self.in_recovery = False

    def record_trade_result(self, pnl: float):
        """
        Call this immediately when a position closes (where dd_guard.add_closed_pnl fires).
        """
        if pnl < 0:
            self.consecutive_losses += 1
            # If a loss occurs while in recovery, immediately re-trigger cooldown
            if self.in_recovery or self.consecutive_losses >= self.max_losses:
                self.cooldown_active_until = time.time() + self.cooldown_seconds
                self.in_recovery = True
                self.ladder_index = 0  # Reset size recovery ladder to lowest step (50%)
                print(f"[STREAK_GUARD] {self.consecutive_losses} consecutive losses! "
                      f"Cooldown triggered until {datetime.fromtimestamp(self.cooldown_active_until).strftime('%H:%M:%S')}")
        else:
            # Win confirms the edge is back — full reset
            if self.in_recovery or self.consecutive_losses > 0:
                print(f"[STREAK_GUARD] Winning trade printed (${pnl:.2f}). Streak reset. Full edge restored.")
            self.consecutive_losses = 0
            self.in_recovery = False
            self.ladder_index = 0
            self.cooldown_active_until = None

    def can_trade(self, current_spread_pts: float, max_allowed_spread: float) -> tuple[bool, str]:
        """
        Call in your pre-execution gate alongside news_gate and dd_guard.
        """
        now = time.time()
        if self.cooldown_active_until is not None:
            if now < self.cooldown_active_until:
                remaining_sec = int(self.cooldown_active_until - now)
                return False, f"STREAK_COOLDOWN_ACTIVE ({remaining_sec // 60}m {remaining_sec % 60}s remaining)"
            else:
                # Timer elapsed, but we must check for toxic spread
                if current_spread_pts > max_allowed_spread:
                    self.cooldown_active_until = now + self.cooldown_seconds
                    return False, "COOLDOWN_EXTENDED_TOXIC_SPREAD"
                    
                # Cooldown time has elapsed and spread is clean, enter recovery mode
                if self.in_recovery and self.consecutive_losses >= self.max_losses:
                    print("[STREAK_GUARD] Cooldown timer elapsed. Entering Size Recovery Mode.")
        return True, "PRISTINE"

    def apply_ramp(self, base_lot_size: float) -> float:
        """
        Call during the position sizing step after dd_guard.apply_scale().
        """
        if not self.in_recovery:
            return base_lot_size
        
        multiplier = self.recovery_ladder[self.ladder_index]
        ramped_size = round(base_lot_size * multiplier, 2)
        
        # Advance ladder index for subsequent trades (caps at 1.0)
        if self.ladder_index < len(self.recovery_ladder) - 1:
            self.ladder_index += 1
            
        print(f"[STREAK_GUARD] Ramp applied ({multiplier*100:.0f}% size): {base_lot_size} -> {ramped_size} lots")
        return ramped_size
