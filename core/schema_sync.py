import logging
from datetime import datetime, timezone
from typing import Any
import httpx
from app.db import SupabaseClient
from core.schemas import (
    InverseShortSetup,
    MacroIndicator,
    MarketNews,
    MarketScan,
    MarketSignal,
    RumorHuntingRecord,
    SystemHealth,
    VNStockProfile,
)

MODEL_CLASSES = [
    VNStockProfile,
    MarketScan,
    MarketSignal,
    MacroIndicator,
    MarketNews,
    SystemHealth,
    RumorHuntingRecord,
    InverseShortSetup,
]

TYPE_MAP = {
    "str": {"text", "varchar", "character varying", "character", "citext"},
    "int": {"integer", "bigint", "smallint", "serial", "bigserial"},
    "float": {"numeric", "real", "double precision", "decimal"},
    "bool": {"boolean"},
    "dict": {"json", "jsonb"},
    "list": {"json", "jsonb"},
    "datetime": {"timestamp without time zone", "timestamp with time zone", "timestamptz", "date"},
    "any": {"text", "json", "jsonb", "varchar", "character varying"},
}


class SchemaSyncChecker:
    def __init__(
        self,
        supabase_client: SupabaseClient,
        dashboard_url: str | None = None,
        dashboard_api_key: str | None = None,
        interval_seconds: int = 3600,
    ):
        self.supabase_client = supabase_client
        self.dashboard_url = dashboard_url
        self.dashboard_api_key = dashboard_api_key
        self.interval_seconds = interval_seconds
        self.status: dict[str, Any] = {
            "last_run": None,
            "last_success": None,
            "last_error": None,
            "last_message": None,
            "last_mismatch_count": 0,
        }

    @staticmethod
    def _get_model_fields(model: type[Any]) -> dict[str, str]:
        fields = {}
        model_fields = getattr(model, "model_fields", None)
        if model_fields is None:
            model_fields = getattr(model, "__fields__", {})

        for name, field in model_fields.items():
            annotation = getattr(field, "annotation", None)
            if annotation is None:
                annotation = getattr(field, "outer_type_", None)
            if annotation is None:
                annotation_name = "any"
            elif getattr(annotation, "__origin__", None) is list:
                annotation_name = "list"
            elif getattr(annotation, "__origin__", None) is dict:
                annotation_name = "dict"
            elif annotation in (str, int, float, bool):
                annotation_name = annotation.__name__
            elif annotation.__name__ == "datetime":
                annotation_name = "datetime"
            else:
                annotation_name = "any"

            fields[name] = annotation_name
        return fields

    def get_code_schema(self) -> dict[str, dict[str, str]]:
        schema_map: dict[str, dict[str, str]] = {}
        for model in MODEL_CLASSES:
            table_name = getattr(model, "table_name", None)
            if not table_name:
                continue
            schema_map[str(table_name).strip().lower()] = self._get_model_fields(model)
        return schema_map

    async def fetch_db_schema(self) -> dict[str, dict[str, dict[str, str]]]:
        if not self.supabase_client._pool:
            raise RuntimeError("Postgres connection pool is required for schema check")

        query = """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1
            ORDER BY table_name, ordinal_position;
        """
        rows = {}
        async with self.supabase_client._pool.acquire() as conn:
            results = await conn.fetch(query, self.supabase_client.schema)
            for row in results:
                table = row["table_name"].strip().lower()
                rows.setdefault(table, {})
                rows[table][row["column_name"].strip().lower()] = {
                    "data_type": row["data_type"].strip().lower(),
                    "is_nullable": row["is_nullable"],
                }
        return rows

    @staticmethod
    def _normalize_db_type(data_type: str) -> str:
        return data_type.strip().lower()

    def compare_schemas(
        self,
        code_schema: dict[str, dict[str, str]],
        db_schema: dict[str, dict[str, dict[str, str]]],
    ) -> list[dict[str, Any]]:
        mismatches: list[dict[str, Any]] = []
        for table_name, expected_fields in code_schema.items():
            table_info = db_schema.get(table_name)
            if table_info is None:
                mismatches.append({
                    "table": table_name,
                    "error": "missing_table",
                    "details": f"Table '{table_name}' exists in code schema but is missing in database.",
                })
                continue

            actual_columns = set(table_info.keys())
            expected_columns = set(expected_fields.keys())
            missing_columns = sorted(expected_columns - actual_columns)
            extra_columns = sorted(actual_columns - expected_columns)
            if missing_columns or extra_columns:
                mismatches.append({
                    "table": table_name,
                    "error": "column_mismatch",
                    "missing_columns": missing_columns,
                    "extra_columns": extra_columns,
                })

            for field_name, annotation_name in expected_fields.items():
                if field_name not in table_info:
                    continue
                actual_type = self._normalize_db_type(table_info[field_name]["data_type"])
                expected_types = TYPE_MAP.get(annotation_name, TYPE_MAP["any"])
                if actual_type not in expected_types:
                    mismatches.append({
                        "table": table_name,
                        "column": field_name,
                        "error": "type_mismatch",
                        "expected": annotation_name,
                        "actual": actual_type,
                    })
        return mismatches

    @staticmethod
    def build_alert_message(mismatches: list[dict[str, Any]]) -> str:
        chunks: list[str] = []
        for mismatch in mismatches:
            if mismatch["error"] == "missing_table":
                chunks.append(mismatch["details"])
            elif mismatch["error"] == "column_mismatch":
                parts = []
                if mismatch.get("missing_columns"):
                    parts.append(f"missing columns {mismatch['missing_columns']}")
                if mismatch.get("extra_columns"):
                    parts.append(f"extra columns {mismatch['extra_columns']}")
                chunks.append(f"Table '{mismatch['table']}': " + ", ".join(parts))
            elif mismatch["error"] == "type_mismatch":
                chunks.append(
                    f"Table '{mismatch['table']}', column '{mismatch['column']}': expected {mismatch['expected']}, actual {mismatch['actual']}"
                )
        return "; ".join(chunks)

    async def send_dashboard_alert(self, mismatch_message: str, mismatches: list[dict[str, Any]]) -> None:
        record = {
            "service": "schema_sync",
            "status": "error",
            "message": mismatch_message,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.supabase_client.insert_rows("system_health", [record])
        except Exception as exc:
            logging.warning("[SchemaSyncChecker] Failed to insert system_health alert: %s", exc)

        if not self.dashboard_url:
            logging.info("[SchemaSyncChecker] Dashboard alert URL is not configured, skipping external notification.")
            return

        payload = {
            "event": "schema_mismatch",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": mismatch_message,
            "details": mismatches,
        }
        headers = {"Content-Type": "application/json"}
        if self.dashboard_api_key:
            headers["Authorization"] = f"Bearer {self.dashboard_api_key}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(self.dashboard_url, json=payload, headers=headers)
                response.raise_for_status()
                logging.info("[SchemaSyncChecker] Dashboard notification sent successfully.")
            except Exception as exc:
                logging.warning("[SchemaSyncChecker] Failed to send dashboard notification: %s", exc)

    async def run_once(self) -> dict[str, Any]:
        if not self.supabase_client._pool:
            raise RuntimeError("Schema sync requires postgres connection pool")

        code_schema = self.get_code_schema()
        db_schema = await self.fetch_db_schema()
        mismatches = self.compare_schemas(code_schema, db_schema)
        self.status["last_run"] = datetime.now(timezone.utc).isoformat()
        self.status["last_mismatch_count"] = len(mismatches)

        if not mismatches:
            logging.info("[SchemaSyncChecker] Schema sync check passed.")
            self.status.update({"last_success": True, "last_error": None, "last_message": "ok"})
            return {"status": "ok", "mismatches": []}

        message = self.build_alert_message(mismatches)
        logging.warning("[SchemaSyncChecker] Schema mismatch detected: %s", message)
        self.status.update({"last_success": False, "last_error": message, "last_message": message})
        await self.send_dashboard_alert(message, mismatches)
        return {"status": "mismatch", "mismatches": mismatches, "message": message}

    async def start_loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logging.exception("[SchemaSyncChecker] Schema sync loop failed: %s", exc)
            await asyncio.sleep(self.interval_seconds)
