"""Pydantic models exposed on the MCP wire.

Field names mirror the original TypeScript memory server (`name`, `entityType`,
`from`, `to`, `relationType`) so this prototype is a drop-in replacement for
existing clients. The Postgres schema uses snake_case columns; the repository
translates between the two.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str = Field(description="The unique name of the entity.")
    entityType: str = Field(description="The type of the entity, e.g. 'person'.")
    observations: list[str] = Field(
        default_factory=list,
        description="Atomic observation strings attached to this entity.",
    )


class Relation(BaseModel):
    from_: str = Field(
        alias="from",
        description="The name of the entity where the relation starts.",
    )
    to: str = Field(description="The name of the entity where the relation ends.")
    relationType: str = Field(
        description="The type of the relation, in active voice (e.g. 'works_at').",
    )

    model_config = {"populate_by_name": True}


class KnowledgeGraph(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


class ObservationInput(BaseModel):
    entityName: str
    contents: list[str]


class ObservationDeletion(BaseModel):
    entityName: str
    observations: list[str]


class AddObservationsResult(BaseModel):
    entityName: str
    addedObservations: list[str]


class MutationStatus(BaseModel):
    success: bool
    message: str
