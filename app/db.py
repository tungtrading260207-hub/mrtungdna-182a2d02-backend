import asyncpg
import logging
import os
from httpx import AsyncClient
from .config import settings


class SupabaseClient:
    def __init__(self):
        self.base_url = str(settings.supabase_url).rstrip("/")
        self.api_key = settings.supabase_service_key
        self.postgres_url = settings.supabase_db_url
        self.schema = os.getenv("SUPABASE_SCHEMA") or os.getenv("POSTGREST_SCHEMA") or "public"
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
        }
        self._rest_client = AsyncClient(base_url=f"{self.base_url}/rest/v1", headers=self.headers, timeout=30.0)
        self._functions_client = AsyncClient(base_url=f"{self.base_url}/functions/v1", headers=self.headers, timeout=30.0)
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

    async def fetch_rows(self, table: str, limit: int = 10, order_by: str | None = None):
        if self._pool:
            order_clause = f" ORDER BY {order_by}" if order_by else ""
            sql = f"SELECT * FROM {table}{order_clause} LIMIT $1"
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, limit)
                return [dict(row) for row in rows]

        params = {"select": "*", "limit": limit}
        if order_by:
            params["order"] = order_by

        response = await self._rest_client.get(f"/{table}", params=params)
        response.raise_for_status()
        return response.json()

    async def invoke_function(
        self,
        function_name: str,
        method: str = "POST",
        body: dict | list | None = None,
        query: dict[str, str] | None = None,
    ):
        response = await self._functions_client.request(
            method,
            f"/{function_name}",
            params=query,
            json=body,
        )

        if response.status_code == 204:
            return {"status": "no_content"}

        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"status": "ok", "detail": "No JSON returned"}

    async def upsert_rows(self, table: str, rows: list[dict], conflict: str):
        if not rows:
            return []

        if self._pool:
            columns = list(rows[0].keys())
            column_list = ", ".join(columns)
            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
            update_clause = ", ".join(f"{col}=EXCLUDED.{col}" for col in columns if col != conflict)
            sql = (
                f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {update_clause}"
            )
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(sql, [tuple(row[col] for col in columns) for row in rows])
            return rows

        response = await self._rest_client.post(
            f"/{table}",
            json=rows,
            params={"on_conflict": conflict, "return": "minimal"},
        )
        response.raise_for_status()
        return []

    async def close(self):
        if self._pool:
            await self._pool.close()
        await self._rest_client.aclose()
        await self._functions_client.aclose()
