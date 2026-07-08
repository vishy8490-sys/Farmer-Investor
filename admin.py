from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, KYCStatus, CropProject, ProjectStatus, Investment,
    InvestmentStatus, Dispute,
)
from app.schemas import UserOut, DisputeCreate, DisputeOut
from app.auth import require_role
from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users/pending-kyc", response_model=list[UserOut])
def list_pending_kyc(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    return db.query(User).filter(User.kyc_status == KYCStatus.PENDING).all()


@router.post("/users/{user_id}/verify")
def verify_user(
    user_id: str,
    approve: bool = True,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.kyc_status = KYCStatus.VERIFIED if approve else KYCStatus.REJECTED
    db.commit()
    return {"user_id": user.id, "kyc_status": user.kyc_status}


@router.get("/analytics")
def analytics_dashboard(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    total_projects = db.query(func.count(CropProject.id)).scalar()
    total_raised = db.query(func.coalesce(func.sum(CropProject.amount_raised), 0.0)).scalar()
    active_investments = db.query(func.count(Investment.id)).filter(
        Investment.status == InvestmentStatus.ACTIVE
    ).scalar()
    settled_investments = db.query(Investment).filter(
        Investment.status == InvestmentStatus.SETTLED
    ).all()

    total_settled_payout = sum(inv.payout_amount or 0 for inv in settled_investments)
    total_settled_principal = sum(inv.amount for inv in settled_investments)

    projects_by_status = dict(
        db.query(CropProject.status, func.count(CropProject.id))
        .group_by(CropProject.status)
        .all()
    )

    return {
        "total_projects": total_projects,
        "total_amount_raised": round(total_raised, 2),
        "active_investments": active_investments,
        "settled_investments_count": len(settled_investments),
        "total_settled_principal": round(total_settled_principal, 2),
        "total_settled_payout": round(total_settled_payout, 2),
        "platform_commission_percent": settings.PLATFORM_COMMISSION_PERCENT,
        "projects_by_status": {
            (k.value if hasattr(k, "value") else str(k)): v
            for k, v in projects_by_status.items()
        },
    }


@router.post("/disputes", response_model=DisputeOut, status_code=201)
def raise_dispute(
    payload: DisputeCreate,
    user: User = Depends(require_role(UserRole.FARMER, UserRole.INVESTOR)),
    db: Session = Depends(get_db),
):
    project = db.query(CropProject).filter(CropProject.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    dispute = Dispute(project_id=project.id, raised_by_user_id=user.id, reason=payload.reason)
    project.status = ProjectStatus.DISPUTED
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.get("/disputes", response_model=list[DisputeOut])
def list_disputes(
    resolved: bool | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    query = db.query(Dispute)
    if resolved is not None:
        query = query.filter(Dispute.resolved == resolved)
    return query.all()


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeOut)
def resolve_dispute(
    dispute_id: str,
    resolution_note: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    dispute.resolved = True
    dispute.resolution_note = resolution_note
    db.commit()
    db.refresh(dispute)
    return dispute
