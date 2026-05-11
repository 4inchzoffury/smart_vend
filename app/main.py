from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.database import Base, engine
from app.models import settings as _settings_models  # noqa: F401 — registers AppSetting with Base
from app.routers import financial, inventory, leads, locations, research, root, sales, sync
from app.routers import auth as auth_router
from app.routers import chatbot as chatbot_router
from app.routers import customer_service as cs_router
from app.routers import equipment as equipment_router
from app.routers import public as public_router
from app.services.auth import require_user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Public routes — no auth required
app.include_router(public_router.router)
app.include_router(auth_router.router)
app.include_router(chatbot_router.router)

# Protected internal routes — require Google sign-in
_auth = [Depends(require_user)]
app.include_router(root.router, dependencies=_auth)
app.include_router(equipment_router.router, dependencies=_auth)
app.include_router(research.router, dependencies=_auth)
app.include_router(financial.router, dependencies=_auth)
app.include_router(locations.router, dependencies=_auth)
app.include_router(sales.router, dependencies=_auth)
app.include_router(inventory.router, dependencies=_auth)
app.include_router(sync.router, dependencies=_auth)
app.include_router(leads.router, dependencies=_auth)
app.include_router(cs_router.router, dependencies=_auth)

# SessionMiddleware must be added last so it wraps everything (outermost = first to run)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key, https_only=True)
# Trust X-Forwarded-Proto/For headers from Cloudflare Tunnel
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
