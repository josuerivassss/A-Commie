import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from middleware.cors import setup_cors
from routers.loader import load_routes
from core.exceptions import setup_exception_handlers
from core.manager import mongo, postgres
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("acommie")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await postgres.connect()
    await load_routes(app)
    logger.info("A Commie API ready")
    yield
    await mongo.close()
    await postgres.close()

app = FastAPI(
    title="A Commie",
    version=settings.VERSION,
    description="A Commie API",
    lifespan=lifespan
)

setup_cors(app)
setup_exception_handlers(app)

@app.get("/", tags=["Health"])
async def root():
    return {"message": "A Commie API is running 🚀"}

@app.get("/health", tags=["Health"])
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
