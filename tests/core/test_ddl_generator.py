"""Tests for DDL generation from a LinkML-backed SchemaRegistry."""

import pytest

from hippo.core.storage.ddl_generator import DDLGenerator
from hippo.linkml_bridge import SchemaRegistry
from tests.support.linkml_schemas import build_registry


class TestTypeMapping:
    @pytest.mark.parametrize(
        "linkml_type,expected",
        [
            ("string", "TEXT"),
            ("integer", "INTEGER"),
            ("float", "REAL"),
            ("double", "REAL"),
            ("decimal", "REAL"),
            ("boolean", "INTEGER"),
            ("date", "TEXT"),
            ("datetime", "TEXT"),
            ("uri", "TEXT"),
            ("uriorcurie", "TEXT"),
        ],
    )
    def test_linkml_type_maps_to_sqlite(self, linkml_type: str, expected: str):
        assert DDLGenerator.TYPE_MAPPING[linkml_type] == expected

    def test_unknown_slot_range_defaults_to_text(self):
        reg = build_registry(
            {
                "item": {
                    "attributes": {
                        "id": {"identifier": True},
                        "mystery": {"range": "not-a-real-type"},
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert '"mystery" TEXT' in ddl[0]


class TestBasicTableGeneration:
    def test_emits_create_table(self):
        reg = build_registry(
            {
                "test_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "name": {"range": "string"},
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert any('CREATE TABLE "test_entity"' in s for s in ddl)

    def test_includes_id_column(self):
        reg = build_registry(
            {"test_entity": {"attributes": {"id": {"identifier": True}}}}
        )
        ddl = DDLGenerator().generate(reg)
        assert '"id" TEXT' in ddl[0]

    def test_includes_is_available_with_default_1(self):
        reg = build_registry(
            {"test_entity": {"attributes": {"id": {"identifier": True}}}}
        )
        ddl = DDLGenerator().generate(reg)
        assert '"is_available" INTEGER' in ddl[0]
        assert "DEFAULT 1" in ddl[0]

    def test_includes_superseded_by_column(self):
        reg = build_registry(
            {"test_entity": {"attributes": {"id": {"identifier": True}}}}
        )
        ddl = DDLGenerator().generate(reg)
        assert '"superseded_by" TEXT' in ddl[0]

    def test_abstract_class_is_skipped(self):
        reg = build_registry(
            {
                "AbstractBase": {
                    "abstract": True,
                    "attributes": {"id": {"identifier": True}},
                },
                "Concrete": {
                    "is_a": "AbstractBase",
                    "attributes": {"name": {"range": "string"}},
                },
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert not any('CREATE TABLE "AbstractBase"' in s for s in ddl)
        assert any('CREATE TABLE "Concrete"' in s for s in ddl)


class TestPrimaryKey:
    def test_identifier_slot_is_primary_key(self):
        reg = build_registry(
            {"test_entity": {"attributes": {"id": {"identifier": True}}}}
        )
        ddl = DDLGenerator().generate(reg)
        assert "PRIMARY KEY" in ddl[0]


class TestForeignKey:
    def test_class_range_becomes_foreign_key(self):
        reg = build_registry(
            {
                "parent_entity": {"attributes": {"id": {"identifier": True}}},
                "child_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "parent_id": {"range": "parent_entity"},
                    }
                },
            }
        )
        ddl = "\n".join(DDLGenerator().generate(reg))
        assert "FOREIGN KEY" in ddl
        assert '"parent_entity"' in ddl


class TestUniqueConstraint:
    def test_hippo_unique_annotation_emits_unique(self):
        reg = build_registry(
            {
                "test_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "email": {
                            "range": "string",
                            "annotations": {"hippo_unique": True},
                        },
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert "UNIQUE" in ddl[0]

    def test_linkml_unique_keys_emit_composite_unique(self):
        reg = build_registry(
            {
                "organization": {
                    "attributes": {
                        "id": {"identifier": True},
                        "name": {"range": "string"},
                        "code": {"range": "string"},
                    },
                    "unique_keys": {
                        "name_code": {"unique_key_slots": ["name", "code"]}
                    },
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert 'UNIQUE ("name", "code")' in ddl[0]


class TestDefaultValue:
    def test_string_default_via_ifabsent(self):
        reg = build_registry(
            {
                "test_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "status": {
                            "range": "string",
                            "ifabsent": "active",
                        },
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert "DEFAULT 'active'" in ddl[0]


class TestIndexGeneration:
    def test_hippo_index_emits_create_index(self):
        reg = build_registry(
            {
                "test_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "name": {
                            "range": "string",
                            "annotations": {"hippo_index": True},
                        },
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert len(ddl) == 2
        assert "CREATE INDEX" in ddl[1]
        assert "idx_test_entity_name" in ddl[1]

    def test_hippo_index_partial_adds_where(self):
        reg = build_registry(
            {
                "test_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "name": {
                            "range": "string",
                            "annotations": {
                                "hippo_index": True,
                                "hippo_index_partial": True,
                            },
                        },
                    }
                }
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert "WHERE is_available = 1" in ddl[1]


class TestInheritance:
    def test_child_class_has_foreign_key_to_parent(self):
        reg = build_registry(
            {
                "parent_entity": {
                    "attributes": {
                        "id": {"identifier": True},
                        "created_at": {"range": "datetime"},
                    }
                },
                "child_entity": {
                    "is_a": "parent_entity",
                    "attributes": {"name": {"range": "string"}},
                },
            }
        )
        ddl = "\n".join(DDLGenerator().generate(reg))
        assert "FOREIGN KEY" in ddl
        assert '"parent_entity"' in ddl

    def test_parent_table_generated_before_child(self):
        reg = build_registry(
            {
                "parent_entity": {"attributes": {"id": {"identifier": True}}},
                "child_entity": {
                    "is_a": "parent_entity",
                    "attributes": {},
                },
            }
        )
        ddl = DDLGenerator().generate(reg)
        parent_idx = next(i for i, s in enumerate(ddl) if "parent_entity" in s)
        child_idx = next(i for i, s in enumerate(ddl) if "child_entity" in s)
        assert parent_idx < child_idx


class TestMultiClass:
    def test_two_unrelated_classes_both_generated(self):
        reg = build_registry(
            {
                "entity_a": {
                    "attributes": {
                        "id": {"identifier": True},
                        "field1": {"range": "string"},
                    }
                },
                "entity_b": {
                    "attributes": {
                        "id": {"identifier": True},
                        "field2": {"range": "string"},
                    }
                },
            }
        )
        ddl = DDLGenerator().generate(reg)
        assert len(ddl) == 2

    def test_full_schema_with_unique_index_and_fk(self):
        reg = build_registry(
            {
                "organization": {
                    "attributes": {
                        "id": {"identifier": True},
                        "name": {"range": "string", "required": True},
                        "code": {
                            "range": "string",
                            "annotations": {
                                "hippo_unique": True,
                                "hippo_index": True,
                            },
                        },
                        "active": {
                            "range": "boolean",
                        },
                    }
                },
                "user": {
                    "attributes": {
                        "id": {"identifier": True},
                        "username": {"range": "string", "required": True},
                        "org_id": {"range": "organization"},
                        "created_at": {"range": "datetime"},
                    }
                },
            }
        )
        ddl = DDLGenerator().generate(reg)
        full = "\n".join(ddl)
        assert "UNIQUE" in full
        assert "CREATE INDEX" in full
        assert "FOREIGN KEY" in full


class TestHippoCoreProvenanceRecordDDL:
    """DDL emitted for the ProvenanceRecord class declared in hippo_core.

    The `provenance-migration` change (sec9 §9.6 / Decision 9.6.A) replaces
    the legacy hand-coded `provenance` table with a DDL-generated
    `ProvenanceRecord` table. This test class verifies the generator emits
    the expected shape *before* legacy DDL is removed.
    """

    @pytest.fixture
    def registry(self) -> SchemaRegistry:
        # User schema importing hippo_core. The registry's class_names()
        # includes every class in hippo_core (Entity, ProvenanceRecord,
        # Process, Validator, ReferenceLoader) — the generator iterates
        # all of them.
        yaml_text = (
            "id: https://example.org/test\n"
            "name: test\n"
            "prefixes: {linkml: 'https://w3id.org/linkml/'}\n"
            "default_range: string\n"
            "imports:\n"
            "  - linkml:types\n"
            "  - hippo_core\n"
            "classes: {}\n"
        )
        return SchemaRegistry.from_yaml(yaml_text)

    @pytest.fixture
    def ddl(self, registry: SchemaRegistry) -> list[str]:
        return DDLGenerator().generate(registry)

    @pytest.fixture
    def prov_table(self, ddl: list[str]) -> str:
        matches = [s for s in ddl if 'CREATE TABLE "ProvenanceRecord"' in s]
        assert matches, "ProvenanceRecord CREATE TABLE not emitted"
        return matches[0]

    def test_provenance_record_table_exists(self, ddl: list[str]):
        assert any('CREATE TABLE "ProvenanceRecord"' in s for s in ddl)

    def test_provenance_record_has_all_sec9_columns(self, prov_table: str):
        # sec9 §9.6 defines the slot inventory. Each slot must map to a column.
        for col in [
            "id",
            "entity_id",
            "entity_type",
            "operation",
            "actor_id",
            "timestamp",
            "schema_version",
            "derived_from_id",
            "process_id",
            "patch",
            "context",
        ]:
            assert f'"{col}"' in prov_table, f"column {col!r} missing from DDL"

    def test_provenance_record_inherits_is_available_and_superseded_by(
        self, prov_table: str
    ):
        # Inherited from Entity (is_available) or appended by the generator.
        assert '"is_available"' in prov_table
        assert '"superseded_by"' in prov_table

    def test_provenance_record_id_is_primary_key(self, prov_table: str):
        assert '"id" TEXT PRIMARY KEY' in prov_table

    def test_provenance_record_required_slots_are_not_null(self, prov_table: str):
        # required=true slots per hippo_core.yaml: operation, actor_id,
        # timestamp, schema_version.
        for col in ("operation", "actor_id", "timestamp", "schema_version"):
            assert f'"{col}" TEXT NOT NULL' in prov_table, (
                f"column {col!r} should be NOT NULL"
            )

    def test_provenance_record_indexes_on_annotated_slots(self, ddl: list[str]):
        # sec9 §9.6 annotates entity_id, operation, timestamp, process_id
        # with hippo_index.
        full = "\n".join(ddl)
        for slot in ("entity_id", "operation", "timestamp", "process_id"):
            assert f'idx_ProvenanceRecord_{slot}' in full, (
                f"index on ProvenanceRecord.{slot} missing"
            )

    def test_process_fk_from_provenance_record(self, prov_table: str):
        # process_id has range Process (another class in hippo_core) — should
        # become a foreign key constraint.
        assert 'FOREIGN KEY ("process_id") REFERENCES "Process"' in prov_table
