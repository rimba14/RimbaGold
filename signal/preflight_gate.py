class PreflightOutput:
    def __init__(self):
        self.all_passed = True
        self.failed_gates = []

class PreflightGate:
    def __init__(self, **kwargs):
        pass
    def run(self, plan) -> PreflightOutput:
        return PreflightOutput()
