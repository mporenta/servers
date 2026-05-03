-- Initial relational memory graph schema.
--
-- Phase 1 only writes to entities, observations, and relations. The remaining
-- tables (entity_aliases, sources, memory_events, memory_conflicts) are created
-- now so later phases (entity resolution, audit trail, conflict reconciliation)
-- can land without another migration window.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS entities_canonical_name_unique
    ON entities (canonical_name)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS entities_entity_type_idx
    ON entities (entity_type)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS entity_aliases (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id         UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias             TEXT NOT NULL,
    alias_normalized  TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, alias_normalized)
);

CREATE INDEX IF NOT EXISTS entity_aliases_normalized_idx
    ON entity_aliases (alias_normalized);

CREATE TABLE IF NOT EXISTS sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     TEXT NOT NULL,
    source_ref      TEXT,
    conversation_id TEXT,
    message_id      TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS observations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id     UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    confidence    NUMERIC NOT NULL DEFAULT 1.0,
    source_id     UUID REFERENCES sources(id) ON DELETE SET NULL,
    valid_from    TIMESTAMPTZ,
    valid_to      TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ,
    UNIQUE (entity_id, content_hash)
);

CREATE INDEX IF NOT EXISTS observations_entity_idx
    ON observations (entity_id)
    WHERE deleted_at IS NULL;

-- Generated tsvector column lets full-text search work without app-side maintenance.
ALTER TABLE observations
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS observations_search_idx
    ON observations USING GIN (search_vector);

CREATE TABLE IF NOT EXISTS relations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id  UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    confidence      NUMERIC NOT NULL DEFAULT 1.0,
    source_id       UUID REFERENCES sources(id) ON DELETE SET NULL,
    valid_from      TIMESTAMPTZ,
    valid_to        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS relations_unique_active
    ON relations (from_entity_id, to_entity_id, relation_type)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS relations_from_idx
    ON relations (from_entity_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS relations_to_idx
    ON relations (to_entity_id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS memory_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type   TEXT NOT NULL,
    target_type  TEXT NOT NULL,
    target_id    UUID,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_events_target_idx
    ON memory_events (target_type, target_id);
