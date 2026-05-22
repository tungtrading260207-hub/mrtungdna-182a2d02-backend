from typing import Any, Type
from pydantic import BaseModel, ValidationError


class DataValidator:
    @staticmethod
    def validate_one(schema: Type[BaseModel], raw_data: Any) -> dict:
        validated = schema.model_validate(raw_data)
        return validated.model_dump(exclude_none=True)

    @staticmethod
    def validate_many(schema: Type[BaseModel], raw_items: list[dict]) -> tuple[list[dict], list[dict]]:
        valid_records: list[dict] = []
        errors: list[dict] = []

        if not raw_items:
            return valid_records, errors

        for index, item in enumerate(raw_items):
            try:
                validated = schema.model_validate(item)
                valid_records.append(validated.model_dump(exclude_none=True))
            except ValidationError as exc:
                errors.append({
                    "index": index,
                    "errors": exc.errors(),
                    "raw_data": item,
                })

        return valid_records, errors
