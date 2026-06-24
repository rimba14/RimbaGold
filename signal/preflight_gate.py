import numpy as np

class PreflightOutput:
    def __init__(self):
        self.all_passed = True
        self.failed_gates = []

class PreflightGate:
    def __init__(self, **kwargs):
        self.closes = kwargs.get('closes', np.array([]))
        self.highs = kwargs.get('highs', np.array([]))
        self.lows = kwargs.get('lows', np.array([]))
        self.active_zone = kwargs.get('active_zone')
        
    def _calc_ema(self, arr, period):
        if len(arr) == 0:
            return 0
        alpha = 2 / (period + 1)
        ema = np.zeros_like(arr)
        ema[0] = arr[0]
        for i in range(1, len(arr)):
            ema[i] = (arr[i] * alpha) + (ema[i - 1] * (1 - alpha))
        return ema[-1]

    def _calc_tr_variance(self, period):
        if len(self.highs) < period + 1:
            return float('inf')
        
        # Calculate True Range for the last 'period' bars
        trs = []
        for i in range(1, period + 1):
            idx = -i
            h = self.highs[idx]
            l = self.lows[idx]
            prev_c = self.closes[idx - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
            
        return np.var(trs)

    def run(self, plan) -> PreflightOutput:
        out = PreflightOutput()
        
        if len(self.closes) < 22:
            # Not enough data, fail safely
            out.all_passed = False
            out.failed_gates.append("INSUFFICIENT_DATA")
            return out
            
        current_close = self.closes[-1]
        
        # 1. Volatility Contraction Check (VCS)
        var_5 = self._calc_tr_variance(5)
        var_20 = self._calc_tr_variance(20)
        
        if var_5 >= var_20:
            out.all_passed = False
            out.failed_gates.append("VOLATILITY_CONTRACTION_FAILED (VCS)")
            
        # 2. Geometric Confirmation Check (LL-HL Structures)
        ema_21 = self._calc_ema(self.closes, 21)
        darvas_top = self.active_zone.high if self.active_zone else float('inf')
        
        if current_close <= ema_21 or current_close <= darvas_top:
            out.all_passed = False
            out.failed_gates.append("GEOMETRIC_CONFIRMATION_FAILED (Pivot/Darvas)")
            
        return out
