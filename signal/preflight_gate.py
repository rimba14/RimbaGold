class GateResult:
    def __init__(self, name: str, passed: bool, msg: str = ""):
        self.name = name
        self.passed = passed
        self.msg = msg

class PreflightOutput:
    def __init__(self):
        self.all_passed = True
        self.failed_gates = []

class PreflightGate:
    def __init__(self, **kwargs):
        self.spread_pts = kwargs.get('spread_pts', 0.0)

    def _gate_9_net_tp1_check(self, plan) -> GateResult:
        """ Enforce a minimum net profit margin on the initial take-profit target 
        after accounting for the dynamic broker spread.
        """
        import config as cfg
        tf = getattr(plan, "timeframe", cfg.PRIMARY_TF)
        
        min_net = cfg.MIN_NET_TP1_PTS.get(tf, 6.0)
        tp1_dist = abs(plan.tp_prices[0] - plan.entry_mid) if getattr(plan, "tp_prices", None) else 0.0
        net_profit = tp1_dist - self.spread_pts
        
        if net_profit < min_net:
            return GateResult(
                "GATE_9_NET_TP1", False,
                f"Edge consumed by spread. Net TP1 {net_profit:.2f} pts < min floor {min_net:.1f} pts "
                f"(TP1_dist={tp1_dist:.2f} - dynamic_spread={self.spread_pts:.2f})."
            )
        return GateResult("GATE_9_NET_TP1", True, "Clear profit margin confirmed.")

    def run(self, plan) -> PreflightOutput:
        out = PreflightOutput()
        
        gate_9 = self._gate_9_net_tp1_check(plan)
        if not gate_9.passed:
            out.all_passed = False
            out.failed_gates.append(gate_9.msg)
            
        return out
