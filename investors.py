from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, InvestorProfile, CropProject, ProjectStatus, Investment
from app.schemas import (
    InvestorProfileCreate, InvestorProfileOut,
    CropProjectOut, ROIEstimateOut,
    InvestmentOut,
)
from app.auth import require_role
from app.services import calculate_roi

router = APIRouter(prefix="/investors", tags=["Investors"])


def _get_own_investor_profile(user: User, db: Session) -> InvestorProfile:
    profile = db.query(InvestorProfile).filter(InvestorProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Investor profile not found. Create one first.")
    return profile


@router.post("/profile", response_model=InvestorProfileOut)
def create_or_update_profile(
    payload: InvestorProfileCreate,
    user: User = Depends(require_role(UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    profile = db.query(InvestorProfile).filter(InvestorProfile.user_id == user.id).first()
    if profile:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
    else:
        profile = InvestorProfile(user_id=user.id, **payload.model_dump())
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/opportunities", response_model=list[CropProjectOut])
def browse_opportunities(
    crop_type: str | None = None,
    max_risk_score: float | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.INVESTOR)),
):
    """Browse open, fundable crop projects. Supports simple filtering."""
    query = db.query(CropProject).filter(CropProject.status == ProjectStatus.OPEN)
    if crop_type:
        query = query.filter(CropProject.crop_type.ilike(f"%{crop_type}%"))
    if max_risk_score is not None:
        query = query.filter(CropProject.risk_score <= max_risk_score)
    return query.all()


@router.get("/opportunities/{project_id}/roi", response_model=ROIEstimateOut)
def estimate_roi(
    project_id: str,
    amount: float,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.INVESTOR)),
):
    project = db.query(CropProject).filter(CropProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = calculate_roi(project, amount)
    return ROIEstimateOut(
        project_id=project.id,
        risk_level=project.risk_level,
        risk_score=project.risk_score,
        **result,
    )


@router.get("/portfolio", response_model=list[InvestmentOut])
def my_portfolio(
    user: User = Depends(require_role(UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    profile = _get_own_investor_profile(user, db)
    return db.query(Investment).filter(Investment.investor_id == profile.id).all()
