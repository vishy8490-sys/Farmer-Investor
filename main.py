from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, farmers, investors, investments, admin

# Creates tables on startup if they don't exist yet.
# For production, use Alembic migrations instead of create_all().
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AgriFund API",
    description=(
        "Backend for a platform connecting verified farmers with investors "
        "for transparent, profit-shared crop funding."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to the Flutter app's domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(farmers.router)
app.include_router(investors.router)
app.include_router(investments.router)
app.include_router(admin.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "AgriFund API"}
