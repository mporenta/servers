from mcp_server_memory_graph.models import (
    Entity,
    KnowledgeGraph,
    Relation,
)


def test_entity_round_trip():
    e = Entity(name="John_Smith", entityType="person", observations=["x"])
    assert e.model_dump()["entityType"] == "person"


def test_relation_accepts_from_alias_and_serializes_back():
    """`from` is a Python keyword. The model uses an alias so the wire format
    matches the legacy server."""
    rel = Relation.model_validate(
        {"from": "A", "to": "B", "relationType": "knows"}
    )
    assert rel.from_ == "A"
    assert rel.to == "B"
    dumped = rel.model_dump(by_alias=True)
    assert dumped == {"from": "A", "to": "B", "relationType": "knows"}


def test_relation_populate_by_name_also_works():
    rel = Relation(from_="A", to="B", relationType="knows")
    assert rel.from_ == "A"


def test_knowledge_graph_default_empty():
    g = KnowledgeGraph()
    assert g.entities == []
    assert g.relations == []
