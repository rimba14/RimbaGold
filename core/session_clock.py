class SessionState:
    def __init__(self):
        self.session_label = "NY_OPERATIONAL"
    def is_trading_allowed(self, timeframe: str) -> bool:
        return True

def get_session_state(now) -> SessionState:
    return SessionState()
