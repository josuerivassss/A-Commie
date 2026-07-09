from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "2.1.0"

    # Authentication for server-to-server callers (bot, scripts, etc.).
    # User-facing dashboard requests use Discord OAuth + JWT instead -- see
    # core/access.py, core/discord_oauth.py, core/jwt_auth.py.
    API_KEY: str = ""

    # MongoDB Atlas -- same cluster/collections as the bot (guilds, tags, starboard_config).
    MONGO_URI: str
    MONGO_DB: str = "kitdb"

    # PostgreSQL (Neon) -- same instance/tables as the bot (reminders, giveaways, user_timezones, audit_log).
    POSTGRES_DSN: str
    POSTGRES_POOL_MIN: int = 0
    POSTGRES_POOL_MAX: int = 3

    # Discord OAuth2 login (dashboard). Create/edit at
    # https://discord.com/developers/applications -> your app -> OAuth2.
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_BOT_TOKEN: str = ""

    # This API's own public URL. {API_BASE_URL}/json/auth/callback must be
    # registered exactly in the Discord Developer Portal's OAuth2 Redirects.
    API_BASE_URL: str = "http://localhost:8000"

    # Where the browser is sent after a successful login (the React app).
    FRONTEND_URL: str = "http://localhost:5173"

    # Comma-separated list of origins allowed to call this API from a
    # browser (your frontend's dev + production URLs). Never use "*" together
    # with cookies/credentials; this API uses Bearer tokens, so it doesn't
    # need credentialed CORS at all, but origins should still be locked down.
    CORS_ORIGINS: str = "http://localhost:5173"

    JWT_SECRET: str = "change-me"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7  # 7 days, matches Discord's own token lifetime ballpark

    class Config:
        env_file = ".env"


settings = Settings()