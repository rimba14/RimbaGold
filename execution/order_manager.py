import logging
import MetaTrader5 as mt5

log = logging.getLogger("rimba_gold.order_mgr")

class OrderOutput:
    def __init__(self):
        self.success = True
        self.ticket = 0
        self.direction = "BUY"
        self.open_price = 0.0
        self.lot_size = 0.01
        self.error = None

class OrderManager:
    def __init__(self, feeder):
        self.feeder = feeder

    def enter_trade(self, plan, lot_size) -> OrderOutput:
        out = OrderOutput()
        out.direction = plan.direction
        out.lot_size = lot_size
        
        symbol = self.feeder.symbol
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            out.success = False
            out.error = "No tick available"
            return out
            
        price = tick.ask if plan.direction == "BUY" else tick.bid
        
        # Ensure TP is mathematically valid against live execution price
        valid_tp = 0.0
        if hasattr(plan, 'tp_prices') and plan.tp_prices:
            valid_tp = plan.tp_prices[0]
            if plan.direction == "BUY":
                for tp in plan.tp_prices:
                    if tp > price + 0.5:
                        valid_tp = tp
                        break
            else:
                for tp in plan.tp_prices:
                    if tp < price - 0.5:
                        valid_tp = tp
                        break
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": mt5.ORDER_TYPE_BUY if plan.direction == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": round(float(plan.sl_price), info.digits),
            "tp": round(float(valid_tp), info.digits),
            "deviation": 20,
            "magic": 202601,
            "comment": "Rimba Flip",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            out.success = True
            out.ticket = res.order
            out.open_price = res.price
            log.info(f"[ORDER_MGR] Entered {plan.direction} {symbol} #{out.ticket} @ {out.open_price}")
        else:
            out.success = False
            out.error = res.comment if res else "Unknown Error"
            log.error(f"[ORDER_MGR] Failed to enter {plan.direction}: {out.error}")
            
        return out

    def close_position(self, ticket: int, symbol: str, direction: str, volume: float, comment="RIMBA_CLOSE") -> bool:
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error(f"[ORDER_MGR] Cannot close #{ticket}, no tick for {symbol}")
            return False
            
        action_type = mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY
        price = tick.bid if direction == "BUY" else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": action_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 202601,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"[ORDER_MGR] Closed {direction} position #{ticket} successfully.")
            return True
        else:
            err = res.comment if res else "Unknown Error"
            log.error(f"[ORDER_MGR] Failed to close #{ticket}: {err}")
            return False

    def modify_sl_tp(self, ticket: int, symbol: str, sl: float, tp: float) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp),
        }
        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"[ORDER_MGR] Modified #{ticket} SL to {sl}, TP to {tp}")
            return True
        else:
            err = res.comment if res else "Unknown Error"
            log.error(f"[ORDER_MGR] Failed to modify #{ticket}: {err}")
            return False
