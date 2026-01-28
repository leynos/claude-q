"""Helper wrappers around json5kit for JSON5 settings files."""

from __future__ import annotations

import json
import typing as typ

import json5kit


def loads(source: str) -> dict[str, typ.Any]:
    """Parse JSON5 source into a Python dictionary.

    Args:
        source: Raw JSON5 string.

    Returns:
        Parsed dictionary.

    """
    parsed = json5kit.parse(source)
    return json.loads(parsed.to_json())


def dumps(data: dict[str, typ.Any]) -> str:
    """Serialize data to JSON5-compatible source.

    Args:
        data: Dictionary to serialize.

    Returns:
        JSON5-compatible string with stable formatting.

    """
    source = json.dumps(data, indent=2)
    return json5kit.parse(source).to_source() + "\n"
