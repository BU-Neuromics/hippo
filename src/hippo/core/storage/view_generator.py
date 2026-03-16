"""SQLite adapter for handling summary views in Hippo."""

from typing import Any, Iterator, List, Optional
import sqlite3
import json

from hippo.config.models import SchemaConfig


class SummaryViewGenerator:
    """Generate and manage summary views for SQLite storage."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def generate_all_summary_views(self, schemas: List[SchemaConfig]) -> List[str]:
        """Generate all summary views based on schema configuration."""
        generated_ddl = []

        for schema in schemas:
            # Process entities that have indexed fields
            view_ddl = self._generate_summary_views_for_schema(schema)
            if view_ddl:
                generated_ddl.extend(view_ddl)

        return generated_ddl

    def _generate_summary_views_for_schema(self, schema: SchemaConfig) -> List[str]:
        """Generate summary views for a specific schema."""
        ddl_statements = []

        # Create a simple count view for each entity type
        count_view_name = f"summary_{schema.name}_count"
        table_name = schema.name

        count_view_ddl = self._generate_count_view(table_name, count_view_name)
        if count_view_ddl:
            ddl_statements.append(count_view_ddl)

        # Create a summary view with multiple aggregations for entities
        agg_view_name = f"summary_{schema.name}_aggregate"
        agg_view_ddl = self._generate_aggregate_view(table_name, agg_view_name, schema)
        if agg_view_ddl:
            ddl_statements.append(agg_view_ddl)

        return ddl_statements

    def _generate_count_view(self, table_name: str, view_name: str) -> Optional[str]:
        """Generate a simple count view for the entity type."""
        # Generate CREATE VIEW statement for total count (active and inactive)
        sql = f"""
        CREATE VIEW IF NOT EXISTS "{view_name}" AS
        SELECT 
            COUNT(*) as count
        FROM "{table_name}"
        """

        return sql

    def _generate_aggregate_view(
        self, table_name: str, view_name: str, schema: SchemaConfig
    ) -> Optional[str]:
        """Generate a comprehensive aggregate view with multiple aggregations."""
        # Get all fields that can be aggregated (numeric types)
        numeric_fields = []

        for field in schema.fields:
            if field.type in ["integer", "float"]:
                numeric_fields.append(field.name)

        if not numeric_fields:
            return None

        # Prepare aggregation columns - one set per numeric field
        agg_columns = []
        for field_name in numeric_fields:
            # COUNT, SUM, AVG aggregations for each numeric field
            agg_columns.append(f"COUNT({field_name}) as {field_name}_count")
            agg_columns.append(f"SUM({field_name}) as {field_name}_sum")
            agg_columns.append(f"AVG({field_name}) as {field_name}_avg")

        if not agg_columns:
            return None

        # Create view with single table scan
        view_sql = f"""
        CREATE VIEW IF NOT EXISTS "{view_name}" AS
        SELECT 
        """

        # Add the aggregate columns
        view_sql += ",\n    ".join(agg_columns)
        view_sql += f"""
        FROM "{table_name}"
        """

        return view_sql

    def create_views_in_migration(self, schemas: List[SchemaConfig]) -> None:
        """Create summary views during schema migration."""
        with self.connection:
            cursor = self.connection.cursor()

            # For each schema in the set, generate and execute view DDL
            for schema in schemas:
                if not schema.name.endswith("s"):
                    continue  # Skip non-table entities

                # Generate specific views for this schema
                view_ddl = self._generate_summary_views_for_schema(schema)

                for ddl in view_ddl:
                    try:
                        cursor.execute(ddl)
                    except Exception as e:
                        print(f"Error creating view: {e}")
