import asyncio
from pathlib import Path
import asyncpg
from dotenv import load_dotenv
import os


def load_sql_file() -> str:
    sql_path = Path(__file__).resolve().parent.parent / "supabase_schema.sql"
    return sql_path.read_text(encoding="utf-8")


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise SystemExit("SUPABASE_DB_URL is required in backend/.env to run this script.")

    sql = load_sql_file()
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(sql)
        print("Supabase tables created successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
