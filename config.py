from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "2.0.0"

    # Authentication: every /json route (guild config, tags, reminders,
    # audit log) requires header `X-API-Key: <API_KEY>`. Image routes
    # remain public, matching the original design (the bot calls them
    # without credentials from inside a private network / with the URL
    # itself acting as the only "secret").
    API_KEY: str = ""

    # MongoDB Atlas — same cluster/collections as the bot (guilds, tags).
    MONGO_URI: str
    MONGO_DB: str = "kitdb"

    # PostgreSQL (Neon) — same instance/tables as the bot (reminders,
    # giveaways, user_timezones, audit_log).
    POSTGRES_DSN: str
    POSTGRES_POOL_MIN: int = 0
    POSTGRES_POOL_MAX: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
