"""
Tool unit tests covering all 13 documented edge cases.

Each test maps directly to the "Handling Tricky Data Cases" table in system_design.md.
Tests hit the live seeded database — run `make up-d` before executing.

Investor / deal anchors used (from seed data):
  INV022  Henrik Sorensen     — zero holdings
  INV023  Lara Greco          — zero holdings
  INV021  Grace Okafor        — pending allocation (DEAL021)
  INV001  Idris Olawale       — multi-round (Forgecraft), price discount (DEAL001),
                                multi-currency (GBP reporting), overdue fees
  INV007  Banyanwood Trust    — partial contribution (DEAL014 Pulsegrid Health, 50%)
  INV011  Sophie Laurent      — exited deal (Helianthe Energy)
  INV010  Yuki Tanaka         — written-off deal (Yappio)
  INV004  Brightmere Family   — down round (Qubrium Series B)
  INV013  Mei Lin             — partial secondary (Tallybook, 30% realised)
  INV002  Selina Voss         — admin fee in USD on GBP deal (DEAL004)
"""

import pytest

from ai.tools.portfolio_summary import get_portfolio_summary
from ai.tools.position_detail import get_position_detail
from ai.tools.upcoming_obligations import get_upcoming_obligations
from ai.tools.distributions import get_distributions
from ai.tools.fee_detail import get_fee_detail
from ai.tools.valuation_history import get_valuation_history
from ai.tools.account_statement import get_account_statement
from ai.tools.fx_rates import get_fx_rates
from ai.tools.search_company import search_company
from ai.tools.investor_profile import get_investor_profile


# ── EC-01: Zero-holding investors ─────────────────────────────────────────────

@pytest.mark.parametrize("investor_id,name", [
    ("INV022", "Henrik Sorensen"),
    ("INV023", "Lara Greco"),
])
def test_zero_holdings_returns_empty_positions(db, investor_id, name):
    result = get_portfolio_summary(investor_id, db)

    assert "error" not in result
    assert result["positions"] == []
    assert result["portfolio_moic"] is None
    assert result["portfolio_dpi"] is None
    assert result["portfolio_rvpi"] is None
    for key in ("committed", "contributed", "current_value", "net_distributions"):
        assert result["totals"][key]["amount"] == 0.0


# ── EC-02: Pending / unfunded allocation ──────────────────────────────────────

def test_pending_allocation_zero_contributed_and_current_value(db):
    # INV021 (Grace Okafor) has allocation_status = Pending on DEAL021
    result = get_portfolio_summary("INV021", db)

    assert "error" not in result
    pending = [p for p in result["positions"] if p["allocation_status"] == "Pending"]
    assert len(pending) >= 1, "Expected at least one Pending allocation for INV021"

    for pos in pending:
        assert pos["contributed"]["amount"] == 0.0, "Pending: contributed must be 0"
        assert pos["current_value"]["amount"] == 0.0, "Pending: current value must be 0"
        assert pos["moic"] is None, "Pending: MOIC undefined with zero contribution"
        assert pos["committed"]["amount"] > 0.0, "Pending: commitment must be recorded"


# ── EC-03: Multi-round company ────────────────────────────────────────────────

def test_multi_round_forgecraft_returns_three_rounds_and_aggregate(db):
    # INV001 holds Forgecraft Seed, Series A, and Series B
    result = get_position_detail("INV001", db, "Forgecraft")

    assert "error" not in result
    rounds = result["rounds"]
    assert len(rounds) == 3, "Forgecraft has Seed + Series A + Series B"

    round_labels = {r["round"] for r in rounds}
    assert "Seed" in round_labels
    assert "Series A" in round_labels
    assert "Series B" in round_labels

    agg = result["aggregate"]
    assert agg["moic"] is not None

    # Aggregate contributed == sum of per-round reporting_amounts (all converted to GBP)
    # round["contributed"]["amount"] is in deal currency (USD for Forgecraft)
    # round["contributed"]["reporting_amount"] and agg["contributed"]["amount"] are both in GBP
    total_contributed_rc = sum(r["contributed"]["reporting_amount"] for r in rounds)
    assert agg["contributed"]["amount"] == pytest.approx(total_contributed_rc, rel=0.01)


# ── EC-04: Per-investor share-price discount ──────────────────────────────────

def test_position_detail_uses_investor_effective_share_price_not_deal_price(db):
    # INV001 DEAL001 (Forgecraft Seed): deal entry = 2.50, investor effective = 2.25
    result = get_position_detail("INV001", db, "Forgecraft")

    assert "error" not in result
    seed = next((r for r in result["rounds"] if r["round"] == "Seed"), None)
    assert seed is not None

    # Tool must read effective_share_price from allocation (2.25), not deal (2.50)
    assert seed["entry_share_price"] == pytest.approx(2.25, abs=0.01), (
        f"Expected investor entry price 2.25, got {seed['entry_share_price']}. "
        "Tool may be reading deal.entry_share_price instead of alloc.effective_share_price."
    )


# ── EC-05: Multi-currency — amounts converted to reporting currency ────────────

def test_multi_currency_all_amounts_in_reporting_currency(db):
    # INV001 reports in GBP and holds deals in multiple currencies
    result = get_portfolio_summary("INV001", db)

    assert "error" not in result
    assert result["reporting_currency"] == "GBP"
    assert result["totals"]["current_value"]["currency"] == "GBP"

    for pos in result["positions"]:
        for field in ("committed", "contributed", "current_value", "net_distributions"):
            money = pos[field]
            assert money["reporting_currency"] == "GBP", (
                f"Position {pos['deal_id']} field '{field}': "
                f"reporting_currency is '{money['reporting_currency']}', expected GBP"
            )


def test_fx_conversion_rate_applied_correctly_for_usd_to_gbp(db):
    # Verify that USD amounts are converted to GBP using the correct FX rate
    fx_result = get_fx_rates(db)
    rates = {r["currency"]: r["to_usd"] for r in fx_result["rates"]}

    result = get_portfolio_summary("INV001", db)
    for pos in result["positions"]:
        if pos["deal_currency"] == "USD" and pos["current_value"]["amount"] > 0:
            usd_amount = pos["current_value"]["amount"]
            gbp_amount = pos["current_value"]["reporting_amount"]
            # USD → GBP: divide by GBP's to_usd rate
            expected_gbp = usd_amount / rates["GBP"]
            assert gbp_amount == pytest.approx(expected_gbp, rel=0.01), (
                f"FX conversion mismatch for {pos['deal_id']}: "
                f"{usd_amount} USD → expected {expected_gbp:.2f} GBP, got {gbp_amount:.2f} GBP"
            )
            return  # one verified USD→GBP position is sufficient
    pytest.skip("INV001 has no USD-denominated positions with non-zero current value")


# ── EC-06: Partial contribution (contributed_pct < 100) ──────────────────────

def test_partial_contribution_shows_outstanding_commitment(db):
    # INV007 DEAL014 (Pulsegrid Health): 50% contributed
    # commitment = 975,000 | contributed = 487,500 | outstanding = 487,500
    result = get_portfolio_summary("INV007", db)

    assert "error" not in result
    pulsegrid = next((p for p in result["positions"] if p["deal_id"] == "DEAL014"), None)
    assert pulsegrid is not None, "INV007 should have a position in DEAL014 (Pulsegrid Health)"

    committed = pulsegrid["committed"]["amount"]
    contributed = pulsegrid["contributed"]["amount"]
    outstanding = pulsegrid["outstanding_commitment"]["amount"]

    assert contributed < committed, "Partial contribution: contributed must be less than committed"
    assert outstanding > 0.0, "Partial contribution: outstanding commitment must be positive"
    assert contributed + outstanding == pytest.approx(committed, rel=0.01), (
        "contributed + outstanding_commitment must equal committed"
    )
    assert contributed / committed == pytest.approx(0.5, abs=0.05), (
        "DEAL014 is 50% contributed"
    )


# ── EC-07: Exited deal — MOIC from distributions only ────────────────────────

def test_exited_deal_current_value_zero_moic_equals_dpi(db):
    # INV011 (Sophie Laurent) holds Helianthe Energy (Exited)
    result = get_position_detail("INV011", db, "Helianthe")

    assert "error" not in result
    round_ = result["rounds"][0]

    assert round_["deal_status"] == "Exited"
    assert round_["current_value"]["amount"] == 0.0, "Exited: current value must be 0"
    assert round_["rvpi"] == pytest.approx(0.0, abs=0.001), "Exited: RVPI must be 0"
    assert round_["net_distributions"]["amount"] > 0.0, "Exited: must have distributions"
    assert round_["dpi"] > 0.0, "Exited: DPI must be positive"
    # When RVPI = 0, MOIC == DPI
    assert round_["moic"] == pytest.approx(round_["dpi"], abs=0.001), (
        "Exited deal: MOIC must equal DPI (no residual value)"
    )


def test_exited_deal_distributions_accessible(db):
    result = get_distributions("INV011", db, company_name="Helianthe")
    assert "error" not in result
    assert len(result["distributions"]) > 0
    assert result["totals"]["net"]["amount"] > 0.0


# ── EC-08: Written-off deal ───────────────────────────────────────────────────

def test_written_off_deal_zero_value_zero_moic(db):
    # INV010 (Yuki Tanaka) holds Yappio (Written Off, share price 0)
    result = get_position_detail("INV010", db, "Yappio")

    assert "error" not in result
    round_ = result["rounds"][0]

    assert round_["deal_status"] == "Written Off"
    assert round_["current_value"]["amount"] == 0.0, "Written off: current value must be 0"
    assert round_["net_distributions"]["amount"] == 0.0, "Yappio has no distributions"
    assert round_["moic"] == pytest.approx(0.0, abs=0.001), "Written off with no distributions: MOIC = 0"


def test_written_off_valuation_history_shows_zero_multiple(db):
    result = get_valuation_history("INV010", db, "Yappio")
    assert "error" not in result
    assert len(result["rounds"]) > 0
    last_mark = result["rounds"][0]["marks"][-1]
    assert last_mark["multiple_vs_deal_entry"] == pytest.approx(0.0, abs=0.001)


# ── EC-09: Down round ─────────────────────────────────────────────────────────

def test_down_round_latest_price_below_entry(db):
    # INV004 (Brightmere Family Office) holds Qubrium Series B
    # Entry: 10.00 | Latest: 6.20 | Multiple: 0.62
    result = get_position_detail("INV004", db, "Qubrium")

    assert "error" not in result
    series_b = next((r for r in result["rounds"] if "Series B" in r["round"]), None)
    assert series_b is not None, "INV004 should have a Qubrium Series B position"

    assert series_b["latest_share_price"] < series_b["entry_share_price"], (
        f"Down round: latest {series_b['latest_share_price']} should be < "
        f"entry {series_b['entry_share_price']}"
    )
    assert series_b["moic"] < 1.0, "Down round: MOIC must be below 1.0"
    assert series_b["rvpi"] < 1.0, "Down round: RVPI must be below 1.0"


def test_down_round_valuation_history_contains_sub_one_multiple(db):
    result = get_valuation_history("INV004", db, "Qubrium")
    assert "error" not in result

    series_b = next((r for r in result["rounds"] if "Series B" in r["round"]), None)
    assert series_b is not None
    assert any(m["multiple_vs_deal_entry"] < 1.0 for m in series_b["marks"]), (
        "Valuation history for down round must contain at least one sub-1.0 multiple"
    )


# ── EC-10: Partial secondary ──────────────────────────────────────────────────

def test_partial_secondary_current_value_uses_remaining_fraction(db):
    # INV013 (Mei Lin) holds Tallybook: 30% sold, 70% still live
    result = get_position_detail("INV013", db, "Tallybook")

    assert "error" not in result
    round_ = result["rounds"][0]

    assert round_["realised_fraction"] == pytest.approx(0.3, abs=0.01), (
        "Tallybook: realised_fraction should be 0.30"
    )

    # current_value = units × (1 - 0.3) × latest_share_price
    expected_cv = round_["units"] * (1 - round_["realised_fraction"]) * round_["latest_share_price"]
    assert round_["current_value"]["amount"] == pytest.approx(expected_cv, rel=0.01), (
        "Partial secondary: current value must use (1 - realised_fraction) × units × price"
    )

    assert round_["net_distributions"]["amount"] > 0.0, "30% realised portion must have distributions"
    assert len(round_["distributions"]) > 0


# ── EC-11: Overdue fees ────────────────────────────────────────────────────────

def test_overdue_fees_flagged_and_has_overdue_items_true(db):
    # INV001 (Idris Olawale) has at least one overdue fee
    result = get_upcoming_obligations("INV001", db)

    assert "error" not in result
    assert result["has_overdue_items"] is True, "INV001 must have overdue items"

    overdue_fees = [f for f in result["fees"] if f["overdue"]]
    assert len(overdue_fees) >= 1, "At least one fee must be flagged overdue"
    for f in overdue_fees:
        assert f["status"] == "Overdue"
        assert f["amount"]["amount"] > 0.0


def test_upcoming_obligations_amounts_in_reporting_currency(db):
    result = get_upcoming_obligations("INV001", db)
    assert "error" not in result
    rc = result["reporting_currency"]
    for fee in result["fees"]:
        assert fee["amount"]["reporting_currency"] == rc
    for call in result["capital_calls"]:
        assert call["amount"]["reporting_currency"] == rc


# ── EC-12: Similar company names — disambiguation ─────────────────────────────

def test_search_company_disambiguates_northpeak(db):
    result = search_company(db, "Northpeak")

    assert "error" not in result
    assert len(result["matches"]) == 2, (
        "search_company('Northpeak') must return both Northpeak Analytics and Northpeak Health"
    )
    names = {m["company_name"] for m in result["matches"]}
    assert "Northpeak Analytics" in names
    assert "Northpeak Health" in names


def test_search_company_returns_empty_for_unknown_name(db):
    result = search_company(db, "NonExistentCompanyXYZ999")
    assert "error" not in result
    assert result["matches"] == []


def test_position_detail_returns_disambiguation_dict_for_ambiguous_name(db):
    # Searching "Northpeak" without specifying which one should trigger disambiguation
    result = get_position_detail("INV001", db, "Northpeak")
    assert result.get("disambiguation") is True
    assert len(result["matches"]) == 2


# ── EC-13: Admin fee currency — always USD even on GBP/EUR deals ──────────────

def test_admin_fee_standard_rate_in_usd_on_gbp_deal(db):
    # INV002 (Selina Voss) has DEAL004 (GBP deal) with std_admin_fee_usd = 450
    result = get_fee_detail("INV002", db)

    assert "error" not in result

    gbp_deal = next(
        (d for d in result["deals"] if d["deal_currency"] == "GBP"),
        None,
    )
    assert gbp_deal is not None, "INV002 must have at least one GBP-denominated deal"

    # Standard schedule stores admin fee in USD regardless of deal currency
    assert gbp_deal["standard_rates"]["admin_fee_usd"] > 0, (
        "Admin fee standard rate must be stored in USD even on GBP deals"
    )

    admin_fees = [f for f in gbp_deal["fees"] if f["fee_type"] == "Admin Fee"]
    assert len(admin_fees) > 0, "DEAL004 must have Admin Fee rows"

    # Reported amount must be converted to investor's reporting currency (GBP for INV002)
    rc = result["reporting_currency"]
    for f in admin_fees:
        assert f["amount"]["reporting_currency"] == rc, (
            f"Admin fee reporting_currency must be {rc}, got {f['amount']['reporting_currency']}"
        )


# ── Sanity: error handling ─────────────────────────────────────────────────────

@pytest.mark.parametrize("investor_id", ["INVALID_ID", "INV999"])
def test_unknown_investor_returns_error_dict(db, investor_id):
    """All investor-scoped tools must return {\"error\": ...} for unknown IDs."""
    for fn, kwargs in [
        (get_portfolio_summary, {}),
        (get_upcoming_obligations, {}),
        (get_distributions, {}),
        (get_investor_profile, {}),
        (get_account_statement, {}),
    ]:
        result = fn(investor_id, db, **kwargs)
        assert "error" in result, (
            f"{fn.__name__} did not return an error dict for investor_id='{investor_id}'"
        )


def test_get_fx_rates_returns_four_currencies(db):
    result = get_fx_rates(db)
    assert "error" not in result
    currencies = {r["currency"] for r in result["rates"]}
    assert currencies == {"USD", "GBP", "EUR", "AED"}
    for rate in result["rates"]:
        assert rate["to_usd"] > 0


def test_account_statement_date_filter_respects_range(db):
    full = get_account_statement("INV001", db)
    filtered = get_account_statement("INV001", db, start_date="2024-01-01", end_date="2024-12-31")

    assert "error" not in filtered
    assert filtered["summary"]["line_count"] <= full["summary"]["line_count"]
    assert filtered["filters"]["start_date"] == "2024-01-01"
    assert filtered["filters"]["end_date"] == "2024-12-31"
    for line in filtered["lines"]:
        assert "2024-01-01" <= line["date"] <= "2024-12-31", (
            f"Line date {line['date']} is outside the requested 2024 range"
        )


def test_account_statement_invalid_date_returns_error(db):
    result = get_account_statement("INV001", db, start_date="not-a-date")
    assert "error" in result
