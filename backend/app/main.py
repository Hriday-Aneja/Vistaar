from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, khata, orders, prices, pulse, shops, stock, stream, swaps, udhaar
from app.config import get_settings
from app.db import models  # noqa: F401  (registers tables)
from app.db.session import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=f"{settings.app_name} API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, auth, shops, stock, orders, swaps, udhaar, khata, pulse, prices, stream):
    app.include_router(module.router)
