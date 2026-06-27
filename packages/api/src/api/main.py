from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import investors, deals, companies, health, chat

app = FastAPI(
    title="EquiTie API",
    version="0.1.0",
    description="EquiTie investor platform API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(investors.router, prefix="/investors", tags=["investors"])
app.include_router(deals.router, prefix="/deals", tags=["deals"])
app.include_router(companies.router, prefix="/portfolio-companies", tags=["companies"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
