from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, FarmerProfile, CropProject, ProgressUpdate
from app.schemas import (
    FarmerProfileCreate, FarmerProfileOut,
    CropProjectCreate, CropProjectOut,
    ProgressUpdateCreate, ProgressUpdateOut,
)
from app.auth import require_role
from app.services import estimate_risk_score

router = APIRouter(prefix="/farmers", tags=["Farmers"])


def _get_own_farmer_profile(user: User, db: Session) -> FarmerProfile:
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Farmer profile not found. Create one first.")
    return profile


@router.post("/profile", response_model=FarmerProfileOut)
def create_or_update_profile(
    payload: FarmerProfileCreate,
    user: User = Depends(require_role(UserRole.FARMER)),
    db: Session = Depends(get_db),
):
    profile = db.query(FarmerProfile).filter(FarmerProfile.user_id == user.id).first()
    if profile:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
    else:
        profile = FarmerProfile(user_id=user.id, **payload.model_dump())
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/projects", response_model=CropProjectOut, status_code=201)
def create_crop_project(
    payload: CropProjectCreate,
    user: User = Depends(require_role(UserRole.FARMER)),
    db: Session = Depends(get_db),
):
    profile = _get_own_farmer_profile(user, db)
    if user.kyc_status.value != "verified":
        raise HTTPException(status_code=403, detail="Complete KYC verification before listing a project")

    project = CropProject(farmer_id=profile.id, **payload.model_dump())
    score, level = estimate_risk_score(project)
    project.risk_score = score
    project.risk_level = level

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/mine", response_model=list[CropProjectOut])
def list_my_projects(
    user: User = Depends(require_role(UserRole.FARMER)),
    db: Session = Depends(get_db),
):
    profile = _get_own_farmer_profile(user, db)
    return db.query(CropProject).filter(CropProject.farmer_id == profile.id).all()


@router.post("/projects/{project_id}/progress", response_model=ProgressUpdateOut, status_code=201)
def add_progress_update(
    project_id: str,
    payload: ProgressUpdateCreate,
    user: User = Depends(require_role(UserRole.FARMER)),
    db: Session = Depends(get_db),
):
    profile = _get_own_farmer_profile(user, db)
    project = db.query(CropProject).filter(
        CropProject.id == project_id, CropProject.farmer_id == profile.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update = ProgressUpdate(project_id=project.id, **payload.model_dump())
    db.add(update)
    db.commit()
    db.refresh(update)
    return update
