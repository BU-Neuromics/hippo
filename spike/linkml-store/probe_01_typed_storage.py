"""Probe #1: per-class typed storage on DuckDB.

Attaches an in-memory DuckDB store, loads a tiny LinkML schema with two
classes (Sample, Donor) that both `is_a: Entity`, inserts a row in each,
and inspects the resulting tables (column names, types, constraints).
"""

import tempfile
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView
from linkml_store import Client

# Minimal schema: hippo-core-ish Entity + two domain classes that inherit.
SCHEMA = """
id: https://example.org/probe
name: probe
prefixes:
  linkml: https://w3id.org/linkml/
default_prefix: ex
default_range: string
imports: [linkml:types]
classes:
  Entity:
    abstract: true
    attributes:
      id:
        identifier: true
        range: string
        required: true
      is_available:
        range: boolean
        required: true
        ifabsent: "true"
  Sample:
    is_a: Entity
    attributes:
      name:
        range: string
        required: true
      donor:
        range: Donor
  Donor:
    is_a: Entity
    attributes:
      name:
        range: string
"""

with tempfile.TemporaryDirectory() as tmp:
    schema_path = Path(tmp) / "schema.yaml"
    schema_path.write_text(SCHEMA)

    client = Client()
    db = client.attach_database("duckdb", alias="probe")
    db.set_schema_view(SchemaView(str(schema_path)))

    # Per linkml-store docs, collections are created per class.
    sample = db.create_collection("Sample", "Sample")
    donor = db.create_collection("Donor", "Donor")

    # Materialize tables by inserting one row each.
    donor.insert([{"id": "D1", "is_available": True, "name": "AcmeDonor"}])
    sample.insert([{"id": "S1", "is_available": True, "name": "S-one", "donor": "D1"}])

    # Now read back the actual DDL DuckDB emitted.
    print("=" * 60)
    print("Tables in DuckDB:")
    print("=" * 60)
    res = db.execute_sql("SELECT table_name FROM information_schema.tables WHERE table_schema='main'")
    for row in res.rows:
        print("  -", row)

    print()
    print("=" * 60)
    print("Column metadata per table (name, type, nullable, default):")
    print("=" * 60)
    for tbl in ["Sample", "Donor"]:
        print(f"\n[{tbl}]")
        cols = db.execute_sql(
            "SELECT column_name, data_type, is_nullable, column_default "
            f"FROM information_schema.columns WHERE table_name='{tbl}' ORDER BY ordinal_position"
        )
        for row in cols.rows:
            print(" ", row)

    print()
    print("=" * 60)
    print("Constraints (PK, FK, etc.):")
    print("=" * 60)
    for tbl in ["Sample", "Donor"]:
        print(f"\n[{tbl}]")
        cons = db.execute_sql(
            "SELECT constraint_name, constraint_type "
            f"FROM information_schema.table_constraints WHERE table_name='{tbl}'"
        )
        for row in cons.rows:
            print(" ", row)

    print()
    print("=" * 60)
    print("Row counts (insert succeeded?):")
    print("=" * 60)
    print("Sample:", sample.size())
    print("Donor:", donor.size())

    # Try to violate "constraints": insert duplicate id, missing required field, etc.
    print()
    print("=" * 60)
    print("Constraint violation tests:")
    print("=" * 60)
    try:
        donor.insert([{"id": "D1", "is_available": True, "name": "Dup"}])
        print("  Duplicate id D1 ACCEPTED (no PK enforcement)")
    except Exception as e:
        print(f"  Duplicate id D1 rejected: {type(e).__name__}: {e}")

    try:
        sample.insert([{"id": "S2", "donor": "NONEXISTENT", "is_available": True, "name": "X"}])
        print("  Dangling FK donor='NONEXISTENT' ACCEPTED (no FK enforcement)")
    except Exception as e:
        print(f"  Dangling FK rejected: {type(e).__name__}: {e}")

    try:
        sample.insert([{"id": "S3", "is_available": True}])  # missing required 'name'
        print("  Missing required 'name' ACCEPTED (no NOT NULL at storage)")
    except Exception as e:
        print(f"  Missing required 'name' rejected: {type(e).__name__}: {e}")
