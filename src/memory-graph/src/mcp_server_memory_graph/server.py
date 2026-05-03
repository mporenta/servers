"""FastMCP server exposing the relational memory graph.

Phase 1 mirrors the original `@modelcontextprotocol/server-memory` tool surface
so existing clients keep working. Later phases add intent-level tools
(`remember_observation`, `resolve_entity`, `find_conflicts`, ...) on top of the
same repository.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastmcp import Context, FastMCP

from .config import Settings
from .models import (
    AddObservationsResult,
    Entity,
    KnowledgeGraph,
    MutationStatus,
    ObservationDeletion,
    ObservationInput,
    Relation,
)
from .repository import MemoryGraphRepository

logger = logging.getLogger("mcp_server_memory_graph")


@dataclass
class AppContext:
    repo: MemoryGraphRepository


def _repo(ctx: Context) -> MemoryGraphRepository:
    """Pull the repository out of the FastMCP lifespan context."""
    return ctx.request_context.lifespan_context.repo


def build_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[AppContext]:
        repo = await MemoryGraphRepository.connect(
            settings.database_url,
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
        )
        try:
            await repo.apply_migrations()
            yield AppContext(repo=repo)
        finally:
            await repo.close()

    mcp = FastMCP(
        "memory-graph",
        instructions=(
            "Relational memory graph backed by Postgres. Tools mirror the "
            "legacy @modelcontextprotocol/server-memory surface."
        ),
        lifespan=lifespan,
    )

    # ------------------------------------------------------------- write tools

    @mcp.tool
    async def create_entities(entities: list[Entity], ctx: Context) -> KnowledgeGraph:
        """Create multiple new entities in the knowledge graph.

        Entities whose names already exist are skipped.
        """
        created = await _repo(ctx).create_entities(entities)
        return KnowledgeGraph(entities=created, relations=[])

    @mcp.tool
    async def create_relations(
        relations: list[Relation], ctx: Context
    ) -> KnowledgeGraph:
        """Create multiple new relations between entities.

        Relations should be in active voice. Duplicate relations are skipped.
        """
        created = await _repo(ctx).create_relations(relations)
        return KnowledgeGraph(entities=[], relations=created)

    @mcp.tool
    async def add_observations(
        observations: list[ObservationInput], ctx: Context
    ) -> list[AddObservationsResult]:
        """Add new observations to existing entities. Fails if an entity is missing."""
        return await _repo(ctx).add_observations(observations)

    @mcp.tool
    async def delete_entities(
        entityNames: list[str], ctx: Context
    ) -> MutationStatus:
        """Soft-delete entities and their relations. Silent on missing entities."""
        await _repo(ctx).delete_entities(entityNames)
        return MutationStatus(success=True, message="Entities deleted successfully")

    @mcp.tool
    async def delete_observations(
        deletions: list[ObservationDeletion], ctx: Context
    ) -> MutationStatus:
        """Soft-delete specific observations from entities."""
        await _repo(ctx).delete_observations(deletions)
        return MutationStatus(
            success=True, message="Observations deleted successfully"
        )

    @mcp.tool
    async def delete_relations(
        relations: list[Relation], ctx: Context
    ) -> MutationStatus:
        """Soft-delete specific relations from the graph."""
        await _repo(ctx).delete_relations(relations)
        return MutationStatus(success=True, message="Relations deleted successfully")

    # -------------------------------------------------------------- read tools

    @mcp.tool
    async def read_graph(ctx: Context) -> KnowledgeGraph:
        """Return the entire knowledge graph."""
        return await _repo(ctx).read_graph()

    @mcp.tool
    async def search_nodes(query: str, ctx: Context) -> KnowledgeGraph:
        """Substring-match entity names, types, and observation content."""
        return await _repo(ctx).search_nodes(query)

    @mcp.tool
    async def open_nodes(names: list[str], ctx: Context) -> KnowledgeGraph:
        """Return the requested entities and any relation that touches them."""
        return await _repo(ctx).open_nodes(names)

    @mcp.resource("memory-graph://graph")
    async def graph_resource(ctx: Context) -> KnowledgeGraph:
        """Read-only resource view of the full graph."""
        return await _repo(ctx).read_graph()

    return mcp


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    mcp = build_server(settings)
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.http_host, port=settings.http_port)
    else:
        mcp.run(transport="stdio")
