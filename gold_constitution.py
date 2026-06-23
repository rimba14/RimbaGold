# ============================================================
# RIMBA GOLD - gold_constitution.py (PRODUCTION BUILD v1.1.0)
# Constitutional laws protecting structural capital execution.
# ============================================================
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone
import config as cfg

log = logging.getLogger("rimba_gold.constitution")

class ConstitutionViolation(Exception):
    """Raised when an order request violates a core strategy law."""
    pass

@dataclass
class TradeProposal:
    """Immutable technical snapshot evaluated prior to market routing."""
    symbol:          str
    direction:       str          
    timeframe:       str          
    zone_low:        float
    zone_high:       float
    zone_width:      float        
    entry_price:     float
    sl_price:        float
    tp_prices:       list[float]  
    lot_size:        float
    account_equity:  float
    account_balance: float
    spread_pts:      float
    conviction:      float
    session:         str
    timestamp:       datetime
    account_id:      int          # Enforced account authentication parameter
    news_event:      Optional[str] = None
    open_positions:  int = 0

def _law_1_symbol_lock(p: TradeProposal):
    """Restricts system execution to XAUUSD vectors only."""
    if p.symbol.upper().replace(" ", "") != cfg.SYMBOL:
        raise ConstitutionViolation(f"[LAW-1] SYMBOL LOCK: {p.symbol} is not authorized.")

def _law_2_one_position_max(p: TradeProposal):
    """Enforces execution cap to guarantee process isolation."""
    if p.open_positions >= cfg.MAX_POSITIONS:
        raise ConstitutionViolation(f"[LAW-2] MAX_POSITIONS: Layering block active. Open Count: {p.open_positions}")

def _law_3_max_risk(p: TradeProposal):
    """Limits aggregate asset exposure to an ironclad capital allocation limit."""
    risk_pts = abs(p.entry_price - p.sl_price)
    if risk_pts <= 0:
        raise ConstitutionViolation("[LAW-3] Invalid stop distance calculation.")
    risk_usd = p.lot_size * risk_pts * 100.0
    max_risk_usd = p.account_equity * cfg.MAX_RISK_PCT
    if risk_usd > (max_risk_usd + 0.01):
        raise ConstitutionViolation(f"[LAW-3] MAX_RISK: ${risk_usd:.2f} exposure exceeds cap of ${max_risk_usd:.2f}")

def _law_4_minimum_rr(p: TradeProposal):
    """Ensures structural setups meet minimum expectancy profiles."""
    if not p.tp_prices or len(p.tp_prices) < 4:
        raise ConstitutionViolation("[LAW-4] Primary target plan unavailable.")
    risk_pts = abs(p.entry_price - p.sl_price)
    reward_pts = abs(p.tp_prices[3] - p.entry_price)  # Anchor to TP4 milestone
    if risk_pts <= 0:
        raise ConstitutionViolation("[LAW-4] Erroneous risk parameters calculated.")
    if (reward_pts / risk_pts) < cfg.MAX_RISK_PCT * 150: # Enforce 1:1.5 threshold
        raise ConstitutionViolation(f"[LAW-4] MIN_RR: Expected target R:R {(reward_pts / risk_pts):.2f} below technical floor.")

def _law_5_lot_bounds(p: TradeProposal):
    """Defends broker allocation parameters against execution leaks."""
    if not (cfg.MIN_LOT <= p.lot_size <= cfg.MAX_LOT):
        raise ConstitutionViolation(f"[LAW-5] LOT_BOUNDS: Allocation packet size {p.lot_size} outside parameters.")

def _law_6_news_blackout(p: TradeProposal):
    """Implements systemic risk shield during high-impact market data releases."""
    if p.news_event and any(e in p.news_event.upper() for e in cfg.HIGH_IMPACT_EVENTS):
        raise ConstitutionViolation(f"[LAW-6] NEWS SHIELD: Order blocked due to upcoming token event arrival: {p.news_event}")

def _law_7_sl_correct_side(p: TradeProposal):
    """Validates structural boundary side logic to protect tracking states."""
    if p.direction == "BUY" and p.sl_price >= p.zone_low:
        raise ConstitutionViolation(f"[LAW-7] RISK INVERSION: BUY Stop Loss {p.sl_price} mapped inside zone boundaries.")
    if p.direction == "SELL" and p.sl_price <= p.zone_high:
        raise ConstitutionViolation(f"[LAW-7] RISK INVERSION: SELL Stop Loss {p.sl_price} mapped inside zone boundaries.")

def _law_8_tp_ordering(p: TradeProposal):
    """Validates clear directional divergence mapping for target levels."""
    for i in range(1, len(p.tp_prices)):
        if p.direction == "BUY" and p.tp_prices[i] <= p.tp_prices[i - 1]:
            raise ConstitutionViolation(f"[LAW-8] PLAN CORRUPTION: Target ladder inversion at profile index {i}")
        if p.direction == "SELL" and p.tp_prices[i] >= p.tp_prices[i - 1]:
            raise ConstitutionViolation(f"[LAW-8] PLAN CORRUPTION: Target ladder inversion at profile index {i}")

def _law_9_margin_buffer(p: TradeProposal):
    """Validates free margin allocation boundaries before transaction execution."""
    est_margin = p.lot_size * 1000.0
    if p.account_balance > 0 and (est_margin / p.account_balance) > (1.0 - cfg.MARGIN_BUFFER_PCT):
        raise ConstitutionViolation("[LAW-9] MARGIN SHIELD: Transaction request violates allocation limits.")

def _law_10_strict_account_lock(p: TradeProposal):
    """Implements non-bypassable strategy alignment parameter check."""
    if int(p.account_id) != cfg.TARGET_GOLD_ACCOUNT:
        raise ConstitutionViolation(
            f"[LAW-10] ILLEGAL ROUTING PACKET: System locked to account {cfg.TARGET_GOLD_ACCOUNT}. "
            f"Transaction payload intercepted account assignment path: {p.account_id}"
        )

LAWS = [
    _law_1_symbol_lock,
    _law_2_one_position_max,
    _law_3_max_risk,
    _law_4_minimum_rr,
    _law_5_lot_bounds,
    _law_6_news_blackout,
    _law_7_sl_correct_side,
    _law_8_tp_ordering,
    _law_9_margin_buffer,
    _law_10_strict_account_lock
]

def enforce(proposal: TradeProposal) -> bool:
    """Executes all structural strategy laws against the order request snapshot."""
    for law in LAWS:
        try:
            law(proposal)
        except ConstitutionViolation as e:
            log.error("CONSTITUTION ACTION VETOED: %s", str(e))
            raise
    log.info("CONSTITUTION APPROVED — Verified %s Routing to Terminal %s", proposal.direction, proposal.account_id)
    return True
