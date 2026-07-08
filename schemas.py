from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models import UserRole, KYCStatus, ProjectStatus, InvestmentStatus, RiskLevel


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    full_name: str
    phone_number: str = Field(..., description="10-digit Indian mobile number")
    email: Optional[str] = None
    password: str
    role: UserRole
    preferred_language: str = "en"


class OTPRequest(BaseModel):
    phone_number: str


class OTPVerify(BaseModel):
    phone_number: str
    otp_code: str


class LoginRequest(BaseModel):
    phone_number: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    phone_number: str
    role: UserRole
    kyc_status: KYCStatus
    preferred_language: str


# ---------------------------------------------------------------------------
# Farmer / Investor profiles
# ---------------------------------------------------------------------------

class FarmerProfileCreate(BaseModel):
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    land_size_acres: Optional[float] = None
    land_document_ref: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class FarmerProfileOut(FarmerProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class InvestorProfileCreate(BaseModel):
    organization_name: Optional[str] = None
    risk_appetite: RiskLevel = RiskLevel.MEDIUM


class InvestorProfileOut(InvestorProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


# ---------------------------------------------------------------------------
# Crop project
# ---------------------------------------------------------------------------

class CropProjectCreate(BaseModel):
    crop_type: str
    land_size_acres: float
    required_investment: float = Field(..., gt=0)
    expected_yield_kg: Optional[float] = None
    estimated_price_per_kg: Optional[float] = None
    profit_share_farmer_percent: float = Field(..., ge=0, le=100)
    sowing_date: Optional[datetime] = None
    estimated_harvest_date: Optional[datetime] = None


class CropProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    farmer_id: str
    crop_type: str
    land_size_acres: float
    required_investment: float
    amount_raised: float
    expected_yield_kg: Optional[float]
    estimated_price_per_kg: Optional[float]
    profit_share_farmer_percent: float
    status: ProjectStatus
    risk_level: RiskLevel
    risk_score: float
    funding_percent: float
    estimated_harvest_date: Optional[datetime]
    created_at: datetime


class ProgressUpdateCreate(BaseModel):
    note: Optional[str] = None
    photo_url: Optional[str] = None
    stage: Optional[str] = None


class ProgressUpdateOut(ProgressUpdateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Investment / agreement
# ---------------------------------------------------------------------------

class InvestmentCreate(BaseModel):
    project_id: str
    amount: float = Field(..., gt=0)


class InvestmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    investor_id: str
    amount: float
    profit_share_investor_percent: float
    status: InvestmentStatus
    farmer_signed: bool
    investor_signed: bool
    agreement_reference: str
    payout_amount: Optional[float]
    created_at: datetime
    settled_at: Optional[datetime]


class SignAgreementRequest(BaseModel):
    investment_id: str


class PaymentConfirmRequest(BaseModel):
    investment_id: str
    payment_reference: str


class HarvestSettlementRequest(BaseModel):
    project_id: str
    actual_yield_kg: float
    sale_amount: float = Field(..., gt=0, description="Total amount produce sold for")


# ---------------------------------------------------------------------------
# ROI / risk
# ---------------------------------------------------------------------------

class ROIEstimateOut(BaseModel):
    project_id: str
    projected_revenue: float
    projected_investor_profit: float
    projected_roi_percent: float
    risk_level: RiskLevel
    risk_score: float


class DisputeCreate(BaseModel):
    project_id: str
    reason: str


class DisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    raised_by_user_id: str
    reason: str
    resolved: bool
    resolution_note: Optional[str]
    created_at: datetime
