from fastapi import FastAPI
from app.core.database import engine, Base

# Import all models so Base.metadata knows about all tables
from app.models import brand
from app.models import category
from app.models import supplier
from app.models import store
from app.models import customer
from app.models import date
from app.models import festival
from app.models import product
from app.models import inventory
from app.models import transaction
from app.models import external_factors

# Import routes
from app.routes.analytics_routes import router as analytics_router
from app.routes.forecast_routes  import router as forecast_router
from app.routes.decision_routes  import router as decision_router
from app.routes.agent_routes     import router as agent_router

app = FastAPI(title="Retail Intelligence System")

# Create all tables on startup (safe — skips existing tables)
Base.metadata.create_all(bind=engine)

# Register routes
app.include_router(analytics_router)
app.include_router(forecast_router)
app.include_router(decision_router)
app.include_router(agent_router)

@app.get("/")
def root():
    return {"message": "Retail Intelligence System Running"}

@app.get("/health")
def health():
    return {"status": "ok"}