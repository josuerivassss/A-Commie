import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from middleware.cors import setup_cors
from routers.loader import load_routes
from core.exceptions import setup_exception_handlers
from core.security import require_api_key
from core.manager import mongo, postgres
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("acommie")

MIN_JWT_SECRET_LENGTH = 32

if len(settings.JWT_SECRET) < MIN_JWT_SECRET_LENGTH:
    raise RuntimeError(
        f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long. "
        "Generate one with: openssl rand -hex 32"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await postgres.connect()
    await load_routes(app)
    logger.info("A Commie API ready")
    yield
    await mongo.close()
    await postgres.close()

is_dev = settings.ENVIRONMENT == "development"

app = FastAPI(
    title="A Commie",
    version=settings.VERSION,
    description="A Commie API",
    lifespan=lifespan,
    docs_url="/docs" if is_dev else None,
    redoc_url="/redoc" if is_dev else None,
    openapi_url="/openapi.json" if is_dev else None,
)

setup_cors(app)
setup_exception_handlers(app)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.get("/", tags=["Health"])
async def root():
    return {"message": "A Commie API is running 🚀"}

@app.get("/health", tags=["Health"], dependencies=[Depends(require_api_key)])
async def health():
    mongo_ok, postgres_ok = False, False
    try:
        if mongo.client:
            await mongo.client.admin.command("ping")
            mongo_ok = True
    except Exception:
        pass
    try:
        postgres_ok = await postgres.ping()
    except Exception:
        pass

    status = "ok" if (mongo_ok and postgres_ok) else "degraded"
    return {"status": status, "version": settings.VERSION, "mongo": mongo_ok, "postgres": postgres_ok}