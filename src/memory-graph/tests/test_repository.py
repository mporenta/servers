"""Integration tests for MemoryGraphRepository.

Skipped unless `MEMORY_GRAPH_TEST_DATABASE_URL` is set, so CI without a
Postgres service stays green. The compose stack in `docker-compose.yml`
exposes a suitable database for local runs.
"""

from __future__ import annotations

import os
import uuid

import pytest

from mcp_server_memory_graph.models import (
    Entity,
    ObservationDeletion,
    ObservationInput,
    Relation,
)
from mcp_server_memory_graph.repository import MemoryGraphRepository

DSN = os.environ.get("MEMORY_GRAPH_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    DSN is None, reason="set MEMORY_GRAPH_TEST_DATABASE_URL to run"
)


@pytest.fixture
async def repo():
    assert DSN is not None
    r = await MemoryGraphRepository.connect(DSN)
    await r.apply_migrations()
    try:
        yield r
    finally:
        await r.close()


def _ns() -> str:
    return f"test_{uuid.uuid4().hex[:8]}"


async def test_create_entities_dedupes_on_name(repo: MemoryGraphRepository):
    name = _ns()
    first = await repo.create_entities(
        [Entity(name=name, entityType="person", observations=["a"])]
    )
    second = await repo.create_entities(
        [Entity(name=name, entityType="person", observations=["b"])]
    )
    assert len(first) == 1
    assert second == []  # already exists, skipped


async def test_add_observations_dedupes_and_errors_on_missing(
    repo: MemoryGraphRepository,
):
    name = _ns()
    await repo.create_entities([Entity(name=name, entityType="person")])

    added = await repo.add_observations(
        [ObservationInput(entityName=name, contents=["x", "x", "y"])]
    )
    assert added[0].addedObservations == ["x", "y"]

    again = await repo.add_observations(
        [ObservationInput(entityName=name, contents=["x", "z"])]
    )
    assert again[0].addedObservations == ["z"]

    with pytest.raises(ValueError):
        await repo.add_observations(
            [ObservationInput(entityName="missing-" + name, contents=["x"])]
        )


async def test_relations_search_and_open_nodes(repo: MemoryGraphRepository):
    a, b = _ns(), _ns()
    await repo.create_entities(
        [
            Entity(name=a, entityType="person", observations=["likes coffee"]),
            Entity(name=b, entityType="org"),
        ]
    )
    created = await repo.create_relations(
        [Relation(**{"from": a, "to": b, "relationType": "works_at"})]
    )
    assert len(created) == 1

    # search should find the entity by observation content
    found = await repo.search_nodes("coffee")
    assert any(e.name == a for e in found.entities)
    # relation is included because endpoint a is in the result set
    assert any(r.from_ == a and r.to == b for r in found.relations)

    # open_nodes returns relations even when the other endpoint isn't requested
    only_a = await repo.open_nodes([a])
    assert any(r.to == b for r in only_a.relations)


async def test_delete_observations_and_entity_cascades(
    repo: MemoryGraphRepository,
):
    a, b = _ns(), _ns()
    await repo.create_entities(
        [
            Entity(name=a, entityType="person", observations=["one", "two"]),
            Entity(name=b, entityType="person"),
        ]
    )
    await repo.create_relations(
        [Relation(**{"from": a, "to": b, "relationType": "knows"})]
    )

    await repo.delete_observations(
        [ObservationDeletion(entityName=a, observations=["one"])]
    )
    graph = await repo.open_nodes([a])
    assert graph.entities[0].observations == ["two"]

    await repo.delete_entities([a])
    graph = await repo.read_graph()
    assert all(e.name != a for e in graph.entities)
    assert all(r.from_ != a and r.to != a for r in graph.relations)
