# Memory Graph MCP Server (Prototype)

> **Status:** Phase 1 prototype. Not published. Lives alongside the existing
> [`src/memory`](../memory/) JSONL server, which it is intended to eventually
> replace.

A FastMCP-based Python server that backs the knowledge graph with a relational
schema in Postgres instead of a flat JSONL file. The MCP tool surface is a
drop-in replacement for `@modelcontextprotocol/server-memory`, but the storage
layer is structured so that later phases (entity resolution, audit/provenance,
conflict reconciliation, hybrid search) can land without changing the tool
contract.

## Why

The existing TypeScript memory server stores observations as raw strings in a
JSONL file with no IDs, no audit trail, no soft deletes, no dedupe, and no
search index. That is fine for demos and unworkable for an actual long-running
memory. This prototype keeps the same wire-level tools but replaces the
storage with:

- Relational tables for entities, observations, relations
- Soft deletes (`deleted_at`) so memory history is recoverable
- Content hashing on observations for deterministic dedupe
- A generated `tsvector` + GIN index ready for full-text search
- Schema slots for aliases, sources, audit events, and conflicts

## Architecture

```
MCP Client (Claude / Codex / etc.)
        |
        v
FastMCP Python server  (this package)
        |
        v
MemoryGraphRepository  (asyncpg)
        |
        v
Postgres 16
```

The MCP layer never exposes raw SQL or arbitrary mutations to the model; it
only exposes intent-level tools. Later phases can swap the repository for a
GraphQL client (Hasura/PostGraphile) without changing the tool surface.

## Tools (Phase 1)

The same nine tools as the legacy memory server, with identical request /
response shapes:

| Tool                  | Description                                                |
| --------------------- | ---------------------------------------------------------- |
| `create_entities`     | Create entities; existing names are skipped.               |
| `create_relations`    | Create directed relations; duplicates are skipped.         |
| `add_observations`    | Add observations to an entity. Errors if entity is missing.|
| `delete_entities`     | Soft-delete entities and their relations.                  |
| `delete_observations` | Soft-delete specific observations.                         |
| `delete_relations`    | Soft-delete specific relations.                            |
| `read_graph`          | Return the entire graph.                                   |
| `search_nodes`        | Substring match on names, types, and observation content.  |
| `open_nodes`          | Return specific entities and any relation that touches them.|

A read-only resource (`memory-graph://graph`) is also exposed.

## Local development

```bash
cd src/memory-graph
uv sync --all-extras --dev

# Bring up Postgres + the server over HTTP for quick poking
docker compose up --build

# Or run against an existing Postgres over stdio (matches the legacy server)
export MEMORY_GRAPH_DATABASE_URL="postgresql://memory:memory@localhost:5432/memory"
uv run mcp-server-memory-graph
```

Migrations live in [`migrations/`](./migrations/) and are applied at server
startup. They use `IF NOT EXISTS` so re-running is safe; a real deployment
should swap to a versioned migration tool (Alembic / sqlx / Flyway).

## Configuration

All settings come from environment variables, prefixed `MEMORY_GRAPH_`:

| Variable                       | Default                                              |
| ------------------------------ | ---------------------------------------------------- |
| `MEMORY_GRAPH_DATABASE_URL`    | `postgresql://memory:memory@localhost:5432/memory`   |
| `MEMORY_GRAPH_POOL_MIN_SIZE`   | `1`                                                  |
| `MEMORY_GRAPH_POOL_MAX_SIZE`   | `10`                                                 |
| `MEMORY_GRAPH_TRANSPORT`       | `stdio` (`http` for network deployments)             |
| `MEMORY_GRAPH_HTTP_HOST`       | `0.0.0.0`                                            |
| `MEMORY_GRAPH_HTTP_PORT`       | `8000`                                               |

## Roadmap

This prototype intentionally only does Phase 1. The schema and architecture
are sized for the rest:

- **Phase 2 — relational graph schema**
  Aliases, sources, observation provenance, soft delete cascades, dedupe
  hashes (already in place).
- **Phase 3 — intent-level tools**
  `remember_observation`, `resolve_entity`, `get_entity_neighborhood`,
  `merge_entities`, `forget_memory`, `explain_memory`, `find_conflicts`.
- **Phase 4 — search and retrieval**
  Hybrid ranking over Postgres FTS, graph proximity, recency, and
  (optionally) `pgvector` embeddings.
- **Phase 5 — governance**
  Audit log via `memory_events`, sensitive-memory policies, manual
  approval flow, export/import, consistency checker.

## License

MIT — see [LICENSE](../../LICENSE).
