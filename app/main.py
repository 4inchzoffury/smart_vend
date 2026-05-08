from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import financial, inventory, leads, locations, research, root, sales, sync


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(root.router)
app.include_router(research.router)
app.include_router(financial.router)
app.include_router(locations.router)
app.include_router(sales.router)
app.include_router(inventory.router)
app.include_router(sync.router)
app.include_router(leads.router)
