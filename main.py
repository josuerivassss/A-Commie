from contextlib import asynccontextmanager
from fastapi import FastAPI
from middleware.cors import setup_cors
from routers.loader import load_routes
from core.exceptions import setup_exception_handlers
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_routes(app)
    yield

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
    return {"status": "ok", "version": settings.VERSION}