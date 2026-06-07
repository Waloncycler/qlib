import os
import sys

# Force MLFlow to allow file store to fix backend crashes
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from api.routers.market import router as market_router
from api.routers.backtest import router as backtest_router
from api.routers.audit import router as audit_router
from api.routers.tasks import router as tasks_router

app = FastAPI(title="Qlib CN Stock API Gateway")

# Add CORS so Vue dev server can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular Routers
app.include_router(market_router)
app.include_router(backtest_router)
app.include_router(audit_router)
app.include_router(tasks_router)

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 28456
    uvicorn.run("api.server:app", host="0.0.0.0", port=28456, reload=True)
