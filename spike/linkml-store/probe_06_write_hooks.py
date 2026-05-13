"""Probe #6: write hooks for validation + provenance.

Subclass DuckDBCollection, override `_pre_insert_hook` and `_post_insert_hook`
to (a) reject inserts that fail a pretend "hippo validator" and (b) emit
a fake provenance record. Confirms hippo's WriteValidator + ProvenanceManager
can be wired into linkml-store at the hook layer.
"""
import tempfile
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView
from linkml_store import Client
from linkml_store.api.stores.duckdb.duckdb_collection import DuckDBCollection


SCHEMA = """
id: https://example.org/probe6
name: probe6
prefixes:
  linkml: https://w3id.org/linkml/
default_prefix: ex
default_range: string
imports: [linkml:types]
classes:
  Entity:
    abstract: true
    attributes:
      id: {identifier: true, range: string, required: true}
      is_available: {range: boolean, required: true, ifabsent: "true"}
  Sample:
    is_a: Entity
    attributes:
      name: {range: string, required: true}
"""


class HippoCollection(DuckDBCollection):
    """Demonstrates hippo write-path concerns plugged into linkml-store hooks."""

    provenance: list  # in-memory provenance log for the probe

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provenance = []

    def _pre_insert_hook(self, objs, **kwargs):
        # Stand-in for hippo's WriteValidator chain.
        for obj in objs:
            if obj.get("name") == "BAD":
                raise ValueError(
                    f"hippo validator rejected object id={obj.get('id')!r}: name='BAD' is reserved"
                )
        # Then call super so linkml-store's own validation runs too.
        super()._pre_insert_hook(objs, **kwargs)

    def _post_insert_hook(self, objs, **kwargs):
        # Stand-in for ProvenanceManager.record_write.
        for obj in objs:
            self.provenance.append({
                "entity_id": obj.get("id"),
                "operation": "create",
                "actor_id": "system",
            })
        super()._post_insert_hook(objs, **kwargs)


with tempfile.TemporaryDirectory() as tmp:
    schema_path = Path(tmp) / "schema.yaml"
    schema_path.write_text(SCHEMA)

    client = Client()
    db = client.attach_database("duckdb", alias="probe6")
    db.set_schema_view(SchemaView(str(schema_path)))

    # Force linkml-store to use our subclass for this collection.
    # CollectionConfig(type=...) sets target_class_name via the underlying metadata.
    from linkml_store.api.config import CollectionConfig
    coll = HippoCollection(
        name="Sample",
        parent=db,
        metadata=CollectionConfig(type="Sample", alias="Sample"),
    )
    db._collections = {"Sample": coll}

    # Happy path
    print("=== Happy path: insert 2 good samples ===")
    coll.insert([
        {"id": "S1", "is_available": True, "name": "good_one"},
        {"id": "S2", "is_available": True, "name": "good_two"},
    ])
    print(f"  size={coll.size()}, provenance entries={len(coll.provenance)}")
    for p in coll.provenance:
        print(f"    {p}")

    # Validator rejection
    print()
    print("=== Pre-insert hook rejects bad sample ===")
    try:
        coll.insert([{"id": "S3", "is_available": True, "name": "BAD"}])
        print("  ERROR: bad insert should have been rejected!")
    except ValueError as e:
        print(f"  rejected as expected: {e}")
    print(f"  size after rejected insert={coll.size()} (should still be 2)")
    print(f"  provenance entries={len(coll.provenance)} (should still be 2)")

    # Confirm the hook intercepted before the DB write
    print()
    print("=== Final DB state ===")
    res = db.execute_sql("SELECT id, name FROM Sample ORDER BY id")
    for row in res.rows:
        print(" ", row)
