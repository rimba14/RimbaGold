class NewsOutput:
    def __init__(self):
        self.blocked = False
        self.reason = "Clear Horizon"
        self.event_name = None

class NewsGate:
    def is_clear(self, now) -> NewsOutput:
        return NewsOutput()
