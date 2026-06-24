import logging
import numpy as np
import MetaTrader5 as mt5

log = logging.getLogger("rimba_gold.feeder")

class MT5ConnectionError(Exception):
    pass

class MockTick:
    def __init__(self):
        self.mid = 2350.0
        self.spread = 2.0

class GoldFeeder:
    def __init__(self, symbol, login=None, password=None, server=None):
        self.symbol = symbol
        self.login = login
        self.password = password
        self.server = server

    def connect(self):
        log.info("Connecting to MT5 Terminal...")
        if not mt5.initialize():
            log.warning("MT5 link unavailable.")

    def disconnect(self):
        mt5.shutdown()

    def reconnect(self):
        self.disconnect()
        self.connect()

    def get_account_info(self) -> dict:
        info = mt5.account_info()
        if info is None:
            return {"login": self.login or 25653715, "equity": 10000.0, "balance": 10000.0, "currency": "USD"}
        return info._asdict()

    def get_ohlcv_arrays(self, timeframe: str, count: int = 300):
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "D1": mt5.TIMEFRAME_D1
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, count)
        
        if rates is None or len(rates) == 0:
            log.error(f"Failed to fetch OHLCV for {self.symbol}")
            return (np.array([]), np.array([]), np.array([]), np.array([]), np.array([]))
            
        times = np.array([r['time'] for r in rates], dtype=float)
        volumes = np.array([r['tick_volume'] for r in rates], dtype=float)
        highs = np.array([r['high'] for r in rates], dtype=float)
        lows = np.array([r['low'] for r in rates], dtype=float)
        closes = np.array([r['close'] for r in rates], dtype=float)
        
        return (times, volumes, highs, lows, closes)

    def get_tick(self):
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return MockTick()
        class ActiveTick:
            def __init__(self, raw_tick):
                self.mid = (raw_tick.bid + raw_tick.ask) / 2.0
                self.spread = abs(raw_tick.ask - raw_tick.bid) * 100.0
                self.ask = raw_tick.ask
                self.bid = raw_tick.bid
        return ActiveTick(tick)

    def get_open_positions(self) -> list:
        pos = mt5.positions_get(symbol=self.symbol)
        return list(pos) if pos is not None else []
