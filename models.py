import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    FARMER = "farmer"
    INVESTOR = "investor"
    ADMIN = "admin"


class KYCStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ProjectStatus(str, enum.Enum):
    OPEN = "open"                 # accepting investment
    FUNDED = "funded"              # fully funded, growing
    HARVESTED = "harvested"        # harvest complete, pending sale
    SETTLED = "settled"            # profit distributed
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class InvestmentStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    SETTLED = "settled"
    REFUNDED = "refunded"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Core user identity (shared by farmers, investors, admins)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    preferred_language = Column(String, default="en")  # en, ta, hi, te, kn ...

    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.PENDING)
    aadhaar_ref = Column(String, nullable=True)  # store only a tokenized ref, never raw Aadhaar
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    farmer_profile = relationship("FarmerProfile", back_populates="user", uselist=False)
    investor_profile = relationship("InvestorProfile", back_populates="user", uselist=False)


class FarmerProfile(Base):
    __tablename__ = "farmer_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    village = Column(String, nullable=True)
    district = Column(String, nullable=True)
    state = Column(String, nullable=True)
    land_size_acres = Column(Float, nullable=True)
    land_document_ref = Column(String, nullable=True)  # uploaded document reference
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    user = relationship("User", back_populates="farmer_profile")
    projects = relationship("CropProject", back_populates="farmer")


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    organization_name = Column(String, nullable=True)  # null if individual investor
    risk_appetite = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM)

    user = relationship("User", back_populates="investor_profile")
    investments = relationship("Investment", back_populates="investor")


# ---------------------------------------------------------------------------
# Crop funding request / project
# ---------------------------------------------------------------------------

class CropProject(Base):
    __tablename__ = "crop_projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    farmer_id = Column(String, ForeignKey("farmer_profiles.id"), nullable=False)

    crop_type = Column(String, nullable=False)
    land_size_acres = Column(Float, nullable=False)
    required_investment = Column(Float, nullable=False)
    amount_raised = Column(Float, default=0.0)
    expected_yield_kg = Column(Float, nullable=True)
    estimated_price_per_kg = Column(Float, nullable=True)
    profit_share_farmer_percent = Column(Float, nullable=False)  # e.g. 60 means farmer keeps 60%
    sowing_date = Column(DateTime, nullable=True)
    estimated_harvest_date = Column(DateTime, nullable=True)

    status = Column(Enum(ProjectStatus), default=ProjectStatus.OPEN)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.MEDIUM)
    risk_score = Column(Float, default=50.0)  # 0-100, lower is safer

    actual_yield_kg = Column(Float, nullable=True)
    sale_amount = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("FarmerProfile", back_populates="projects")
    investments = relationship("Investment", back_populates="project")
    progress_updates = relationship("ProgressUpdate", back_populates="project")

    @property
    def funding_percent(self) -> float:
        if self.required_investment <= 0:
            return 0.0
        return min(100.0, round(self.amount_raised / self.required_investment * 100, 2))

    @property
    def is_fully_funded(self) -> bool:
        return self.amount_raised >= self.required_investment


class ProgressUpdate(Base):
    __tablename__ = "progress_updates"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("crop_projects.id"), nullable=False)
    note = Column(Text, nullable=True)
    photo_url = Column(String, nullable=True)
    stage = Column(String, nullable=True)  # e.g. "sowing", "irrigation", "flowering", "harvest"
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("CropProject", back_populates="progress_updates")


# ---------------------------------------------------------------------------
# Investment / digital agreement
# ---------------------------------------------------------------------------

class Investment(Base):
    __tablename__ = "investments"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("crop_projects.id"), nullable=False)
    investor_id = Column(String, ForeignKey("investor_profiles.id"), nullable=False)

    amount = Column(Float, nullable=False)
    profit_share_investor_percent = Column(Float, nullable=False)  # mirrors project ratio at time of investing
    status = Column(Enum(InvestmentStatus), default=InvestmentStatus.PENDING_PAYMENT)

    # Digital signatures (simple hash/token based e-signature, not a scanned signature)
    farmer_signed = Column(Boolean, default=False)
    investor_signed = Column(Boolean, default=False)
    agreement_reference = Column(String, default=gen_uuid)

    payment_reference = Column(String, nullable=True)  # UPI/bank txn id
    payout_amount = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)

    project = relationship("CropProject", back_populates="investments")
    investor = relationship("InvestorProfile", back_populates="investments")

    @property
    def is_fully_signed(self) -> bool:
        return self.farmer_signed and self.investor_signed


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("crop_projects.id"), nullable=False)
    raised_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
