import pytest
from unittest.mock import patch
import time

from risk.streak_guard import StreakCooldownGuard

class TestStreakCooldownGuard:
    
    def test_consecutive_losses_trigger_cooldown(self):
        """Simulate 2 consecutive M1 losses. Confirm the system triggers a 15-min lockout."""
        guard = StreakCooldownGuard(max_consecutive_losses=2, cooldown_minutes=15)
        
        with patch('time.time', return_value=1000.0):
            # First loss
            guard.record_trade_result(-10.0)
            tradeable, reason = guard.can_trade(current_spread_pts=10, max_allowed_spread=30)
            assert tradeable is True
            assert guard.consecutive_losses == 1
            
            # Second loss
            guard.record_trade_result(-15.0)
            tradeable, reason = guard.can_trade(current_spread_pts=10, max_allowed_spread=30)
            assert tradeable is False
            assert "STREAK_COOLDOWN_ACTIVE" in reason
            assert guard.consecutive_losses == 2
            assert guard.cooldown_active_until == 1000.0 + (15 * 60)
            assert guard.in_recovery is True
            
    def test_post_cooldown_entry_sizing(self):
        """Simulate post-15-min entry. Confirm trade 1 after pause uses 50% lot size."""
        guard = StreakCooldownGuard(max_consecutive_losses=2, cooldown_minutes=15, recovery_ladder=[0.50, 0.75, 1.00])
        
        # Trigger lockout
        with patch('time.time', return_value=1000.0):
            guard.record_trade_result(-10.0)
            guard.record_trade_result(-15.0)
            assert guard.in_recovery is True
            
        # Fast forward past the 15 minute (900 seconds) cooldown
        with patch('time.time', return_value=1901.0):
            # Verify can trade
            tradeable, reason = guard.can_trade(current_spread_pts=10, max_allowed_spread=30)
            assert tradeable is True
            assert reason == "PRISTINE"
            
            # Verify 50% lot size ramp
            base_lots = 1.0
            ramped_lots = guard.apply_ramp(base_lots)
            assert ramped_lots == 0.50
            
    def test_winning_trade_clears_recovery(self):
        """Simulate winning trade. Confirm `in_recovery` clears and full sizing restores."""
        guard = StreakCooldownGuard(max_consecutive_losses=2, cooldown_minutes=15, recovery_ladder=[0.50, 0.75, 1.00])
        
        # Trigger lockout
        with patch('time.time', return_value=1000.0):
            guard.record_trade_result(-10.0)
            guard.record_trade_result(-15.0)
            
        # Fast forward and log a win
        with patch('time.time', return_value=1901.0):
            guard.record_trade_result(50.0) # Win!
            
            assert guard.consecutive_losses == 0
            assert guard.in_recovery is False
            assert guard.cooldown_active_until is None
            
            # Verify full sizing restored
            base_lots = 1.0
            ramped_lots = guard.apply_ramp(base_lots)
            assert ramped_lots == 1.00

    def test_toxic_spread_extends_cooldown(self):
        """Confirm that if the timer expires but the spread is toxic, the cooldown extends."""
        guard = StreakCooldownGuard(max_consecutive_losses=2, cooldown_minutes=15)
        
        # Trigger lockout
        with patch('time.time', return_value=1000.0):
            guard.record_trade_result(-10.0)
            guard.record_trade_result(-15.0)
            
        # Fast forward past cooldown, but market is extremely volatile/toxic
        with patch('time.time', return_value=1901.0):
            tradeable, reason = guard.can_trade(current_spread_pts=45, max_allowed_spread=30)
            
            assert tradeable is False
            assert reason == "COOLDOWN_EXTENDED_TOXIC_SPREAD"
            # It should have extended the cooldown by another 900 seconds from 1901.0
            assert guard.cooldown_active_until == 1901.0 + 900
