import os
import sys

# Force MLFlow to allow file store to fix backend crashes
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from modules.market.router import router as market_router
from modules.backtest.router import router as backtest_router
from modules.audit.router import router as audit_router
from modules.intelligence.router import router as tasks_router
from modules.user.router import router as user_prefs_router

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
app.include_router(user_prefs_router)

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 28456
    uvicorn.run("main:app", host="0.0.0.0", port=28456, reload=True)
