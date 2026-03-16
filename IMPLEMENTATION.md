# Schema Diff Command Implementation

This document describes the implementation of the `hippo schema diff` command as requested.

## Features Implemented

The `hippo schema diff` command provides:
1. **Command Access**: `hippo schema diff <file1> <file2>`
2. **File Validation**: Checks for valid file paths and shows clear errors
3. **Human-readable Output**: Shows added/removed/modified elements clearly formatted 
4. **Detailed Comparison**: Compares all schema structure including entities and properties

## Command Usage
```
hippo schema diff schema1.yaml schema2.yaml
```

## Example Output
```
Comparing schema1.yaml and schema2.yaml
============================================================

Added entities:
  + Project

Entity 'Organization' changes:
  Added property: address
    Type: string
    Required: False
    Description: Physical address

Entity 'Person' changes:
  Added property: phone
    Type: string
    Required: False
    Description: Phone number
============================================================
Schema comparison complete
```

## Implementation Details

The implementation:
- Resides in `src/hippo/cli/main.py`
- Uses proper YAML parsing with error handling  
- Handles both entity-level and property-level differences
- Provides clean, formatted output for readability
- Includes comprehensive error handling for file operations