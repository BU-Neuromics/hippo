"""Tests for schema-related CLI commands."""

import tempfile
import os
from pathlib import Path
import yaml
import pytest
from typer.testing import CliRunner

from hippo.cli.main import app


def test_compile_schema_command():
    """Test the compile-schema command with a sample schema."""
    runner = CliRunner()

    # Create a temporary schema file
    schema_content = {
        "name": "test_schema",
        "description": "A test schema",
        "entities": [
            {
                "name": "User",
                "description": "A user entity",
                "properties": [
                    {
                        "name": "id",
                        "type": "integer",
                        "description": "User ID",
                        "required": True,
                    },
                    {"name": "name", "type": "string", "description": "User name"},
                ],
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(schema_content, f)
        schema_file = f.name

    try:
        # Test that the command runs without error
        result = runner.invoke(app, ["compile-schema", schema_file])
        assert result.exit_code == 0
        assert "Compilation complete" in result.stdout
    finally:
        os.unlink(schema_file)


def test_schema_diff_command():
    """Test the schema-diff command with two sample schemas."""
    runner = CliRunner()

    # Create two temporary schema files
    schema1_content = {
        "name": "test_schema_1",
        "entities": [
            {
                "name": "User",
                "properties": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                ],
            }
        ],
    }

    schema2_content = {
        "name": "test_schema_2",
        "entities": [
            {
                "name": "User",
                "properties": [
                    {"name": "id", "type": "integer"},
                    {
                        "name": "email",
                        "type": "string",  # Added email field
                    },
                ],
            }
        ],
    }

    files = []
    try:
        for i, content in enumerate([schema1_content, schema2_content], 1):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(content, f)
                files.append(f.name)

        # Test that the diff command runs without error
        result = runner.invoke(app, ["schema-diff", files[0], files[1]])
        assert result.exit_code == 0
        assert "Schema comparison complete" in result.stdout

    finally:
        for f in files:
            os.unlink(f)


def test_validate_command():
    """Test the validate command with a valid schema."""
    runner = CliRunner()

    # Create a temporary schema file
    schema_content = {
        "name": "test_schema",
        "entities": [
            {"name": "User", "properties": [{"name": "id", "type": "integer"}]}
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(schema_content, f)
        schema_file = f.name

    try:
        # Test that the validate command runs without error
        result = runner.invoke(app, ["validate", "--schema", schema_file])
        assert result.exit_code == 0
        assert "Validation passed" in result.stdout
    finally:
        os.unlink(schema_file)


if __name__ == "__main__":
    test_compile_schema_command()
    test_schema_diff_command()
    test_validate_command()
    print("All tests passed!")
