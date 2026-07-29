from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    VERSION: str = "2.1.0"
    API_KEY: str = ""
    MONGO_URI: str
    MONGO_DB: str = "kitdb"
    POSTGRES_DSN: str
    POSTGRES_POOL_MIN: int = 0
    POSTGRES_POOL_MAX: int = 3
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_BOT_TOKEN: str = ""
    API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"
    ENVIRONMENT: str = "production"  # "development" | "production"

    # No default: forces the process to fail at startup if unset, instead
    # of silently running with a publicly known secret.
    JWT_SECRET: str
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7
    EMBED_SEND_COOLDOWN_SECONDS: int = 5

    class Config:
        env_file = ".env"


settings = Settings()