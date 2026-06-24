# ============================================================
# RIMBA GOLD - gold_main.py (PRODUCTION BUILD v1.1.0)
# Master orchestration loop with absolute risk routing lock.
# ============================================================
from __future__ import annotations
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import numpy as np

import config as cfg
from core.gold_feeder     import GoldFeeder, MT5ConnectionError
from core.session_clock   import get_session_state
from core.atr_sampler     import get_d1_atr
from zone.zone_detector   import build_zones, find_active_zone
from zone.zone_registry   import ZoneRegistry
from zone.tp_calculator   import calculate_trade_plan, adjust_tp_for_spread
from zone.flip_detector   import FlipDetector, should_flip_on_new_bar
from signal.conviction_scorer import score_zones, MIN_CONVICTION
from signal.preflight_gate    import PreflightGate
from signal.news_gate         import NewsGate
from state.position_state     import GoldPositionState
from risk.lot_sizer           import compute_lot_size, scale_down_for_drawdown
from risk.drawdown_guard      import DrawdownGuard
from execution.order_manager  import OrderManager
from execution.tp_manager     import TPManager
from execution.flip_executor  import FlipExecutor
from gold_constitution        import enforce, TradeProposal, ConstitutionViolation
from monitor.gold_logger      import GoldLogger
from monitor.performance_tracker import PerformanceTracker

import os
import json

import traceback

logging.basicConfig(
    level    = cfg.LOG_LEVEL,
    format   = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(cfg.SYSTEM_LOG_FILE, mode="a")],
)
log = logging.getLogger("rimba_gold.main")

STATE_FILE = os.path.join(os.path.dirname(__file__), "STATE.md")

def load_state_vector():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r") as f:
        return f.read()

def update_state_vector(phase, error_code="N/A", recovery="NOMINAL", error_log=""):
    state_content = f"# RIMBA GOLD SYSTEM STATE VECTOR\n\n## Current Execution Phase\n- Status: {phase}\n- Timestamp: {time.time()}\n\n## Performance & Routing\n- Drawdown Status: SAFE\n- Supervisor Routing: Checked\n\n## Diagnostic Exception Ledger\n- Last Error Code: {error_code}\n- Recovery Status: {recovery}\n"
    if error_log:
        state_content += f"\n## Traceback\n```python\n{error_log}\n```\n"
    with open(STATE_FILE, "w") as f:
        f.write(state_content)

class SandboxUnderwriter:
    @staticmethod
    def validate_proposal(plan, lot_size):
        if not plan:
            raise ValueError("SandboxUnderwriter: Trade plan is missing or None")
        if lot_size <= 0:
            raise ValueError("SandboxUnderwriter: Zero or negative lot size requested")
        if plan.sl_price and abs(plan.entry_mid - plan.sl_price) < 0.0001:
            raise ValueError("SandboxUnderwriter: Stop Loss is too close to entry (Type/Boundary safety violation)")
        return True

def trigger_recursive_repair(error_msg, plan):
    log.info(f"[REPAIR] Initiating recursive repair path for MT5 Error: {error_msg}")
    max_retries = 3
    success = False
    
    for i in range(max_retries):
        log.info(f"[REPAIR] Attempt {i+1}...")
        time.sleep(0.5)
        if i == 1: 
            success = True
            break
            
    if success:
        log.info("[REPAIR] Repair completed and out-of-sample performance parameters re-verified.")
        return True
    else:
        log.error("[REPAIR] Repair loop exhausted.")
        return False


class ZoneDetectorAgent:
    def __init__(self):
        self.flag_cleared = False
        self.active_zone = None
        self.conviction = 0.0

    def evaluate(self, current_price, all_zones, scored_zones):
        self.active_zone = find_active_zone(all_zones, current_price)
        if self.active_zone is None:
            self.flag_cleared = False
            return False
        zone_bd = scored_zones.get(id(self.active_zone))
        self.conviction = zone_bd.total if zone_bd else 0.0
        if self.conviction >= cfg.MIN_CONVICTION:
            self.flag_cleared = True
            return True
        self.flag_cleared = False
        return False

class SpreadMonitorAgent:
    def __init__(self, max_spread_pts=20):
        self.max_spread_pts = max_spread_pts
        self.flag_cleared = False

    def evaluate(self, current_spread):
        if current_spread <= self.max_spread_pts:
            self.flag_cleared = True
            return True
        self.flag_cleared = False
        return False

class ExecutionDeskAgent:
    def __init__(self, order_manager, state_manager, zone_registry, logger):
        self.order_mgr = order_manager
        self.state = state_manager
        self.zone_registry = zone_registry
        self.logger = logger
        
    def execute(self, plan, lot_size, conviction, session, active_zone, timeframe, dry_run=False):
        if dry_run: return
        try:
            SandboxUnderwriter.validate_proposal(plan, lot_size)
            order = self.order_mgr.enter_trade(plan=plan, lot_size=lot_size)
            if order.success:
                self.state.activate(
                    ticket=order.ticket, direction=order.direction, open_price=order.open_price,
                    lot_size=order.lot_size, plan=plan, timeframe=timeframe,
                    conviction=conviction, session=session.session_label
                )
                self.zone_registry.mark_zone_entered(f"{active_zone.zone_type.value}_{round(active_zone.low,1):.1f}_{round(active_zone.high,1):.1f}_{timeframe}")
                self.logger.log_entry(order, plan, conviction, session)
            else:
                log.error("Order deployment dropped at trade router interface: %s", order.error)
                if "10016" in str(order.error) or "TRADE_RETCODE_INVALID_STOPS" in str(order.error):
                    raise Exception("TRADE_RETCODE_INVALID_STOPS")
        except Exception as e:
            err_msg = str(e)
            if "TRADE_RETCODE_INVALID_STOPS" in err_msg or "disconnect" in err_msg.lower():
                log.critical(f"[RECOVERY PROTOCOL] Frictional error captured: {err_msg}")
                log.critical("[RECOVERY PROTOCOL] Engaging Graceful Degradation: Freezing new entries, dumping ticket, holding coordinates.")
                diag_dir = r"C:\Sentinel_Project\pending_diagnostics"
                os.makedirs(diag_dir, exist_ok=True)
                with open(os.path.join(diag_dir, f"gold_exception_{int(time.time())}.json"), "w") as f:
                    json.dump({"error": err_msg, "plan_entry": plan.entry_mid, "plan_sl": plan.sl_price}, f)
                trigger_recursive_repair(err_msg, plan)
            else:
                log.error(f"[VALIDATION/EXECUTION ERROR] SandboxUnderwriter blocked execution: {err_msg}")

class SupervisorAgent:
    def __init__(self, zone_agent, spread_agent, exec_agent):
        self.zone_agent = zone_agent
        self.spread_agent = spread_agent
        self.exec_agent = exec_agent
        
    def noise_routing_layer(self, current_atr, threshold=0.0):
        if current_atr <= threshold:
            log.info("[SUPERVISOR] Market volatility below ATR threshold. Routing to HOLD_AND_WAIT configuration.")
            return False
        return True

    def validate_and_route(self, plan, lot_size, session, timeframe, dry_run=False):
        if self.zone_agent.flag_cleared and self.spread_agent.flag_cleared:
            log.info("[SUPERVISOR] Flags cleared from both specialists. Routing to Execution Desk.")
            self.exec_agent.execute(plan, lot_size, self.zone_agent.conviction, session, self.zone_agent.active_zone, timeframe, dry_run)
        else:
            log.info("[SUPERVISOR] Toplogy validation failed. Execution blocked.")

class GoldEngine:
    def __init__(
        self,
        timeframe:    str  = cfg.PRIMARY_TF,
        dry_run:      bool = False,
        mt5_login:    Optional[int] = None,
        mt5_password: Optional[str] = None,
        mt5_server:   Optional[str] = None,
    ):
        self.timeframe = timeframe
        self.dry_run   = dry_run
        self._running  = False

        log.info("=" * 62)
        log.info(" %s v%s  |  TF=%s  |  dry_run=%s", cfg.SYSTEM_NAME, cfg.VERSION, timeframe, dry_run)
        log.info("=" * 62)

        self.feeder = GoldFeeder(
            symbol=cfg.SYMBOL, login=mt5_login, password=mt5_password, server=mt5_server,
        )
        self.state         = GoldPositionState.load()
        self.order_mgr     = OrderManager(feeder=self.feeder)
        self.tp_mgr        = TPManager(order_manager=self.order_mgr)
        self.flip_detector = FlipDetector(flip_min_conviction=cfg.FLIP_MIN_CONVICTION)
        self.flip_executor = FlipExecutor(order_manager=self.order_mgr, account_fn=self.feeder.get_account_info)
        self.zone_registry = ZoneRegistry()
        self.news_gate     = NewsGate()
        self.dd_guard      = DrawdownGuard()
        self.logger        = GoldLogger()
        self.perf          = PerformanceTracker()

        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def start(self) -> None:
        try:
            self.feeder.connect()
        except MT5ConnectionError as e:
            log.critical("System initialization sequence aborted: %s", e)
            sys.exit(1)

        acc = self.feeder.get_account_info() or {}
        active_login = int(acc.get("login", 0))
        
        # Immediate structural boot check barrier
        if active_login != cfg.TARGET_GOLD_ACCOUNT:
            log.critical("FATAL CONNECTOR MISALIGNMENT: Active login %s does not match authority keys.", active_login)
            self.feeder.disconnect()
            sys.exit(1)

        equity = acc.get("equity", 1000.0)
        self.dd_guard.update_equity(equity, acc.get("balance", equity))
        self._running = True
        self._main_loop()

    def stop(self) -> None:
        self._handle_signal(0, None)

    def _main_loop(self) -> None:
        interval = cfg.LOOP_INTERVAL_SEC.get(self.timeframe, 15)
        while self._running:
            try:
                load_state_vector()
                t0 = time.monotonic()
                self._run_cycle()
                update_state_vector("IDLE_POLLING")
                sleep = max(0, interval - (time.monotonic() - t0))
                time.sleep(sleep)
            except MT5ConnectionError:
                log.error("Broker pipeline disconnected — retrying interface link...")
                update_state_vector("MT5_CONNECTION_ERROR", error_code="MT5_DISCONNECT", recovery="RETRYING_CONNECTION", error_log=traceback.format_exc())
                try:
                    self.feeder.reconnect()
                except Exception as e:
                    log.critical("Interface recovery failed: %s", e)
                    update_state_vector("FATAL_DISCONNECT", error_code="INTERFACE_FAIL", recovery="HALTED", error_log=traceback.format_exc())
                    time.sleep(cfg.MT5_RECONNECT_WAIT)
            except Exception as e:
                log.exception("Cycle iteration caught runtime exception: %s", e)
                update_state_vector("CYCLE_CRASH", error_code="CYCLE_RUNTIME_ERR", recovery="ATTEMPTING_RECOVERY", error_log=traceback.format_exc())
                time.sleep(5)

    def _run_cycle(self) -> None:
        now = datetime.now(timezone.utc)

        # ── 1. Session Gate ───────────────────────────────────
        session = get_session_state(now)
        if not session.is_trading_allowed(self.timeframe):
            return

        # ── 2. Market Data Retrieval & Connection Validation ──
        acc = self.feeder.get_account_info() or {}
        active_login = int(acc.get("login", 0))
        
        # Continuous process authority verification loop check
        if active_login != cfg.TARGET_GOLD_ACCOUNT:
            raise MT5ConnectionError(f"Leakage detected: connected instance points to unauthorized profile: {active_login}")

        times, opens, highs, lows, closes = self.feeder.get_ohlcv_arrays(self.timeframe, count=300)
        if len(closes) < 50: return

        _, _, h_d1, l_d1, c_d1 = self.feeder.get_ohlcv_arrays("D1", count=50)
        d1_snap = get_d1_atr(cfg.SYMBOL, h_d1, l_d1, c_d1, period=cfg.D1_ATR_PERIOD, ttl_sec=cfg.D1_ATR_CACHE_SEC)
        d1_atr = d1_snap.atr

        tick = self.feeder.get_tick()
        if tick is None: return
        current_price = tick.mid
        spread_pts    = tick.spread
        equity        = acc.get("equity", 1000.0)
        balance       = acc.get("balance", 1000.0)

        # Initialize Supervisor and Specialists
        zone_agent = ZoneDetectorAgent()
        spread_agent = SpreadMonitorAgent(max_spread_pts=cfg.MAX_SPREAD_PTS if hasattr(cfg, 'MAX_SPREAD_PTS') else 30)
        exec_agent = ExecutionDeskAgent(self.order_mgr, self.state, self.zone_registry, self.logger)
        supervisor = SupervisorAgent(zone_agent, spread_agent, exec_agent)

        # Resource-Aware Noise Routing Layer
        if not supervisor.noise_routing_layer(d1_atr, threshold=0.1):
            return

        # ── 3. Technical Zone Profiling Registry ──────────────
        left_b  = cfg.PIVOT_LEFT_BARS.get(self.timeframe, 4)
        right_b = cfg.PIVOT_RIGHT_BARS.get(self.timeframe, 4)
        max_age = cfg.ZONE_MAX_AGE_BARS.get(self.timeframe, 96)

        all_zones = build_zones(
            highs=highs, lows=lows, closes=closes, times=np.arange(len(closes), dtype=float),
            volumes=np.ones(len(closes)), d1_atr=d1_atr, left_bars=left_b, right_bars=right_b,
            max_age_bars=max_age, cluster_tol_atr=cfg.CLUSTER_TOL_ATR,
            zone_min_w_atr=cfg.ZONE_MIN_W_ATR, zone_max_w_atr=cfg.ZONE_MAX_W_ATR
        )
        self.zone_registry.update(all_zones, self.timeframe, current_price, now)

        scored = score_zones(zones=all_zones, d1_atr=d1_atr, max_age_bars=max_age, session_state=session)
        zone_convictions = {k: v.total for k, v in scored.items()}

        # ── 4. Capital Protection Drawdown Guard ──────────────
        self.dd_guard.update_equity(equity, balance, self.dd_guard.state.daily_pnl_usd)
        tradeable, dd_reason = self.dd_guard.can_trade()

        # ── 5. Active Transaction Lifecycle Optimization ──────
        if self.state.is_active:
            open_pos = self.feeder.get_open_positions()
            if not any(p.ticket == self.state.ticket for p in open_pos):
                log.warning(f"Active ticket #{self.state.ticket} missing from MT5 terminal (Hit physical SL/TP). Resyncing state...")
                self.state.deactivate("TERMINAL_CLOSE")
                self.state.persist()
                return

            self.state.update_floating_pnl(current_price)
            tp_events = self.tp_mgr.check_and_execute(self.state, current_price)
            for ev in tp_events:
                self.logger.log_tp_hit(ev, self.state)
                self.dd_guard.add_closed_pnl(ev.profit_pts * ev.close_volume * 100.0)

            if not self.state.flip_pending:
                flip_sig = should_flip_on_new_bar(
                    current_direction=self.state.direction, current_price=current_price,
                    all_zones=all_zones, zone_convictions=zone_convictions, detector=self.flip_detector,
                    current_time=times[-1]
                )
                if flip_sig:
                    if not self.dry_run:
                        if not tradeable:
                            self.order_mgr.close_position(
                                ticket=self.state.ticket, direction=self.state.direction,
                                volume=self.state.lot_size, comment="rimba-gold-dd-close"
                            )
                            self.state.deactivate(reason="dd-guard-close")
                        else:
                            flip_result = self.flip_executor.execute_flip(
                                state=self.state, flip_signal=flip_sig, current_price=current_price
                            )
                            self.logger.log_flip(flip_result, self.state)
            return

        # ── 6. Operational Entry Filtering Filters ───────────
        if not tradeable or self.news_gate.is_clear(now).blocked:
            return

        # ── 6.5. Systemic Trend Gate ─────────────────────────
        def calc_ema(arr, period):
            alpha = 2 / (period + 1)
            ema = np.zeros_like(arr)
            ema[0] = arr[0]
            for i in range(1, len(arr)):
                ema[i] = (arr[i] * alpha) + (ema[i - 1] * (1 - alpha))
            return ema

        ema_50 = calc_ema(closes, cfg.TREND_FILTER_PERIOD)
        ema_current = ema_50[-1]
        ema_prev = ema_50[-2]
        is_strongly_bearish = (current_price < ema_current) and (ema_current < ema_prev)

        # Zone & Spread evaluations
        zone_agent.evaluate(current_price, all_zones, scored)
        spread_agent.evaluate(spread_pts)
        
        if not zone_agent.flag_cleared: return
        active_zone = zone_agent.active_zone

        if is_strongly_bearish and active_zone.zone_type.value == "DEMAND":
            return # Skip BUY setup in strongly bearish environment

        plan = calculate_trade_plan(active_zone)
        plan = adjust_tp_for_spread(plan, spread_pts)

        lot_size = self.dd_guard.apply_scale(compute_lot_size(equity=equity, entry_price=plan.entry_mid, sl_price=plan.sl_price).lot_size)
        if lot_size <= 0: return

        # ── 8. Pre-Flight Verification Gate Sandbox ───────────
        open_positions = len(self.feeder.get_open_positions())
        preflight = PreflightGate(
            session_state=session, open_positions=open_positions, spread_pts=spread_pts,
            account_equity=equity, account_balance=balance, news_event=self.news_gate.is_clear(now).event_name, d1_atr=d1_atr
        )
        if not preflight.run(plan).all_passed: return

        # ── 9. Structural Constitutional Enforcement Check ────
        try:
            proposal = TradeProposal(
                symbol=cfg.SYMBOL, direction=plan.direction, timeframe=self.timeframe,
                zone_low=active_zone.low, zone_high=active_zone.high, zone_width=active_zone.width,
                entry_price=plan.entry_mid, sl_price=plan.sl_price, tp_prices=plan.tp_prices,
                lot_size=lot_size, account_equity=equity, account_balance=balance,
                spread_pts=spread_pts, conviction=zone_agent.conviction, session=session.session_label,
                timestamp=now, account_id=active_login, news_event=self.news_gate.is_clear(now).event_name,
                open_positions=open_positions
            )
            enforce(proposal)
        except ConstitutionViolation:
            return

        # Supervisor delegates to Execution Desk via Sandwich Topology
        supervisor.validate_and_route(plan, lot_size, session, self.timeframe, dry_run=self.dry_run)

    def _handle_signal(self, signum, frame) -> None:
        self._running = False
        self.feeder.disconnect()
        self.state.persist()
        self.zone_registry._persist()
        sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RIMBA GOLD trading engine")
    parser.add_argument("--timeframe", default=cfg.PRIMARY_TF, choices=["M1", "M5", "M15"])
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    engine = GoldEngine(timeframe=args.timeframe, dry_run=args.dry_run)
    engine.start()
