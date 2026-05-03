"""Async Postgres repository for the memory graph.

This is the only module that talks SQL. The MCP tool layer never sees raw
columns or driver objects; it only sees the Pydantic models in `models.py`.
That separation is what later phases (Hasura, vector search, audit events)
plug into without churning the tool surface.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import asyncpg

from .models import (
    AddObservationsResult,
    Entity,
    KnowledgeGraph,
    ObservationDeletion,
    ObservationInput,
    Relation,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class MemoryGraphRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def connect(
        cls, dsn: str, *, min_size: int = 1, max_size: int = 10
    ) -> "MemoryGraphRepository":
        pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        assert pool is not None
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def apply_migrations(self) -> None:
        """Apply SQL files in `migrations/` in lexicographic order.

        Idempotent: every migration uses CREATE ... IF NOT EXISTS / ADD COLUMN
        IF NOT EXISTS. Good enough for a prototype; a real deployment should
        track applied versions in a schema_migrations table.
        """
        if not MIGRATIONS_DIR.exists():
            return
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        async with self._pool.acquire() as conn:
            for f in files:
                await conn.execute(f.read_text())

    # ------------------------------------------------------------------ entities

    async def create_entities(self, entities: Iterable[Entity]) -> list[Entity]:
        """Insert new entities; entities whose canonical_name already exists
        (and is not soft-deleted) are skipped, matching the legacy behavior."""
        created: list[Entity] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for ent in entities:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO entities (canonical_name, entity_type)
                        VALUES ($1, $2)
                        ON CONFLICT (canonical_name) WHERE deleted_at IS NULL
                        DO NOTHING
                        RETURNING id
                        """,
                        ent.name,
                        ent.entityType,
                    )
                    if row is None:
                        continue
                    entity_id = row["id"]
                    new_obs: list[str] = []
                    for content in ent.observations:
                        inserted = await conn.fetchval(
                            """
                            INSERT INTO observations (entity_id, content, content_hash)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (entity_id, content_hash) DO NOTHING
                            RETURNING id
                            """,
                            entity_id,
                            content,
                            _hash(content),
                        )
                        if inserted is not None:
                            new_obs.append(content)
                    created.append(
                        Entity(
                            name=ent.name,
                            entityType=ent.entityType,
                            observations=new_obs,
                        )
                    )
        return created

    async def delete_entities(self, names: Iterable[str]) -> None:
        names = list(names)
        if not names:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE entities
                SET deleted_at = now()
                WHERE canonical_name = ANY($1::text[])
                  AND deleted_at IS NULL
                """,
                names,
            )
            # Cascade soft-deletes so search/read views stay consistent.
            await conn.execute(
                """
                UPDATE relations r
                SET deleted_at = now()
                FROM entities e
                WHERE (r.from_entity_id = e.id OR r.to_entity_id = e.id)
                  AND e.canonical_name = ANY($1::text[])
                  AND r.deleted_at IS NULL
                """,
                names,
            )

    # -------------------------------------------------------------- observations

    async def add_observations(
        self, observations: Iterable[ObservationInput]
    ) -> list[AddObservationsResult]:
        results: list[AddObservationsResult] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for obs in observations:
                    entity_id = await conn.fetchval(
                        """
                        SELECT id FROM entities
                        WHERE canonical_name = $1 AND deleted_at IS NULL
                        """,
                        obs.entityName,
                    )
                    if entity_id is None:
                        raise ValueError(
                            f"Entity with name {obs.entityName} not found"
                        )
                    added: list[str] = []
                    for content in obs.contents:
                        inserted = await conn.fetchval(
                            """
                            INSERT INTO observations (entity_id, content, content_hash)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (entity_id, content_hash) DO NOTHING
                            RETURNING id
                            """,
                            entity_id,
                            content,
                            _hash(content),
                        )
                        if inserted is not None:
                            added.append(content)
                    results.append(
                        AddObservationsResult(
                            entityName=obs.entityName, addedObservations=added
                        )
                    )
        return results

    async def delete_observations(
        self, deletions: Iterable[ObservationDeletion]
    ) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for d in deletions:
                    if not d.observations:
                        continue
                    hashes = [_hash(c) for c in d.observations]
                    await conn.execute(
                        """
                        UPDATE observations o
                        SET deleted_at = now()
                        FROM entities e
                        WHERE o.entity_id = e.id
                          AND e.canonical_name = $1
                          AND e.deleted_at IS NULL
                          AND o.content_hash = ANY($2::text[])
                          AND o.deleted_at IS NULL
                        """,
                        d.entityName,
                        hashes,
                    )

    # ----------------------------------------------------------------- relations

    async def create_relations(
        self, relations: Iterable[Relation]
    ) -> list[Relation]:
        created: list[Relation] = []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for rel in relations:
                    row = await conn.fetchrow(
                        """
                        WITH src AS (
                            SELECT id FROM entities
                            WHERE canonical_name = $1 AND deleted_at IS NULL
                        ),
                        dst AS (
                            SELECT id FROM entities
                            WHERE canonical_name = $2 AND deleted_at IS NULL
                        )
                        INSERT INTO relations (from_entity_id, to_entity_id, relation_type)
                        SELECT src.id, dst.id, $3
                        FROM src, dst
                        ON CONFLICT (from_entity_id, to_entity_id, relation_type)
                            WHERE deleted_at IS NULL
                        DO NOTHING
                        RETURNING id
                        """,
                        rel.from_,
                        rel.to,
                        rel.relationType,
                    )
                    if row is not None:
                        created.append(rel)
        return created

    async def delete_relations(self, relations: Iterable[Relation]) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for rel in relations:
                    await conn.execute(
                        """
                        UPDATE relations r
                        SET deleted_at = now()
                        FROM entities src, entities dst
                        WHERE r.from_entity_id = src.id
                          AND r.to_entity_id = dst.id
                          AND src.canonical_name = $1
                          AND dst.canonical_name = $2
                          AND r.relation_type = $3
                          AND r.deleted_at IS NULL
                        """,
                        rel.from_,
                        rel.to,
                        rel.relationType,
                    )

    # ----------------------------------------------------------------- read-only

    async def read_graph(self) -> KnowledgeGraph:
        return await self._build_graph(filter_names=None)

    async def search_nodes(self, query: str) -> KnowledgeGraph:
        """Match by entity name, type, or observation content (case-insensitive
        substring). For the prototype we keep parity with the legacy server;
        the tsvector index is in place for a later semantic upgrade."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT e.canonical_name
                FROM entities e
                LEFT JOIN observations o
                       ON o.entity_id = e.id AND o.deleted_at IS NULL
                WHERE e.deleted_at IS NULL
                  AND (
                       e.canonical_name ILIKE '%' || $1 || '%'
                    OR e.entity_type    ILIKE '%' || $1 || '%'
                    OR o.content        ILIKE '%' || $1 || '%'
                  )
                """,
                query,
            )
        names = [r["canonical_name"] for r in rows]
        return await self._build_graph(filter_names=names)

    async def open_nodes(self, names: list[str]) -> KnowledgeGraph:
        return await self._build_graph(filter_names=names)

    async def _build_graph(
        self, *, filter_names: list[str] | None
    ) -> KnowledgeGraph:
        """Single read path used by read_graph / search_nodes / open_nodes.

        Relations are included whenever EITHER endpoint is in the result set,
        matching the legacy server's behavior so callers can discover
        connections to nodes outside the search frame.
        """
        async with self._pool.acquire() as conn:
            if filter_names is None:
                ent_rows = await conn.fetch(
                    """
                    SELECT id, canonical_name, entity_type
                    FROM entities
                    WHERE deleted_at IS NULL
                    ORDER BY canonical_name
                    """
                )
            else:
                ent_rows = await conn.fetch(
                    """
                    SELECT id, canonical_name, entity_type
                    FROM entities
                    WHERE deleted_at IS NULL
                      AND canonical_name = ANY($1::text[])
                    ORDER BY canonical_name
                    """,
                    filter_names,
                )

            ids = [r["id"] for r in ent_rows]
            if not ids:
                return KnowledgeGraph()

            obs_rows = await conn.fetch(
                """
                SELECT entity_id, content
                FROM observations
                WHERE deleted_at IS NULL
                  AND entity_id = ANY($1::uuid[])
                ORDER BY created_at
                """,
                ids,
            )

            rel_rows = await conn.fetch(
                """
                SELECT src.canonical_name AS from_name,
                       dst.canonical_name AS to_name,
                       r.relation_type
                FROM relations r
                JOIN entities src ON src.id = r.from_entity_id
                JOIN entities dst ON dst.id = r.to_entity_id
                WHERE r.deleted_at IS NULL
                  AND src.deleted_at IS NULL
                  AND dst.deleted_at IS NULL
                  AND (r.from_entity_id = ANY($1::uuid[])
                       OR r.to_entity_id = ANY($1::uuid[]))
                """,
                ids,
            )

        observations_by_entity: dict[str, list[str]] = {}
        for r in obs_rows:
            observations_by_entity.setdefault(r["entity_id"], []).append(r["content"])

        entities = [
            Entity(
                name=r["canonical_name"],
                entityType=r["entity_type"],
                observations=observations_by_entity.get(r["id"], []),
            )
            for r in ent_rows
        ]
        relations = [
            Relation(
                **{
                    "from": r["from_name"],
                    "to": r["to_name"],
                    "relationType": r["relation_type"],
                }
            )
            for r in rel_rows
        ]
        return KnowledgeGraph(entities=entities, relations=relations)
