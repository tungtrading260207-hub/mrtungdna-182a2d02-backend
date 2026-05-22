from abc import ABC, abstractmethod
from typing import Any
import logging
from pydantic import BaseModel
from app.db import SupabaseClient
from core.validator import DataValidator


class BaseWorker(ABC):
    def __init__(
        self,
        supabase_client: SupabaseClient,
        schema: type[BaseModel],
        table_name: str,
        conflict: str = "id",
    ):
        self.supabase_client = supabase_client
        self.schema = schema
        self.table_name = table_name
        self.conflict = conflict
        self.validator = DataValidator()

    @abstractmethod
    async def fetch(self) -> Any:
        raise NotImplementedError

    def normalize(self, payload: Any) -> list[dict]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        return [payload]

    def validate_records(self, records: list[dict]) -> list[dict]:
        valid_records, errors = self.validator.validate_many(self.schema, records)
        if errors:
            logging.warning(
                "[%s] Data validation found %s invalid records.",
                self.__class__.__name__,
                len(errors),
            )
            for error in errors:
                logging.debug(
                    "[%s] Record %s validation errors: %s",
                    self.__class__.__name__,
                    error["index"],
                    error["errors"],
                )
        return valid_records

    async def load(self, records: list[dict]) -> list[dict]:
        if not records:
            return []
        await self.supabase_client.upsert_rows(self.table_name, records, conflict=self.conflict)
        return records

    async def run_once(self) -> list[dict]:
        payload = await self.fetch()
        records = self.normalize(payload)
        validated = self.validate_records(records)
        return await self.load(validated)
