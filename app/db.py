import asyncpg
import logging
from httpx import AsyncClient
from .config import settings


class SupabaseClient:
    def __init__(self):
        self.base_url = str(settings.supabase_url).rstrip("/")
        self.api_key = settings.supabase_service_key
        self.postgres_url = settings.supabase_db_url
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._rest_client = AsyncClient(base_url=f"{self.base_url}/rest/v1", headers=self.headers, timeout=30.0)
        self._pool: asyncpg.Pool | None = None

    async def init_pool(self):
        if self.postgres_url:
            logging.info("Initializing PostgreSQL connection pool.")
            self._pool = await asyncpg.create_pool(self.postgres_url, max_size=6)

    async def insert_rows(self, table: str, rows: list[dict]):
        if not rows:
            return []

        if self._pool:
            return await self._insert_postgres(table, rows)

        return await self._insert_rest(table, rows)

    async def _insert_postgres(self, table: str, rows: list[dict]):
        if self._pool is None:
            raise RuntimeError("PostgreSQL pool is not initialized")

        columns = list(rows[0].keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        column_list = ", ".join(columns)
        sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(sql, [tuple(row[col] for col in columns) for row in rows])
        return rows

    async def _insert_rest(self, table: str, rows: list[dict]):
        response = await self._rest_client.post(f"/{table}", json=rows, params={"return": "minimal"})
        response.raise_for_status()
        return []

    async def close(self):
        if self._pool:
            await self._pool.close()
        await self._rest_client.aclose()
