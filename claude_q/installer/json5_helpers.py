"""Helper wrappers around json5kit for JSON5 settings files.

Examples
--------
Round-trip JSON5 content::

    settings = loads('{"hooks": {"stop": {"enabled": true}}}')
    content = dumps(settings)

The helpers return plain dictionaries and raise ``ValueError`` or ``TypeError``
if the JSON5 source is invalid.

"""

from __future__ import annotations

import json
import typing as typ

import json5kit


def loads(source: str) -> dict[str, typ.Any]:
    """Parse JSON5 source into a Python dictionary.

    Parameters
    ----------
    source : str
        Raw JSON5 string.

    Returns
    -------
    dict[str, typing.Any]
        Parsed dictionary.

    """
    parsed = json5kit.parse(source)
    return json.loads(parsed.to_json())


def dumps(data: dict[str, typ.Any]) -> str:
    """Serialize data to JSON5-compatible source.

    Parameters
    ----------
    data : dict[str, typing.Any]
        Dictionary to serialize.

    Returns
    -------
    str
        JSON5-compatible string with stable formatting.

    """
    source = json.dumps(data, indent=2)
    return json5kit.parse(source).to_source() + "\n"
