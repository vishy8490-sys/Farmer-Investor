"""
Core business-logic helpers, kept separate from route handlers so they can be
unit-tested independently and later swapped for real ML models.

NOTE: `estimate_risk_score` and `predict_yield_adjustment` are placeholder
heuristics that stand in for the AI features described in the product spec
(crop disease detection, yield prediction, risk scoring). Replace these with
real trained models (e.g. a CV model served separately, or a regression /
gradient-boosted model on historical yield data) without changing the calling
code's interface.
"""
from app.config import settings
from app.models import CropProject, Investment, RiskLevel


def estimate_risk_score(project: CropProject) -> tuple[float, RiskLevel]:
    """
    Very simple heuristic risk scorer (0-100, lower = safer).
    Real system: combine soil health data, weather forecast volatility,
    farmer's past repayment history, and crop-specific failure rates.
    """
    score = 40.0  # baseline

    # Larger requested investment relative to land size implies higher risk.
    if project.land_size_acres > 0:
        investment_density = project.required_investment / project.land_size_acres
        if investment_density > 100000:
            score += 20
        elif investment_density > 50000:
            score += 10

    # High-value / high-maintenance crops are inherently riskier than staples.
    volatile_crops = {"cotton", "chilli", "tomato", "grapes", "banana"}
    if project.crop_type.strip().lower() in volatile_crops:
        score += 15

    score = max(0.0, min(100.0, score))

    if score < 35:
        level = RiskLevel.LOW
    elif score < 65:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.HIGH

    return score, level


def calculate_roi(project: CropProject, investment_amount: float) -> dict:
    """
    Projects investor profit assuming expected yield and price hold.
    Real formula for profit split:
        gross_revenue = expected_yield_kg * estimated_price_per_kg
        net_profit    = gross_revenue - required_investment  (cost recovered first)
        investor_share = net_profit * (investor_percent / 100) * (investment_amount / required_investment)
    """
    if not project.expected_yield_kg or not project.estimated_price_per_kg:
        return {
            "projected_revenue": 0.0,
            "projected_investor_profit": 0.0,
            "projected_roi_percent": 0.0,
        }

    gross_revenue = project.expected_yield_kg * project.estimated_price_per_kg
    net_profit = max(0.0, gross_revenue - project.required_investment)

    investor_percent = 100 - project.profit_share_farmer_percent
    ownership_fraction = (
        investment_amount / project.required_investment if project.required_investment else 0
    )
    investor_profit = net_profit * (investor_percent / 100) * ownership_fraction

    roi_percent = (investor_profit / investment_amount * 100) if investment_amount else 0.0

    return {
        "projected_revenue": round(gross_revenue, 2),
        "projected_investor_profit": round(investor_profit, 2),
        "projected_roi_percent": round(roi_percent, 2),
    }


def settle_harvest(project: CropProject, investments: list[Investment], sale_amount: float) -> None:
    """
    Distributes actual harvest proceeds across all active investments in a
    project, proportional to each investor's share of total funding, then
    applies the platform commission and the agreed profit-share ratio.

    Mutates `investment.payout_amount` / `.status` for each investment.
    Does not commit — caller is responsible for the DB transaction.
    """
    total_invested = sum(inv.amount for inv in investments)
    if total_invested <= 0:
        return

    net_profit = max(0.0, sale_amount - project.required_investment)
    investor_pool_percent = 100 - project.profit_share_farmer_percent

    for inv in investments:
        ownership_fraction = inv.amount / total_invested
        gross_investor_profit = net_profit * (investor_pool_percent / 100) * ownership_fraction

        commission = gross_investor_profit * (settings.PLATFORM_COMMISSION_PERCENT / 100)
        net_investor_profit = gross_investor_profit - commission

        # Investor gets back their principal + net profit share.
        inv.payout_amount = round(inv.amount + net_investor_profit, 2)
        inv.status = inv.status.SETTLED
