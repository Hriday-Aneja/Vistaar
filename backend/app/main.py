
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import tuning
from app.api import (
    alerts,
    auth,
    distributors,
    health,
    impact,
    khata,
    orders,
    prices,
    pulse,
    shops,
    stock,
    stream,
    swaps,
    udhaar,
)
from app.config import get_settings
from app.db import models  # noqa: F401
from app.db.session import Base, engine
from app.startup_checks import parse_origins, secret_problems

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    problems = secret_problems(settings.env, tuning.PHONE_SECRET)
    if problems:
        raise RuntimeError(
            "Refusing to start with ENV="
            + settings.env
            + ": "
            + "; ".join(problems)
        )

    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    health,
    auth,
    shops,
    stock,
    orders,
    swaps,
    udhaar,
    khata,
    pulse,
    prices,
    impact,
    distributors,
    stream,
    alerts,
):
    app.include_router(module.router)

