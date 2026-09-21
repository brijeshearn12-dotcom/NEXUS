"""Base Pydantic model for NEXUS with clean string ID and MongoDB compatibility."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class NexusBaseModel(BaseModel):
    """Base model providing string ID handling, MongoDB _id coercion, and validation."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    @model_validator(mode="before")
    @classmethod
    def handle_mongo_id(cls, data: Any) -> Any:
        """Coerce MongoDB ObjectId or _id to string id if present."""
        if isinstance(data, dict):
            if "_id" in data and "id" not in data:
                data = dict(data)
                data["id"] = str(data.pop("_id"))
        return data
