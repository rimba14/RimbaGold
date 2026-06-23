# RIMBA GOLD

**XAUUSD-only algorithmic trading system for MetaTrader 5.**  
Architecturally separate from [CADES (rimba-trading)](https://github.com/rimba14/rimba-trading). Do not mix.

---

## What This Is

A production-grade zone-based trading engine for gold on M1, M5, and M15 timeframes. The core edge is a reverse-engineered zone formula from the XAU ALGO XNINE signal system, implemented as a fully autonomous MT5 EA in Python.

**Key design principle:** The zone width `W` is the atomic unit. Everything — TP levels, SL placement, conviction scoring, spread gates — derives from it.

```
TP1 = boundary + 0.5W     SL = opposite boundary − 2.0W
TP2 = boundary + 1.0W
TP3 = boundary + 2.0W
TP4 = boundary + 4.0W     ← Primary target (1.8R from mid)
TP5 = boundary + 8.0W
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- MetaTrader 5 terminal (Windows or VPS)
- Vantage Markets ECN account (or any MT5 broker with XAUUSD)

### Installation

```bash
git clone https://github.com/rimba14/rimba-gold.git
cd rimba-gold
cp .env.example .env
# Edit .env with your MT5 credentials
```

### Run (Windows)
```powershell
# Dry run first — always
.\START_GOLD.ps1 -DryRun

# Live with dashboard
.\START_GOLD.ps1 -Timeframe M5 -Dashboard

# Backtest before going live
.\START_GOLD.ps1 -Backtest -BacktestBars 5000
```

### Run (Linux/VPS)
```bash
chmod +x start_gold.sh

# Dry run
./start_gold.sh --dry-run

# Live M5 with dashboard
./start_gold.sh --tf M5 --dashboard

# Backtest
./start_gold.sh --backtest --bars 5000
```

### Dashboard
Open `http://localhost:8001` after starting with `--dashboard` / `-Dashboard`.

Shows: active session, live zones, position + TP ladder, equity curve, drawdown guard status.

---

## Architecture

```
rimba-gold/
├── gold_main.py              ← Master orchestration loop
├── gold_constitution.py      ← 9 constitutional laws (non-bypassable)
├── config.py                 ← All tunable parameters
│
├── core/
│   ├── session_clock.py      ← London/NY/Asia session detection
│   ├── atr_sampler.py        ← D1 ATR (TTL-cached sizing anchor)
│   └── gold_feeder.py        ← MT5 connection + OHLCV data
│
├── zone/
│   ├── zone_detector.py      ← Pivot → cluster → zone detection (the edge)
│   ├── tp_calculator.py      ← XNINE geometric TP/SL formula
│   ├── flip_detector.py      ← Opposite-zone close+reverse logic
│   └── zone_registry.py      ← Persistent zone store with TTL
│
├── signal/
│   ├── conviction_scorer.py  ← Zone quality: 0.0–1.0 (5 components)
│   ├── preflight_gate.py     ← 8-gate pre-flight check
│   └── news_gate.py          ← High-impact event blackout
│
├── state/
│   └── position_state.py     ← Single-position runtime state (JSON-persisted)
│
├── risk/
│   ├── lot_sizer.py          ← Fractional Kelly sizing (1% max risk)
│   └── drawdown_guard.py     ← 3-tier DD response: scale/pause/halt
│
├── execution/
│   ├── order_manager.py      ← MT5 order placement + SL modification
│   ├── tp_manager.py         ← TP ladder partial close manager
│   └── flip_executor.py      ← Atomic close+reverse sequence
│
├── monitor/
│   ├── gold_logger.py        ← Structured JSONL trade journal
│   ├── performance_tracker.py← Session/all-time metrics
│   ├── dashboard_server.py   ← FastAPI server (port 8001)
│   └── gold_dashboard.html   ← Live HTML dashboard
│
├── backtest/
│   ├── gold_backtester.py    ← Walk-forward backtester
│   └── backtest_runner.py    ← CLI: compare M1/M5/M15
│
└── tests/
    ├── test_tp_calculator.py ← XNINE formula verified vs PDF signals
    ├── test_constitution.py  ← All 9 laws validated
    └── test_core_modules.py  ← Sizing, zones, session, conviction, DD
```

---

## Constitutional Laws (Non-Bypassable)

| Law | Rule |
|-----|------|
| 1 | Symbol must be XAUUSD only |
| 2 | Maximum 1 open position at any time |
| 3 | Risk per trade ≤ 1% of equity |
| 4 | TP4 R:R ≥ 1.5 (TP4 is the primary target) |
| 5 | Lot size within [0.01, 0.50] |
| 6 | No entry during high-impact news events |
| 7 | SL must be on the correct side of the zone |
| 8 | TP prices must be strictly ordered from entry |
| 9 | Margin usage must leave ≥ 30% of balance free |

Any violation raises `ConstitutionViolation` and kills the trade immediately.

---

## Timeframe Comparison

Backtested on synthetic XAUUSD-like data (3000 bars). Re-run with real MT5 data before going live.

| TF | Zone W (avg) | TP1 pts | SL pts | Trades/wk | Best for |
|----|-------------|---------|--------|-----------|----------|
| M1 | ~8–10 pts | ~400 | ~1600 | 15–20 | High frequency, tight spread required |
| **M5** | **~18–22 pts** | **~980** | **~4000** | **4–6** | **Small account sweet spot** |
| M15 | ~33–40 pts | ~1750 | ~7200 | 1–3 | Wider stops, longer holds |

**Recommendation: Start on M5.** It absorbs spread costs, generates enough trades to be statistically meaningful, and the TP4 target is reachable in one session.

---

## Key Parameters (`config.py`)

```python
PRIMARY_TF          = "M5"     # Active timeframe
MAX_RISK_PCT        = 0.01     # 1% per trade
KELLY_FRACTION      = 0.25     # Fractional Kelly multiplier
MIN_CONVICTION      = 0.62     # Zone quality gate
MAX_POSITIONS       = 1        # Constitutional maximum
BE_AFTER_TP         = 2        # Move SL to breakeven after TP2
FLIP_MIN_CONVICTION = 0.55     # Opposing zone needed for flip
DASHBOARD_PORT      = 8001     # Separate from CADES (8000)
```

---

## Drawdown Guard

Three-tier automatic protection:

| Drawdown | Response |
|----------|----------|
| > 5% | Lot size scaled to 50% |
| > 10% | Lot size scaled to 25%, warning logged |
| > 15% | **HALT** — no new entries until recovery to 8% |

Plus a daily loss limit: if today's realised loss exceeds 3% of balance, no new entries for the rest of the session.

---

## Separation from CADES

| | CADES | RIMBA GOLD |
|-|-------|------------|
| Repo | rimba-trading | rimba-gold |
| Magic number | (CADES default) | **202601** |
| Dashboard port | 8000 | **8001** |
| State file | cades_state.json | gold_position_state.json |
| Strategy | Multi-asset swing | XAUUSD zone only |
| Timeframes | D1/H4/H1 swing | M1/M5/M15 intraday |

These systems never share a position, database, or config file.

---

## Running the Tests

```bash
pip install pytest
python -m pytest tests/ -v
# Expected: 82 passed
```

The test suite validates the XNINE formula against real signal data from the PDF (May–June 2026), all 9 constitutional laws, lot sizing math, session detection, and drawdown guard tiers.

---

## Licence

Private — Marimba / rimba14. Not for redistribution.
