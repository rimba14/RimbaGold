# ============================================================
# RIMBA GOLD - config.py (PRODUCTION BUILD v1.1.0)
# Single source of truth for all strategy parameters.
# ============================================================
from dataclasses import dataclass, field
from typing import List

# ── Instrument & Absolute Routing Lock ───────────────────────
SYMBOL               = "XAUUSD"
TARGET_GOLD_ACCOUNT  = 25653715
TIMEFRAMES           = ["M1", "M5", "M15"]
PRIMARY_TF           = "M5"          # Default execution timeframe
BROKER_SUFFIX        = ""            # System auto-discovery fallback string

# ── Zone Detection Math ──────────────────────────────────────
PIVOT_LEFT_BARS   = {"M1": 5, "M5": 4, "M15": 3}
PIVOT_RIGHT_BARS  = {"M1": 5, "M5": 4, "M15": 3}
CLUSTER_TOL_ATR   = 0.15             # Zone cluster convergence tolerance
MIN_ZONE_TOUCHES  = 2                # Valid criteria filter
ZONE_MAX_AGE_BARS = {"M1": 240, "M5": 96, "M15": 48}

# Zone width boundaries expressed as multipliers of D1 ATR
ZONE_MIN_W_ATR   = 0.15              # Prevents micro-clusters from registering as zones
ZONE_MAX_W_ATR   = 0.35              # Accommodates true multi-bar institutional zones
FLIP_COOLDOWN_SEC    = 1800          # Minimum 30-minute lock to prevent rapid chattering
TREND_FILTER_PERIOD  = 50            # Lookback window for trend identification

# ── Mathematical Risk & Scale-Out Rules ──────────────────────
TP_MULTIPLES     = [0.5, 1.0, 2.0, 4.0, 8.0]  # W Multipliers from outer boundary
SL_MULTIPLE      = 2.0                        # W Multiplier from opposite boundary
BE_AFTER_TP      = 2                          # Advance Stop-Loss to Breakeven at TP2
TP_CLOSE_FRACS   = [0.20, 0.20, 0.20, 0.20, 0.20]

# ── Session Windows & Regime Constraints (UTC) ──────────────
SESSION_WINDOWS = {
    "ASIA":   {"open": (0, 0), "close": (8, 0)},
    "LONDON": {"open": (7, 0), "close": (16, 0)},
    "NY":     {"open": (13, 0), "close": (22, 0)},
}
SESSION_TF_RULES = {
    "M1":  ["LONDON", "NY"],
    "M5":  ["LONDON", "NY", "ASIA"],
    "M15": ["LONDON", "NY", "ASIA"],
}

# ── Spread Gate Limits ───────────────────────────────────────
MAX_SPREAD_FRAC  = {"M1": 0.35, "M5": 0.20, "M15": 0.12}
MAX_SPREAD_HARD  = {"M1": 4.0,  "M5": 6.0,  "M15": 8.0}

# ── Epistemic Scoring Weights ────────────────────────────────
CONVICTION_WEIGHTS = {
    "touches":       0.30,
    "width_score":   0.20,
    "recency":       0.20,
    "session_align": 0.15,
    "volume_ratio":  0.15,
}
MIN_CONVICTION      = 0.62           # Hard filter gate
FLIP_MIN_CONVICTION = 0.55           # Counter-zone validation cutoff

# ── Risk Parameters & Capital Guardrails ─────────────────────
MAX_RISK_PCT         = 0.01          # Fixed 1% aggregate equity risk threshold
MAX_POSITIONS        = 1             # Structural maximum limit
KELLY_FRACTION       = 0.25          # Fixed Quarter-Kelly fraction scaling
MIN_LOT              = 0.01          # Absolute physical floor
MAX_LOT              = 0.50          # Safe capital capitalization ceiling
MARGIN_BUFFER_PCT    = 0.30          # Minimum unallocated margin profile

# ── Macro Event Horizon Shields ──────────────────────────────
NEWS_BLACKOUT_BEFORE = 30            # Minutes before event arrival
NEWS_BLACKOUT_AFTER  = 15            # Minutes post event resolution
HIGH_IMPACT_EVENTS   = ["NFP", "FOMC", "CPI", "FOMC_MINUTES", "FED_RATE"]

# ── Infrastructure Orchestration Loops ───────────────────────
LOOP_INTERVAL_SEC   = {"M1": 5, "M5": 15, "M15": 30}
MT5_RECONNECT_WAIT  = 10
MT5_MAX_RETRIES     = 5
D1_ATR_PERIOD        = 14
D1_ATR_CACHE_SEC     = 3600

# ── Forensic Metadata Logging Directories ────────────────────
LOG_DIR              = "logs"
LOG_LEVEL            = "INFO"
LOG_JSON             = True
TRADE_LOG_FILE       = "logs/gold_trades.jsonl"
SYSTEM_LOG_FILE      = "logs/gold_system.log"

# ── Decoupled Telemetry Port Allocations ──────────────────────
DASHBOARD_PORT       = 8001          # Clean port separation from CADES (8000)
DASHBOARD_HOST       = "0.0.0.0"
VERSION              = "1.1.0"
SYSTEM_NAME          = "RIMBA-GOLD"
