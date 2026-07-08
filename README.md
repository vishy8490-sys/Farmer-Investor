# AgriFund — Farmer–Investor Crop Funding Platform (Backend)

A production-style **FastAPI** backend for a platform that connects verified
farmers with investors for transparent, profit-shared crop funding — the
Backend counterpart to the Flutter mobile app described in the product spec.

This is the **backend/API layer**. The Flutter app (or any web/admin panel)
is expected to consume this REST API.

---

## 1. Architecture

```
agrifund/
├── requirements.txt
└── app/
    ├── main.py          # FastAPI app entry point, router wiring, CORS
    ├── config.py        # Environment-driven settings (DB URL, JWT secret, commission %)
    ├── database.py       # SQLAlchemy engine/session (SQLite by default, Postgres via env var)
    ├── models.py         # ORM models: User, FarmerProfile, InvestorProfile,
    │                     #   CropProject, Investment, ProgressUpdate, Dispute
    ├── schemas.py        # Pydantic request/response contracts
    ├── auth.py           # Password hashing, JWT issuance, OTP simulation, role guards
    ├── services.py       # Business logic: risk scoring, ROI calculator, harvest settlement
    └── routers/
        ├── auth.py        # /auth/*        registration, OTP, login
        ├── farmers.py      # /farmers/*     profile, crop projects, progress updates
        ├── investors.py    # /investors/*   browse, ROI calculator, portfolio
        ├── investments.py  # /investments/* fund → sign → pay → settle
        └── admin.py        # /admin/*       KYC verification, disputes, analytics
```

### Why this structure
- **Routers** are thin — they only handle HTTP concerns (auth, validation, status codes).
- **`services.py`** holds the actual money-math (risk scoring, ROI, profit
  settlement) so it can be unit-tested without spinning up the API, and so the
  Placeholder heuristics can later be swapped for real ML models without
  Touching route code.
- **Role-based access** (`require_role(...)`) is a single reusable FastAPI
  dependency, not duplicated per-route checks.

---

## 2. The core flow this API implements

1. `POST /auth/register` — farmer, investor, or admin signs up.
2. `POST /auth/otp/request` + `POST /auth/otp/verify` — OTP login flow (or
   `POST /auth/login` with password.
3. `POST /admin/users/{id}/verify` — admin approves farmer/investor KYC.
4. `POST /farmers/profile` — farmer submits land/location details.
5. `POST /farmers/projects` — farmer creates a crop funding request
   (crop type, land size, investment needed, expected yield, harvest date,
   profit-share %). A risk score is computed automatically.
6. `GET /investors/opportunities` — investors browse open, verified projects
   (filterable by crop type / max risk score).
7. `GET /investors/opportunities/{id}/roi` — projected ROI calculator.
8. `POST /investments` — investor commits an amount to a project.
9. `POST /investments/sign` — **both** farmer and investor digitally sign the
   agreement (each calls this once).
10. `POST /investments/confirm-payment` — investor confirms UPI/bank
    transfer; project funding total updates automatically.
11. `POST /farmers/projects/{id}/progress` — farmer posts progress
    updates/photos through the growing season.
12. `POST /investments/settle-harvest` — after the produce is sold, proceeds
    are split across all investors proportional to their stake, platform
    commission is deducted, and payouts are computed automatically.
13. `GET /admin/analytics` — totals raised, active/settled investments,
    project status breakdown.
14. `POST /admin/disputes` + `POST /admin/disputes/{id}/resolve` — dispute
    handling.

---

## 3. Running it locally

```bash
# from the agrifund/ directory
pip install -r requirements.txt

uvicorn app. main: app --reload
```

Then open **http://127.0.0.1:8000/docs** for interactive Swagger docs
(auto-generated from the code — every endpoint above is listed there with
request/response schemas you can try directly in the browser.

By default, it uses a local SQLite file (`agrifund.db`) so there's zero setup.
To use PostgreSQL (recommended for production, per the spec's tech stack):

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@host:5432/agrifund"
```

---

## 4. Mapping to the original feature list

| Spec feature | Where it lives |
|---|---|
| Farmer profile verification | `admin.py::verify_user`, `User.kyc_status` |
| Crop funding requests | `farmers.py::create_crop_project` |
| Crop progress updates | `farmers.py::add_progress_update` |
| Browse investment opportunities | `investors.py::browse_opportunities` |
| Risk assessment | `services.py::estimate_risk_score` |
| Expected ROI calculator | `services.py::calculate_roi`, `investors.py::estimate_roi` |
| Portfolio management / investment history | `investors.py::my_portfolio` |
| Digital/smart agreement | `Investment.farmer_signed/investor_signed`, `investments.py::sign_agreement` |
| Secure payment | `investments.py::confirm_payment` (stubbed for a real payment gateway webhook) |
| Automatic profit settlement | `services.py::settle_harvest` |
| Admin: verify farmers/investors | `admin.py::verify_user` |
| Admin: manage disputes | `admin.py` dispute endpoints |
| Admin: analytics dashboard | `admin.py::analytics_dashboard` |
| Revenue model (1–3% commission) | `config.py::PLATFORM_COMMISSION_PERCENT`, applied in `settle_harvest` |
| Multilingual support | `User.preferred_language` field (drives client-side localization) |

Features that are inherently **client-side or third-party-integration**
concerns rather than backend logic — the Flutter UI itself, push
notifications, Google Maps rendering, the voice assistant, offline mode, and
actual SMS/payment gateway integration — are stubbed with clear extension
points (`generate_otp`, `confirm_payment`) rather than faked, so you can wire
in real providers (MSG91/Twilio for SMS, Razorpay/UPI PSP for payments)
without restructuring the app.

---

## 5. Design notes/production hardening checklist

- **Migrations**: replace `Base.metadata.create_all()` in `main.py` with
  **Alembic** migrations before going to production.
- **OTP store**: currently in-memory (`app/auth.py`); replace with Redis + TTL.
- **Payment confirmation**: currently trusts the investor's client call;
  Replace with a signed webhook from the payment gateway.
- **Aadhaar/eKYC**: only a tokenized reference (`aadhaar_ref`) is stored —
  Never raw Aadhaar numbers — and real integration must go through a
  licensed eKYC provider (UIDAI-authorized), not raw Aadhaar API calls.
- **Fraud monitoring**: the admin analytics endpoint is a starting point;
  A real fraud-monitoring feature would need anomaly detection over
  investment/withdrawal patterns.
- **AI features** (crop disease detection, yield prediction, weather-based
  recommendations): `services.py` has clearly marked placeholder heuristics
  where real trained models should be plugged in.
