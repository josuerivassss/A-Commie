"""Database managers shared by every /json router.

Same collections/tables as the B-Commie bot (MongoDB Atlas: `guilds`,
`tags`; PostgreSQL/Neon: `reminders`, `user_timezones`,
`audit_log`) -- this API is a read/write companion to the bot's data, not a
separate schema. Table/collection names and document shapes must stay in
sync with the bot's `src/bcommie/cogs/*.py`.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger("acommie.db")

TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
COLUMN_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Same whitelist as the bot's PostgresDatabaseManager -- this API must never
# be able to touch a table the bot itself doesn't recognize.
ALLOWED_TABLES: set[str] = {"reminders", "giveaways", "user_timezones", "audit_log"}


class MongoManager:
    """Read/write access to the bot's MongoDB collections (`guilds`, `tags`)."""

    def __init__(self, uri: str, db_name: str) -> None:
        self.uri = uri
        self.db_name = db_name
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        if self.client is None:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            await self.client.admin.command("ping")
            logger.info("mongo connected (db=%s)", self.db_name)

    async def close(self) -> None:
        if self.client:
            self.client.close()
            self.client, self.db = None, None
            logger.info("mongo closed")

    def _require_db(self) -> AsyncIOMotorDatabase:
        if self.db is None:
            raise RuntimeError("MongoManager.connect() must be called first")
        return self.db

    async def get(self, *, table: str, id: int | str, path: str | None = None) -> Any:
        db = self._require_db()
        doc = await db[table].find_one({"_id": id})
        if not doc:
            return None
        if not path:
            return doc
        value: Any = doc
        for key in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(key)
            if value is None:
                return None
        return value

    async def set(
        self, *, table: str, id: int | str, data: dict[str, Any] | None = None,
        path: str | None = None, value: Any = None, upsert: bool = True,
    ) -> bool:
        db = self._require_db()
        update_data = data if data is not None else {path: value}
        result = await db[table].update_one({"_id": id}, {"$set": update_data}, upsert=upsert)
        return result.acknowledged

    async def delete_field(self, *, table: str, id: int | str, path: str) -> bool:
        db = self._require_db()
        result = await db[table].update_one({"_id": id}, {"$unset": {path: ""}})
        return result.modified_count > 0


class PostgresManager:
    """Read/write access to the bot's PostgreSQL tables (reminders, audit_log, ...)."""

    def __init__(self, dsn: str, *, min_size: int = 0, max_size: int = 3) -> None:
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is None:
            self.pool = await asyncpg.create_pool(self.dsn, min_size=self.min_size, max_size=self.max_size)
            logger.info("postgres connected (pool=%s-%s)", self.min_size, self.max_size)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("postgres closed")

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("PostgresManager.connect() must be called first")
        return self.pool

    def _validate_table(self, table: str) -> str:
        if table not in ALLOWED_TABLES or not TABLE_NAME_PATTERN.match(table):
            raise ValueError(f"Table '{table}' is not allowed")
        return table

    def _validate_column(self, column: str) -> str:
        if not COLUMN_NAME_PATTERN.match(column):
            raise ValueError(f"Invalid column name: {column}")
        return column

    async def find(
        self, *, table: str, where: dict[str, Any], limit: int | None = None, order_by: str | None = None
    ) -> list[dict[str, Any]]:
        pool = self._require_pool()
        table = self._validate_table(table)
        where_keys = [self._validate_column(c) for c in where]
        where_clause = " AND ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(where_keys))
        query = f'SELECT * FROM "{table}"'
        if where_clause:
            query += f" WHERE {where_clause}"
        if order_by:
            col, *direction = order_by.strip().split()
            self._validate_column(col)
            query += f' ORDER BY "{col}"'
            if direction and direction[0].upper() in {"ASC", "DESC"}:
                query += f" {direction[0].upper()}"
        if limit:
            query += f" LIMIT {int(limit)}"
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *where.values())
        return [dict(r) for r in rows]

    async def delete(self, *, table: str, id: int | str) -> bool:
        pool = self._require_pool()
        table = self._validate_table(table)
        async with pool.acquire() as conn:
            result = await conn.execute(f'DELETE FROM "{table}" WHERE id = $1', id)
        return result.endswith("1")

    async def ping(self) -> bool:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1


# Singletons used across every router (constructed lazily; connected in main.py's lifespan).
from config import settings  # noqa: E402 (avoids a circular import at module-load time)

mongo = MongoManager(uri=settings.MONGO_URI, db_name=settings.MONGO_DB)
postgres = PostgresManager(dsn=settings.POSTGRES_DSN, min_size=settings.POSTGRES_POOL_MIN, max_size=settings.POSTGRES_POOL_MAX)
