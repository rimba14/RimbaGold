import pytest
from datetime import datetime, timezone
import config as cfg
from gold_constitution import enforce, TradeProposal, ConstitutionViolation

def test_constitution_account_lock():
    # Valid baseline proposal
    prop_valid = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2290.0,
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.01,
        account_equity=10000.0,
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=25653715,
        open_positions=0
    )
    
    # Check that valid proposal passes enforce
    assert enforce(prop_valid) is True

    # Test Law 10: Unauthorized account ID
    prop_invalid_acc = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2290.0,
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.01,
        account_equity=10000.0,
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=99999999,  # Unauthorized account
        open_positions=0
    )
    
    with pytest.raises(ConstitutionViolation) as excinfo:
        enforce(prop_invalid_acc)
    assert "[LAW-10] ILLEGAL ROUTING PACKET" in str(excinfo.value)

def test_constitution_symbol_lock():
    # Test Law 1: Unauthorized symbol lock
    prop_invalid_symbol = TradeProposal(
        symbol="EURUSD",  # Unauthorized symbol
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2290.0,
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.01,
        account_equity=10000.0,
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=25653715,
        open_positions=0
    )
    
    with pytest.raises(ConstitutionViolation) as excinfo:
        enforce(prop_invalid_symbol)
    assert "[LAW-1] SYMBOL LOCK" in str(excinfo.value)

def test_constitution_max_positions():
    # Test Law 2: One position maximum limit
    prop_invalid_pos = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2290.0,
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.01,
        account_equity=10000.0,
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=25653715,
        open_positions=1  # 1 already open, blocks subsequent layering
    )
    
    with pytest.raises(ConstitutionViolation) as excinfo:
        enforce(prop_invalid_pos)
    assert "[LAW-2] MAX_POSITIONS" in str(excinfo.value)

def test_constitution_max_risk():
    # Test Law 3: Maximum 1% risk of equity limit
    prop_high_risk = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2200.0,   # Very large stop distance: 110.0 points
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.50,     # Large lot size: 0.5 lot. Risk = 0.5 * 110.0 * 100 = $5500
        account_equity=10000.0,  # Max risk allowed is 1% of $10000 = $100
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=25653715,
        open_positions=0
    )
    
    with pytest.raises(ConstitutionViolation) as excinfo:
        enforce(prop_high_risk)
    assert "[LAW-3] MAX_RISK" in str(excinfo.value)

def test_constitution_news_blackout():
    # Test Law 6: Event blackout rules
    prop_news_event = TradeProposal(
        symbol="XAUUSD",
        direction="BUY",
        timeframe="M5",
        zone_low=2300.0,
        zone_high=2310.0,
        zone_width=10.0,
        entry_price=2310.0,
        sl_price=2290.0,
        tp_prices=[2315.0, 2320.0, 2330.0, 2350.0, 2390.0],
        lot_size=0.01,
        account_equity=10000.0,
        account_balance=10000.0,
        spread_pts=1.0,
        conviction=0.75,
        session="LONDON",
        timestamp=datetime.now(timezone.utc),
        account_id=25653715,
        news_event="FOMC Rate Decision",  # High-impact news event
        open_positions=0
    )
    
    with pytest.raises(ConstitutionViolation) as excinfo:
        enforce(prop_news_event)
    assert "[LAW-6] NEWS SHIELD" in str(excinfo.value)
