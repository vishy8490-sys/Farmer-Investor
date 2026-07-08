from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, InvestorProfile, FarmerProfile, CropProject, ProjectStatus,
    Investment, InvestmentStatus,
)
from app.schemas import (
    InvestmentCreate, InvestmentOut, SignAgreementRequest,
    PaymentConfirmRequest, HarvestSettlementRequest,
)
from app.auth import require_role
from app.services import settle_harvest

router = APIRouter(prefix="/investments", tags=["Investments"])


@router.post("", response_model=InvestmentOut, status_code=201)
def create_investment(
    payload: InvestmentCreate,
    user: User = Depends(require_role(UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    """Step 1: Investor commits to fund part or all of a project.
    Creates the investment record in PENDING_PAYMENT with the profit-share
    ratio locked in from the project at this moment."""
    investor = db.query(InvestorProfile).filter(InvestorProfile.user_id == user.id).first()
    if not investor:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    project = db.query(CropProject).filter(CropProject.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != ProjectStatus.OPEN:
        raise HTTPException(status_code=400, detail="Project is not open for investment")

    remaining = project.required_investment - project.amount_raised
    if payload.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds remaining funding need of {remaining:.2f}",
        )

    investment = Investment(
        project_id=project.id,
        investor_id=investor.id,
        amount=payload.amount,
        profit_share_investor_percent=100 - project.profit_share_farmer_percent,
    )
    db.add(investment)
    db.commit()
    db.refresh(investment)
    return investment


@router.post("/sign", response_model=InvestmentOut)
def sign_agreement(
    payload: SignAgreementRequest,
    user: User = Depends(require_role(UserRole.FARMER, UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    """Step 2: Both farmer and investor digitally sign the smart agreement.
    Each party calls this endpoint independently; once both have signed the
    investment becomes eligible for payment."""
    investment = db.query(Investment).filter(Investment.id == payload.investment_id).first()
    if not investment:
        raise HTTPException(status_code=404, detail="Investment not found")

    project = db.query(CropProject).filter(CropProject.id == investment.project_id).first()

    if user.role == UserRole.FARMER:
        farmer_profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == user.id).first()
        if not farmer_profile or farmer_profile.id != project.farmer_id:
            raise HTTPException(status_code=403, detail="Not the farmer for this project")
        investment.farmer_signed = True
    else:
        investor_profile = db.query(InvestorProfile).filter(InvestorProfile.user_id == user.id).first()
        if not investor_profile or investor_profile.id != investment.investor_id:
            raise HTTPException(status_code=403, detail="Not the investor for this agreement")
        investment.investor_signed = True

    db.commit()
    db.refresh(investment)
    return investment


@router.post("/confirm-payment", response_model=InvestmentOut)
def confirm_payment(
    payload: PaymentConfirmRequest,
    user: User = Depends(require_role(UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    """Step 3: Investor confirms UPI/bank transfer has been completed.
    In production this should be replaced/validated by a webhook from the
    payment gateway (Razorpay/UPI PSP) rather than trusted client input."""
    investment = db.query(Investment).filter(Investment.id == payload.investment_id).first()
    if not investment:
        raise HTTPException(status_code=404, detail="Investment not found")
    if not investment.is_fully_signed:
        raise HTTPException(status_code=400, detail="Both parties must sign the agreement first")

    investment.payment_reference = payload.payment_reference
    investment.status = InvestmentStatus.ACTIVE

    project = db.query(CropProject).filter(CropProject.id == investment.project_id).first()
    project.amount_raised += investment.amount
    if project.is_fully_funded:
        project.status = ProjectStatus.FUNDED

    db.commit()
    db.refresh(investment)
    return investment


@router.post("/settle-harvest")
def settle_harvest_endpoint(
    payload: HarvestSettlementRequest,
    user: User = Depends(require_role(UserRole.FARMER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Step 4: After produce is sold, distribute proceeds across all active
    investments proportionally, apply platform commission, and mark the
    project as settled."""
    project = db.query(CropProject).filter(CropProject.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != ProjectStatus.FUNDED and project.status != ProjectStatus.HARVESTED:
        raise HTTPException(status_code=400, detail="Project must be funded/harvested before settlement")

    active_investments = db.query(Investment).filter(
        Investment.project_id == project.id,
        Investment.status == InvestmentStatus.ACTIVE,
    ).all()
    if not active_investments:
        raise HTTPException(status_code=400, detail="No active investments to settle")

    project.actual_yield_kg = payload.actual_yield_kg
    project.sale_amount = payload.sale_amount

    settle_harvest(project, active_investments, payload.sale_amount)

    for inv in active_investments:
        inv.settled_at = datetime.utcnow()

    project.status = ProjectStatus.SETTLED
    db.commit()

    return {
        "project_id": project.id,
        "status": project.status,
        "settlements": [
            {"investment_id": inv.id, "payout_amount": inv.payout_amount}
            for inv in active_investments
        ],
    }
