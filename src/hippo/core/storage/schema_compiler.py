"""Schema compiler for converting Hippo DSL to LinkML."""

import json
from typing import Dict, Any, List
from pathlib import Path


def compile_schema_to_linkml(
    schema_content: Dict[str, Any], format: str = "yaml"
) -> str:
    """
    Compile a Hippo DSL schema to LinkML format.

    Args:
        schema_content: The parsed Hippo DSL schema content
        format: Output format ("yaml" or "json")

    Returns:
        String representation of the compiled schema in requested format

    Raises:
        ValueError: If schema content is invalid or unsupported format
    """
    # Validate input
    if not isinstance(schema_content, dict):
        raise ValueError("Schema content must be a dictionary")

    # Build LinkML structure from Hippo DSL
    linkml_schema = _build_linkml_schema(schema_content)

    # Convert to requested format
    if format.lower() == "json":
        return json.dumps(linkml_schema, indent=2)
    else:  # default to yaml
        import yaml

        return yaml.dump(linkml_schema, default_flow_style=False, sort_keys=False)


def _build_linkml_schema(schema_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a LinkML schema from Hippo DSL content.

    Args:
        schema_content: The parsed Hippo DSL schema

    Returns:
        Dictionary representing the LinkML schema
    """
    # Extract schema metadata
    name = schema_content.get("name", "hippo_schema")
    description = schema_content.get("description", "Compiled from Hippo DSL")

    # Build base LinkML schema structure
    linkml_schema = {
        "id": f"https://example.org/{name}",
        "name": name,
        "description": description,
        "prefixes": {
            "linkml": "https://w3id.org/linkml/",
            "schema": "http://schema.org/",
        },
        "imports": ["linkml:types"],
        "classes": {},
    }

    # Extract entities and convert to classes
    entities = schema_content.get("entities", [])

    for entity in entities:
        class_def = _build_class_from_entity(entity)
        linkml_schema["classes"][entity["name"]] = class_def

    return linkml_schema


def _build_class_from_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a LinkML class definition from an entity definition.

    Args:
        entity: The Hippo entity definition

    Returns:
        Dictionary representing the LinkML class
    """
    class_def = {
        "description": entity.get("description", ""),
        "attributes": {},
    }

    # Process properties (attributes)
    properties = entity.get("properties", [])
    for prop in properties:
        attr_name = prop.get("name")
        if not attr_name:
            continue

        attr_def = _build_attribute_from_property(prop)
        class_def["attributes"][attr_name] = attr_def

    # Handle relationships
    relationships = entity.get("relationships", [])
    for rel in relationships:
        attr_def = _build_relationship_from_definition(rel)
        class_def["attributes"][rel["name"]] = attr_def

    return class_def


def _build_attribute_from_property(prop: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a LinkML attribute (property) definition from a Hippo property.

    Args:
        prop: The Hippo property definition

    Returns:
        Dictionary representing the LinkML attribute
    """
    # Map Hippo types to LinkML types
    type_map = {
        "string": "string",
        "integer": "integer",
        "float": "float",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
        "uri": "uri",
        "enum": "string",
        "list": "string",
        "dict": "string",
        "reference": "string",  # References are strings in LinkML
    }

    attr_type = prop.get("type", "string")
    linkml_type = type_map.get(attr_type, "string")

    attr_def = {
        "description": prop.get("description", ""),
        "range": linkml_type,
        "required": prop.get("required", False),
    }

    # Handle enum values
    if attr_type == "enum" and "values" in prop:
        attr_def["examples"] = [{"value": val} for val in prop["values"]]

    # Handle constraints
    if "min_length" in prop:
        attr_def["minimum_length"] = prop["min_length"]

    if "max_length" in prop:
        attr_def["maximum_length"] = prop["max_length"]

    if "pattern" in prop:
        attr_def["pattern"] = prop["pattern"]

    # Handle references
    if "references" in prop:
        attr_def["range"] = "string"  # Reference attributes are strings in LinkML

    return attr_def


def _build_relationship_from_definition(rel: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a LinkML attribute definition from a relationship definition.

    Args:
        rel: The relationship definition

    Returns:
        Dictionary representing the LinkML attribute for the relationship
    """
    # Map relationship cardinality to LinkML
    range_type = "string"  # Default to string for reference

    # For relationships, we map them to a "string" type since they represent references
    rel_def = {
        "description": rel.get("description", ""),
        "range": range_type,
        "required": rel.get("required", False),
    }

    # Handle cardinality (1..1, 0..1, 1..*, 0..*) - these are conceptual in LinkML
    if "cardinality" in rel:
        rel_def["cardinality"] = rel["cardinality"]

    return rel_def
